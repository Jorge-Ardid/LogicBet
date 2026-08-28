#!/usr/bin/env python3
"""Автономний cron-воркер розрахунку LogicBet (v29).

Проблема, яку він закриває: сетлмент ставок виконувався лише "ліниво" —
при відкритті /api/bets або /api/matches у браузері. Якщо ніхто не заходив
на сайт, вчорашні матчі зі ставками зависали в PENDING/Аналітиці.

Цей скрипт не потребує Flask-сервера і браузера: він імпортує той САМИЙ
settle_pending_bets() з webapp/app.py (єдине джерело правди — без дублювання
логіки), примусово підтягує фінальні рахунки через Football-Data fallback
та оновлює статуси матчів/ставок за часом.

Використання:
    python cron_settle.py                 # один прохід (для cron/scheduler)
    python cron_settle.py --loop 900      # демон: цикл кожні 15 хвилин
    python cron_settle.py --force-fd      # форсувати FD-запит (обійти тротлінг)
    python cron_settle.py --no-fd         # не ходити в Football-Data взагалі

Приклад рядка для PythonAnywhere → Tasks → Scheduled task:
    */15 * * * * cd /home/LogicBetAI/LogicBet/python && \\
        /home/LogicBetAI/.local/bin/python3 cron_settle.py >> ../cron_settle.log 2>&1

НІЧНИЙ ГАРАНТОВАНИЙ ПРОГІН (до ранку все пораховано):
  • PythonAnywhere Tasks → Scheduled task:
      0 1 * * * cd /home/LogicBetAI/LogicBet/python && \\
          python3 cron_settle.py --force-fd --force-bet365 >> ../cron_settle.log 2>&1
  • Або GitHub Actions: .github/workflows/nightly_settle.yml (cron 01:00 UTC,
    уже в репо) — сам підтягне результати, розрахує ставки і закомітить
    оновлені logicbet.db / user_data.db.

Робоча директорія значення не має: скрипт сам додає корінь репо та webapp/
у sys.path, тож env-логіка LOGICBET_DATA_DB / LOGICBET_DB_PATH працює як у
проді. На PythonAnywhere шляхи дефолтні — додаткових змінних не треба.
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, os.path.join(ROOT, "webapp"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Імпорт webapp.app створює Flask-додаток, але НЕ запускає сервер
# (app.run лише під if __name__ == "__main__"), тож імпорт безпечний.
from webapp.app import (                      # noqa: E402
    settle_pending_bets,
    fetch_finished_scores_from_fd,
    maybe_sync_bet365_odds,
    db,
)
import webapp.app as _WAPP                    # noqa: E402  (патч глобалів)


def update_match_statuses():
    """М'яка синхронізація статусів із реальним часом (v29).

    - PENDING-ставка, матч якої почався понад 3 години тому і досі без
      фінального рахунку -> AWAITING (прибирається з Аналітики, показується
      в Історії як «ОЧІКУЄ РЕЗУЛЬТАТУ»).
    - AWAITING-ставка, у якої з'явився рахунок -> повертається у PENDING,
      щоб наступний settle_pending_bets() одразу її розрахував.
    Відповідає вимозі «автономне перенесення закритих матчів в Історію»:
    жоден завершений матч не залишається в активному списку.
    Повертає dict із лічильниками.
    """
    with db.get_connection() as conn:
        cur = conn.execute("""
            UPDATE user_bets SET status='AWAITING'
            WHERE status='PENDING' AND match_id IN (
                SELECT id FROM matches
                WHERE date < datetime('now', '-3 hours')
                  AND (home_score IS NULL OR away_score IS NULL
                       OR status NOT IN ('FT','AET','PEN','FINISHED'))
            )
        """)
        to_await = cur.rowcount or 0

        # Рахунок доїхав (наприклад, CI-синком) — AWAITING знову готовий
        # до розрахунку.
        cur2 = conn.execute("""
            UPDATE user_bets SET status='PENDING'
            WHERE status='AWAITING' AND match_id IN (
                SELECT id FROM matches
                WHERE status IN ('FT','AET','PEN','FINISHED')
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
            )
        """)
        to_pending = cur2.rowcount or 0
        conn.commit()
    return {"pending_to_awaiting": to_await, "awaiting_to_pending": to_pending}


def run_cycle(force_fd=False, use_fd=True, force_b365=False, use_b365=True):
    """Один повний прохід: b365-ліги -> FD-рахунки -> settle -> статуси."""
    b365_res = None
    if use_b365:
        try:
            import bet365_client as _b365
            plan = _b365.accumulator_plan(db.get_config)
            print("[CRON] b365 plan:", plan)
            b365_res = maybe_sync_bet365_odds(force=force_b365)
            # Щоб settle всередині не запускав sync вдруге (він викликає
            # СВІЙ глобал webapp.app.maybe_sync_bet365_odds) — патчу саме
            # атрибут модуля webapp.app на час settle.
            _orig = _WAPP.maybe_sync_bet365_odds
            _WAPP.maybe_sync_bet365_odds = lambda force=False: None
            try:
                settle = settle_pending_bets()
            finally:
                _WAPP.maybe_sync_bet365_odds = _orig
        except Exception as exc:                 # noqa: BLE001
            print("[CRON] b365 sync error:", exc)
            b365_res = {"error": str(exc)}
            try:
                settle = settle_pending_bets()
            except Exception as exc2:            # noqa: BLE001
                print("[CRON] settle error:", exc2)
                settle = {"error": str(exc2)}
    else:
        try:
            settle = settle_pending_bets()
        except Exception as exc:                 # noqa: BLE001
            print("[CRON] settle error:", exc)
            settle = {"error": str(exc)}
    fd_res = None
    if use_fd:
        try:
            fd_res = fetch_finished_scores_from_fd(force=force_fd)
        except Exception as exc:                 # noqa: BLE001
            print("[CRON] FD fetch error:", exc)
            fd_res = {"error": str(exc)}
    statuses = update_match_statuses()
    summary = {"b365": b365_res, "fd": fd_res, "settle": settle,
               "statuses": statuses}
    print("[CRON] cycle:", summary)
    return summary


def main():
    ap = argparse.ArgumentParser(description="LogicBet auto-settle cron worker")
    ap.add_argument("--loop", type=int, default=0,
                    help="секунд між циклами; 0 = один прохід і вихід")
    ap.add_argument("--force-fd", action="store_true",
                    help="форсувати Football-Data запит (обійти тротлінг)")
    ap.add_argument("--no-fd", action="store_true",
                    help="не ходити в Football-Data у цьому запуску")
    ap.add_argument("--force-bet365", action="store_true",
                    help="форсувати Bet365 ліговий забір (обійти денний ліміт)")
    ap.add_argument("--no-bet365", action="store_true",
                    help="не ходити в Bet365 у цьому запуску")
    args = ap.parse_args()

    while True:
        run_cycle(force_fd=args.force_fd, use_fd=not args.no_fd,
                  force_b365=args.force_bet365, use_b365=not args.no_bet365)
        if args.loop <= 0:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
