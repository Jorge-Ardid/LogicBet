#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Одноразовий примусовий розрахунок 3 legacy-ставок (v29).

Симулює повний цикл «списання -> розрахунок» для трьох матчів:
  1) Celta — Osasuna 1:2        | ТМ 1.5 (1st half) @ 1.37 -> LOST
  2) Barcelona — Athletic 2:0   | П1                  @ 1.25 -> WON (виплата 12.5)
  3) Real Madrid — Sociedad 4:1 | 1X                  @ 1.03 -> WON (виплата 10.3)

Бухгалтерія (модель v26):
  - за кожну НОВУ ставку списується 10.0 грн (разом -30.0);
  - WON зараховує ПОВНУ виплату stake*odd (+12.5 та +10.3);
  - LOST нічого не повертає (стейк уже списаний).

Ідемпотентний: PENDING-ставка на матчі перезаписується БЕЗ повторного
списання. Після розрахунку матчі зникають з «Аналітики» (фільтр минулих
дат) і з'являються в «Історії» зі статусами WON/LOST. Запуск з кореня:
    python python/settle_legacy_bets.py
"""

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, os.path.join(ROOT, "webapp"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import webapp.app as W                     # noqa: E402  (ініціалізує db)

STAKE = 10.0

LEGS = [
    {"match_id": 1272, "home": "Celta", "away": "Osasuna",
     "score": (1, 2), "selection": "ТМ 1.5 (1st half)",
     "market": "1st Half Goals", "odd": 1.37, "expect": "LOST"},
    {"match_id": 1273, "home": "Barcelona", "away": "Athletic Club",
     "score": (2, 0), "selection": "П1",
     "market": "1X2", "odd": 1.25, "expect": "WON"},
    {"match_id": 1223, "home": "Real Madrid", "away": "Real Sociedad",
     "score": (4, 1), "selection": "1X",
     "market": "Double Chance", "odd": 1.03, "expect": "WON"},
]


def get_bankroll():
    with W.db.get_connection() as c:
        r = c.execute("SELECT value FROM config WHERE key='bankroll'").fetchone()
        return float(r[0]) if r and r[0] else 1000.0


def set_bankroll(v):
    with W.db.get_connection() as c:
        c.execute("INSERT INTO config (key, value) VALUES ('bankroll', ?) "
                  "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                  (str(round(v, 2)),))
        c.commit()



def sync_scores():
    """Рахунки/статус трьох матчів у data-БД — точно як у завданні."""
    dconn = sqlite3.connect(W.DATA_DB_PATH)
    try:
        for leg in LEGS:
            h, a = leg["score"]
            dconn.execute(
                "UPDATE matches SET status='FT', home_score=?, away_score=?, "
                "finished_at=COALESCE(finished_at, datetime('now')) WHERE id=?",
                (h, a, leg["match_id"]))
        dconn.commit()
    finally:
        dconn.close()


def place_or_update():
    """Створює/оновлює 3 ставки; повертає кількість НОВИХ (для списання)."""
    new_placed = 0
    for leg in LEGS:
        with W.db.get_connection() as c:
            cur = c.execute(
                "SELECT id, status FROM user_bets WHERE match_id=? "
                "ORDER BY id DESC LIMIT 1", (leg["match_id"],)).fetchone()
            if cur and cur[1] == "PENDING":
                # Вже висить ставка — оновлюємо вибір/кеф, НЕ списаємо вдруге.
                c.execute("UPDATE user_bets SET selection=?, odd=?, market=? "
                          "WHERE id=?", (leg["selection"], leg["odd"],
                                         leg["market"], cur[0]))
                print("  #%d %s — PENDING оновлено (без списання)"
                      % (leg["match_id"], leg["selection"]))
            else:
                if cur:
                    # Стара розрахована ставка (напр. AI-сід) — лишаємо її
                    # в історії і кладемо окрему нову ставку користувача.
                    print("  #%d стара ставка %s — додаю нову PENDING"
                          % (leg["match_id"], cur[1]))
                c.execute(
                    "INSERT INTO user_bets (match_id, market, selection, "
                    "stake, odd, status, profit) "
                    "VALUES (?, ?, ?, ?, ?, 'PENDING', 0.0)",
                    (leg["match_id"], leg["market"], leg["selection"],
                     STAKE, leg["odd"]))
                new_placed += 1
                print("  #%d %s @ %.2f — нова ставка, списано %.2f"
                      % (leg["match_id"], leg["selection"], leg["odd"], STAKE))
            c.commit()
    return new_placed


def main():
    print("=== LogicBet legacy settle (3 bets) ===")
    b0 = get_bankroll()
    print("Bankroll before: %.2f" % b0)

    # 1) рахунки матчів — точно як у завданні
    sync_scores()

    # 2) детермінований локальний режим: без мережевих хуків
    W.fetch_finished_scores_from_fd = lambda force=False: {"skipped": True}
    W.maybe_refresh_recent_stats = lambda: None
    W.maybe_sync_bet365_odds = lambda: None

    # 3) ставки: списання за нові
    placed = place_or_update()
    if placed:
        set_bankroll(get_bankroll() - STAKE * placed)
        print("Deducted %.2f UAH for %d new bets" % (STAKE * placed, placed))

    # 4) розрахунок (той самий сетлмент, що й у вебі)
    res = W.settle_pending_bets()
    print("Settle result:", res)

    # 5) верифікація статусів і математики
    ok = True
    b1 = get_bankroll()
    payout_won = 0.0
    with W.db.get_connection() as c:
        for leg in LEGS:
            r = c.execute("SELECT status, profit, odd, stake FROM user_bets "
                          "WHERE match_id=? ORDER BY id DESC LIMIT 1",
                          (leg["match_id"],)).fetchone()
            status = r[0] if r else None
            mark = "OK " if status == leg["expect"] else "FAIL"
            if status != leg["expect"]:
                ok = False
            if status == "WON":
                payout_won += float(r[3]) * float(r[2])
            print("  [%s] #%d %-24s -> %s (profit %s)"
                  % (mark, leg["match_id"], leg["selection"], status,
                     (round(float(r[1]), 2) if r and r[1] is not None else "-")))
    expected_bank = round(b0 - STAKE * placed + payout_won, 2)
    if abs(b1 - expected_bank) > 0.01:
        ok = False
        print("BANKROLL MISMATCH: %.2f != %.2f" % (b1, expected_bank))
    print("Bankroll after: %.2f (expected %.2f)" % (b1, expected_bank))

    # 6) Аналітика vs Історія
    client = W.app.test_client()
    ids_matches = [m["id"] for g in
                   client.get("/api/matches").get_json()["groups"]
                   for m in g["matches"]]
    for leg in LEGS:
        if leg["match_id"] in ids_matches:
            ok = False
            print("FAIL: match %d досі в Аналітиці" % leg["match_id"])
    hist = {b["id"]: (b.get("bet") or {}).get("status")
            for b in client.get("/api/bets?limit=300").get_json()["bets"]}
    for leg in LEGS:
        st = hist.get(leg["match_id"])
        if st != leg["expect"]:
            ok = False
            print("FAIL: match %d в Історії зі статусом %s" % (leg["match_id"], st))
        else:
            print("  Історія: #%d -> %s" % (leg["match_id"], st))

    print("LEGACY_SETTLE_" + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

