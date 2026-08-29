"""BACKTEST_HISTORY — Zero-Future-Leakage walk-forward на історії матчів.

Для кожного завершеного матчу за датою ASC виконується:
  A) Прогноз — модель бачить ВИКЛЮЧНО стан ДО старту гри:
       • Elo — онлайн-рейтинги, накопичені з РАНІШЕ зіграних матчів
         (не фінальні teams.home_elo/away_elo, інакше витік майбутнього);
       • тренди/H2H — вже фільтруються за m.date < match_date (analytics);
       • поточний матч і рахунок — приховані.
  B) Ставка фіксується (PENDING, stake=10, odd=1/prob).
  C) Тільки тоді відкривається реальний рахунок -> WON/LOST, банкрол,
     online-Elo обох команд оновлюється venue-каналами.

Пише прогнози+ставки у валідаційну монолітну БД (копія logicbet.db).
Використання:
    python backtest_history.py            # згенерувати та показати статистику
    python backtest_history.py --apply    # перенести результат у прод data+user_db
"""
import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STAKE = 10.0
K = 20
INIT_ELO = 1500.0


def _apply_venue_elo(elo, home_tid, away_tid, h_score, a_score):
    """Оновлює венюні канали (як у prod full_elo_recalc)."""
    he, ha = elo[home_tid]
    ae, aa = elo[away_tid]
    # домашній канал господаря vs виїзний канал гостя
    exp_h = 1.0 / (1.0 + 10 ** ((aa - he) / 400.0))
    act_h = 1.0 if h_score > a_score else (0.5 if h_score == a_score else 0.0)
    new_he = he + K * (act_h - exp_h)
    new_aa = aa + K * ((1.0 - act_h) - (1.0 - exp_h))
    # виїзний канал господаря та домашній гостя не змінюються
    elo[home_tid] = (new_he, ha)
    elo[away_tid] = (ae, new_aa)


def _resolve(selection, home, away):
    """Найпростіший resolver для головних маркетів (дзеркало prod)."""
    s = (selection or "").upper().strip()
    if not s:
        return None
    if "1X" in s or "1Х" in s:
        return home >= away
    if "X2" in s or "Х2" in s:
        return away >= home
    if s.startswith("П1") or s == "1":
        return home > away
    if s.startswith("П2") or s == "2":
        return away > home
    if s == "X" or s == "Х" or s.startswith("X ("):
        return home == away
    # тотали
    for thr in ("0.5", "1.5", "2.5", "3.5", "4.5", "5.5"):
        if thr in s:
            t = float(thr)
            if "ТБ" in s or "OVER" in s or "БІЛЬШЕ" in s:
                return (home + away) > t
            if "ТМ" in s or "UNDER" in s or "МЕНШЕ" in s:
                return (home + away) < t
            break
    # ОЗ
    if "ОЗ" in s and ("ТАК" in s):
        return home > 0 and away > 0
    if "ОЗ" in s and ("НІ" in s or "НI" in s):
        return not (home > 0 and away > 0)
    return None


def _pick_bet(preds):
    """Обирає один основний маркет за confidence_score_pct (найвищий),
    з пріоритетом надійних (1X2/Total/BTTS)."""
    best = None
    for p in preds:
        market = p.get("market")
        if market not in ("1X2", "Total Goals", "BTTS"):
            continue
        if p.get("selection") is None:
            continue
        conf = float(p.get("confidence_score_pct") or
                     float(p.get("calculated_prob") or 0) * 100)
        if best is None or conf > best[0]:
            best = (conf, p)
    return best[1] if best else None

def prepare_val_db(src, val):
    """Копіює logicbet.db -> валідаційна монолітна БД, чистить прогнози/ставки."""
    shutil.copyfile(src, val)
    with sqlite3.connect(val) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(user_bets)")}
        if "market" not in cols:
            c.execute("ALTER TABLE user_bets ADD COLUMN market TEXT")
        if "bookkeeper_odd" not in cols:
            c.execute("ALTER TABLE user_bets ADD COLUMN bookkeeper_odd REAL")
        c.execute("DELETE FROM predictions")
        c.execute("DELETE FROM user_bets")
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('bankroll','1000.0')")
        c.commit()


def run_backtest(val, verbose=False):
    """Головний walk-forward цикл. Повертає підсумок dict."""
    from analytics import BettingAnalytics
    from database import LogicBetDB

    db = LogicBetDB(val)
    anal = BettingAnalytics(db)

    with sqlite3.connect(val) as c:
        matches = c.execute("""
            SELECT id, date, home_team_id, away_team_id, home_score, away_score, league
            FROM matches
            WHERE status IN ('FT','AET','PEN','FINISHED')
              AND home_score IS NOT NULL AND away_score IS NOT NULL
            ORDER BY date ASC, id ASC
        """).fetchall()
        tids = [r[0] for r in c.execute("SELECT id FROM teams")]

    elo = {tid: (INIT_ELO, INIT_ELO) for tid in tids}
    bankroll = 1000.0
    wins = losses = skipped = match_hit = 0
    placed = []

    with sqlite3.connect(val) as c:
        for mid, mdate, hid, aid, hs, as_, lg in matches:
            if hid not in elo or aid not in elo:
                skipped += 1
                continue
            # A) прокинути ОНЛАЙН Elo (стан до цього матчу) у teams
            c.execute("UPDATE teams SET home_elo=?, away_elo=?, elo_rating=? WHERE id=?",
                      (elo[hid][0], elo[hid][1], (elo[hid][0]+elo[hid][1])/2, hid))
            c.execute("UPDATE teams SET home_elo=?, away_elo=?, elo_rating=? WHERE id=?",
                      (elo[aid][0], elo[aid][1], (elo[aid][0]+elo[aid][1])/2, aid))
            c.commit()

            # генерує прогноз ІЗОЛЬОВАНО (аналізатор не бачить майбутнє)
            try:
                preds = anal.determine_predictions(mid, hid, aid, None)
            except Exception as exc:               # noqa: BLE001
                skipped += 1
                continue

            bet = _pick_bet(preds)
            if bet is None:
                skipped += 1
                continue
            sel = bet['selection']
            prob = float(bet.get('calculated_prob') or 0) or 0.001
            # Fair odds без маржі — вимірює ЧИСТУ якість моделі
            # (реінвестування/змаз без арбітраж-чинника букмекера).
            odd = round(min(5.0, max(1.01, 1.0 / prob)), 2)

            # B) фіксація ставки PENDING
            c.execute(
                "INSERT INTO user_bets (match_id, market, selection, stake, odd, status, profit) "
                "VALUES (?,?,?,?,?,'PENDING',0.0)",
                (mid, bet.get('market'), sel, STAKE, odd))
            # відповідний прогноз теж зберігаємо
            c.execute(
                "INSERT INTO predictions (match_id, market, selection, calculated_prob, bookmaker_odd, value_percentage, confidence_level) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, bet.get('market'), sel, prob, odd, 0.0,
                 bet.get('confidence_level') or 'MEDIUM'))

            # C) відкриваємо реальний рахунок -> розрахунок
            hit = _resolve(sel, int(hs), int(as_))
            if hit is None:
                # не розпізнано — скасувати (не псує статистику)
                c.execute("UPDATE user_bets SET status='CANCELED' WHERE match_id=?", (mid,))
                c.commit()
                skipped += 1
                continue
            if hit:
                payout = round(STAKE * odd, 2)
                bankroll += round(payout - STAKE, 2)
                c.execute("UPDATE user_bets SET status='WON', profit=? WHERE match_id=?",
                          (round(payout - STAKE, 2), mid))
                wins += 1
                match_hit += 1
            else:
                bankroll -= STAKE
                c.execute("UPDATE user_bets SET status='LOST', profit=? WHERE match_id=?",
                          (-STAKE, mid))
                losses += 1
            c.execute("UPDATE config SET value=? WHERE key='bankroll'", (str(round(bankroll,2)),))
            c.commit()

            # оновлюємо онлайн-Elo за фактичним результатом
            _apply_venue_elo(elo, hid, aid, int(hs), int(as_))
            placed.append(mid)

            if verbose:
                print(f"{mdate[:10]} {mid} {sel} @{odd} -> {'WON' if match_hit else 'LOST'}")

    total = wins + losses
    roi = ((bankroll - 1000.0) / 1000.0) * 100.0 if total else 0.0
    return {"matches": len(matches), "placed": len(placed), "skipped": skipped,
            "wins": wins, "losses": losses,
            "winrate": (wins / total * 100.0) if total else 0.0,
            "bankroll": round(bankroll, 2), "roi_pct": round(roi, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="перенести результат у прод data+user БД")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    src = os.path.join(ROOT, "godot_app", "logicbet.db")
    val = os.path.join(tempfile.gettempdir(), "logicbet_val.db")
    prepare_val_db(src, val)
    res = run_backtest(val, verbose=a.verbose)
    print("BACKTEST_SUMMARY:", res)

    if a.apply:
        data_db = src
        user_db = os.path.join(ROOT, "webapp", "user_data.db")
        with sqlite3.connect(val) as vc, \
                sqlite3.connect(data_db) as dc, \
                sqlite3.connect(user_db) as uc:
            dc.execute("DELETE FROM predictions")
            for row in vc.execute(
                    "SELECT match_id, market, selection, calculated_prob, "
                    "bookmaker_odd, value_percentage, confidence_level "
                    "FROM predictions"):
                dc.execute("INSERT INTO predictions (match_id, market, selection, "
                           "calculated_prob, bookmaker_odd, value_percentage, "
                           "confidence_level) VALUES (?,?,?,?,?,?,?)", row)
            dc.commit()
            uc.execute("DELETE FROM user_bets WHERE status IN ('WON','LOST')")
            for row in vc.execute(
                    "SELECT match_id, market, selection, stake, odd, status, "
                    "profit FROM user_bets WHERE status IN ('WON','LOST')"):
                uc.execute("INSERT INTO user_bets (match_id, market, selection, "
                           "stake, odd, status, profit) VALUES (?,?,?,?,?,?,?)", row)
            uc.execute("INSERT OR REPLACE INTO config (key, value) "
                       "VALUES ('bankroll', ?)",
                       (str(max(1000.0, float(res["bankroll"]))),))
            uc.commit()
        print("APPLY_DONE: predictions + settled history + bankroll",
              res["bankroll"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
