# -*- coding: utf-8 -*-
"""Smoke test v26: миттєве списання балансу при оформленні ставки.

Перевіряє:
  1. Одноразову міграцію легасі PENDING-ставок (списання з банкролу).
  2. POST /api/place_bet (новий ендпоінт-аліас) з повним payload
     {match_id, market, selection, odds, stake} -> списання 10 грн + COMMIT.
  3. Повторний вибір на той самий матч -> Update БЕЗ повторного списання.
  4. Легасі-аліас POST /api/bets працює.
  5. Недостатньо коштів -> 400.
  6. DELETE повертає заморожені кошти на баланс.
  7. Сетлмент v26: LOST не списує стейк вдруге, WON нараховує повну виплату.
  8. /api/matches віддає bet_selection/bet_stake для підсвітки на картці.
"""
import json
import os
import sqlite3
import sys
import tempfile

# Windows-консоль (cp1251/cp866) ламається на українському тексті у print
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="logicbet_smoke_v26_")
DATA_DB = os.path.join(TMP, "logicbet.db")
USER_DB = os.path.join(TMP, "user_data.db")

# ---------- 1. Готуємо БД ДАНИХ (Godot) з легасі-ставкою ----------
con = sqlite3.connect(DATA_DB)
con.executescript("""
CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, elo_rating REAL);
CREATE TABLE matches (id INTEGER PRIMARY KEY, date TEXT, league TEXT, status TEXT,
  home_score REAL, away_score REAL, ht_score_h REAL, ht_score_a REAL,
  home_team_id INTEGER, away_team_id INTEGER);
CREATE TABLE predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER,
  algorithm TEXT, market TEXT, selection TEXT, calculated_prob REAL,
  bookmaker_odd REAL, value_percentage REAL, confidence_level TEXT,
  is_hit INTEGER);
CREATE TABLE odds (match_id INTEGER, bookmaker TEXT, market TEXT,
  selection TEXT, odd REAL);
CREATE TABLE team_synonyms (synonym TEXT, canonical TEXT);
CREATE TABLE user_bets (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER,
  selection TEXT, stake REAL, odd REAL, status TEXT, profit REAL);
CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
INSERT INTO teams (id, name, elo_rating) VALUES (1, 'Shakhtar', 1700.0),
                                                (2, 'Dynamo', 1680.0);
INSERT INTO matches (id, date, league, status, home_team_id, away_team_id) VALUES
  (101, '2026-08-28 19:00', 'UPL', 'NS', 1, 2),
  (102, '2026-08-28 21:00', 'UPL', 'NS', 2, 1),
  (103, '2026-08-29 18:00', 'UPL', 'NS', 1, 2),
  (104, '2026-08-29 20:00', 'UPL', 'NS', 2, 1);
INSERT INTO predictions (match_id, market, selection, calculated_prob,
                         bookmaker_odd, confidence_level) VALUES
  (101, '1X2', 'П1', 0.55, 1.85, 'HIGH'),
  (101, 'BTTS', 'ОЗ - Так', 0.51, 1.90, 'MEDIUM'),
  (103, '1X2', 'П1', 0.60, 2.00, 'HIGH');
INSERT INTO config (key, value) VALUES ('bankroll', '1000.0'),
                                       ('default_stake', '10.0');
-- легасі PENDING ставка ДО v26: стейк ще НЕ списаний з банку
INSERT INTO user_bets (match_id, selection, stake, odd, status, profit)
  VALUES (102, 'П2', 10.0, 2.05, 'PENDING', 0.0);
""")
con.commit()

# ---------- 2. Імпорт вебзастосунку на тимчасових БД ----------
os.environ["LOGICBET_DB_PATH"] = USER_DB
os.environ["LOGICBET_DATA_DB"] = DATA_DB
sys.path.insert(0, os.path.join(BASE, "webapp"))
import app as webapp  # noqa: E402

client = webapp.app.test_client()
FAILS = []


def check(name, cond, extra=""):
    tag = "OK " if cond else "FAIL"
    print(f"[{tag}] {name} {extra}")
    if not cond:
        FAILS.append(name)


def balance():
    return client.get("/api/state").get_json()["balance_total"]


# ---------- 3. Міграція легасі PENDING ----------
check("migration: legacy pending deducted", abs(balance() - 990.0) < 0.01,
      f"balance={balance()}")

# ---------- 4. Нова ставка: миттєве списання 10 грн ----------
r = client.post("/api/place_bet", data=json.dumps(
    {"match_id": 101, "market": "1X2", "selection": "П1",
     "odds": 1.85, "stake": 10.0}), content_type="application/json")
j = r.get_json()
check("place_bet 201", r.status_code == 201, str(j))
check("place_bet new_balance 980", j.get("new_balance") == 980.0,
      f"got {j.get('new_balance')}")
check("place_bet success field", j.get("success") is True)
bet_101 = j.get("id")

# ---------- 5. Зміна варіанту на ТОМУ САМОМУ матчі: без другого списання ----------
r = client.post("/api/place_bet", data=json.dumps(
    {"match_id": 101, "market": "1X2", "selection": "X2",
     "odds": 3.40, "stake": 10.0}), content_type="application/json")
j = r.get_json()
check("reselect 200 + updated", r.status_code == 200 and j.get("updated") is True)
check("reselect: NO double deduction", j.get("new_balance") == 980.0,
      f"got {j.get('new_balance')}")
con = sqlite3.connect(USER_DB)
row = con.execute(
    "SELECT COUNT(*), selection, stake, odd, market FROM user_bets "
    "WHERE match_id=101 AND status='PENDING'").fetchone()
con.close()
check("reselect: single row", row[0] == 1, str(row))
check("reselect: selection/odd/market updated, stake kept",
      row[1] == "X2" and row[2] == 10.0 and row[3] == 3.40 and row[4] == "1X2",
      str(row))

# ---------- 6. Легасі-аліас /api/bets (оновлення легасі-ставки 102) ----------
r = client.post("/api/bets", data=json.dumps(
    {"match_id": 102, "market": "1X2", "selection": "П2",
     "odds": 2.05, "stake": 10.0}), content_type="application/json")
j = r.get_json()
check("legacy alias /api/bets ok", r.status_code == 200 and j.get("ok") is True)
check("legacy alias: no re-deduction", balance() == 980.0,
      f"balance={balance()}")

con.close()


# ---------- 7. Нова ставка на 103 + недостатньо коштів на 104 ----------
r = client.post("/api/place_bet", data=json.dumps(
    {"match_id": 103, "market": "1X2", "selection": "П1",
     "odds": 2.00, "stake": 10.0}), content_type="application/json")
j = r.get_json()
bet_103 = j.get("id")
check("bet 103 placed", r.status_code == 201 and j.get("new_balance") == 970.0,
      f"balance={j.get('new_balance')}")
r = client.post("/api/place_bet", data=json.dumps(
    {"match_id": 104, "market": "1X2", "selection": "П2",
     "odds": 1.50, "stake": 5000.0}), content_type="application/json")
check("insufficient funds -> 400", r.status_code == 400, str(r.get_json()))
check("balance unchanged after 400", balance() == 970.0,
      f"balance={balance()}")

# ---------- 8. DELETE: повернення коштів ----------
r = client.delete(f"/api/bets/{bet_103}")
j = r.get_json()
check("delete refund", r.status_code == 200 and j.get("new_balance") == 980.0,
      str(j))

# ---------- 9. Картка матчів: bet_selection/bet_stake для підсвітки ----------
groups = client.get("/api/matches?filter=all").get_json()["groups"]
flat = [m for g in groups for m in g["matches"]]
m102 = next(m for m in flat if m["id"] == 102)
check("match card: has_bet + bet_selection + bet_stake",
      m102["has_bet"] is True and m102["bet_selection"] == "П2"
      and m102["bet_stake"] == 10.0 and m102["bet_odd"] == 2.05,
      str({k: m102[k] for k in ("has_bet", "bet_selection", "bet_stake", "bet_odd")}))

# ---------- 10. Сторінка ставки рендериться ----------
rr = client.get("/bet/101")
check("bet page 200", rr.status_code == 200)

# ---------- 11. Сетлмент v26: LOST без другого списання, WON = повна виплата ----------
# Ізолюємо сетлмент від зовнішніх сервісів (FD API, b365, Elo, статистика)
webapp.fetch_finished_scores_from_fd = lambda: None
webapp.maybe_refresh_recent_stats = lambda force=False: None
webapp.maybe_sync_bet365_odds = lambda: None
webapp.full_elo_recalc = lambda: None
webapp.recalc_team_elo_form = lambda: None
webapp.settle_ai_predictions = lambda: {"settled": 0}
con = sqlite3.connect(DATA_DB)
con.execute("UPDATE matches SET status='FT', home_score=2, away_score=1 WHERE id=101")
con.execute("UPDATE matches SET status='FT', home_score=0, away_score=1 WHERE id=102")
con.commit()
con.close()
res = webapp.settle_pending_bets()
check("settle ran", res.get("settled") == 2, str(res))
# LOST не змінює банкрол (стейк списаний при ставці), WON додає повну виплату:
# 980 (до сетлменту) + 10*2.05 (WON) + 0 (LOST) = 1000.5
check("settle math: LOST no double deduction + WON full payout",
      abs(balance() - 1000.5) < 0.01, f"balance={balance()}")
con = sqlite3.connect(USER_DB)
rows = con.execute(
    "SELECT match_id, status, profit FROM user_bets ORDER BY match_id").fetchall()
con.close()
st = {m: (s, p) for m, s, p in rows}
check("bet 101 LOST profit -10", st[101] == ("LOST", -10.0), str(st))
check("bet 102 WON profit +10.5", st[102] == ("WON", 10.5), str(st))

# ---------- Підсумок ----------
print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL SMOKE TESTS PASSED - db:", USER_DB)
