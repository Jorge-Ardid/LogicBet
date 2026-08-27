# -*- coding: utf-8 -*-
"""Smoke test v27: модуль конкуренції стратегій у вебзастосунку.

Перевіряє:
  1. GET /api/matches -> 200 і Ensemble Consensus (outcomes/totals/btts)
     на картці матчу після автоматичного циклу арени (settle -> stats ->
     generate) прямо при читанні матчів.
  2. Тротлінг run_cycle: повторний запит не падає, консенсус на місці.
  3. GET /api/strategies -> 200, 30 скриптів по 3 секторах + top3, сортування
     за ROI.
"""
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
TMP = tempfile.mkdtemp(prefix="logicbet_smoke_v27_")
DATA_DB = os.path.join(TMP, "logicbet.db")
USER_DB = os.path.join(TMP, "user_data.db")

# ---------- 1. Готуємо БД ДАННИХ з майбутнім матчем ----------
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
INSERT INTO teams (id, name, elo_rating) VALUES (1, 'Shakhtar', 1720.0),
                                                (2, 'Dynamo', 1660.0),
                                                (3, 'Zorya', 1600.0),
                                                (4, 'Kolos', 1580.0);
-- Історія з голами (FT) — форма/H2H для стратегій тоталів і БТТС
INSERT INTO matches (id, date, league, status, home_score, away_score,
                     ht_score_h, ht_score_a, home_team_id, away_team_id) VALUES
  (101, strftime('%Y-%m-%d 18:00', 'now', '-7 day'), 'UPL', 'FT', 2, 1, 1, 0, 1, 2),
  (102, strftime('%Y-%m-%d 18:00', 'now', '-6 day'), 'UPL', 'FT', 1, 1, 0, 1, 2, 1),
  (103, strftime('%Y-%m-%d 18:00', 'now', '-5 day'), 'UPL', 'FT', 3, 0, 2, 0, 1, 3),
  (104, strftime('%Y-%m-%d 18:00', 'now', '-4 day'), 'UPL', 'FT', 0, 2, 0, 1, 4, 2),
  (105, strftime('%Y-%m-%d 18:00', 'now', '-3 day'), 'UPL', 'FT', 2, 2, 1, 1, 3, 1),
  (106, strftime('%Y-%m-%d 18:00', 'now', '-2 day'), 'UPL', 'FT', 1, 2, 0, 1, 2, 4),
  (107, strftime('%Y-%m-%d 18:00', 'now', '-1 day'), 'UPL', 'FT', 2, 0, 1, 0, 4, 1),
  (108, strftime('%Y-%m-%d 18:00', 'now', '-7 day'), 'UPL', 'FT', 1, 3, 0, 2, 3, 4),
  (109, strftime('%Y-%m-%d 18:00', 'now', '-6 day'), 'UPL', 'FT', 2, 1, 1, 0, 4, 3);
-- матч на завтра (NS) — у вікні генерації тіней і на сторінці «Завтра»
INSERT INTO matches (id, date, league, status, home_team_id, away_team_id) VALUES
  (201, strftime('%Y-%m-%d 18:00', 'now', '+1 day'), 'UPL', 'NS', 1, 2);
INSERT INTO predictions (match_id, market, selection, calculated_prob,
                         bookmaker_odd, confidence_level) VALUES
  (201, '1X2', 'П1', 0.55, 1.85, 'HIGH'),
  (201, 'Totals 2.5', 'Більше 2.5', 0.53, 1.90, 'MEDIUM'),
  (201, 'BTTS', 'ОЗ - Так', 0.51, 1.80, 'MEDIUM');
INSERT INTO config (key, value) VALUES ('bankroll', '1000.0'),
                                       ('default_stake', '10.0');
""")
con.commit()
con.close()

# ---------- 2. Імпорт вебзастосунку на тимчасових БД ----------
os.environ["LOGICBET_DB_PATH"] = USER_DB
os.environ["LOGICBET_DATA_DB"] = DATA_DB
sys.path.insert(0, os.path.join(BASE, "webapp"))
sys.path.insert(0, os.path.join(BASE, "python"))
import app as webapp  # noqa: E402

client = webapp.app.test_client()
FAILS = []


def check(name, cond, extra=""):
    print(("OK  " if cond else "FAIL") + " " + name
          + ((" | " + str(extra)) if extra else ""))
    if not cond:
        FAILS.append(name)


# ---------- 3. /api/matches: консенсус ТОП-3 ----------
r1 = client.get("/api/matches")
check("GET /api/matches -> 200", r1.status_code == 200, r1.status_code)
j1 = r1.get_json()
ms = [m for g in j1.get("groups", []) for m in g.get("matches", [])]
m201 = next((m for m in ms if m.get("id") == 201), None)
check("матч 201 у видачі /api/matches", m201 is not None)
ens = (m201 or {}).get("ensemble") or {}
check("ensemble на картці матчу", bool(ens), sorted(ens.keys()))
for sector in ("outcomes", "totals", "btts"):
    e = ens.get(sector) or {}
    check("ensemble.%s: pick+prob+votes" % sector,
          bool(e.get("pick")) and float(e.get("prob") or 0) > 0
          and bool(e.get("votes")),
          "%s | %s | %s" % (e.get("pick"), e.get("prob"), e.get("votes")))

# ---------- 4. Тротлінг: повторний запит — консенсус на місці ----------
r2 = client.get("/api/matches")
check("GET /api/matches (2-й, тротлінг) -> 200", r2.status_code == 200)
ms2 = [m for g in r2.get_json().get("groups", [])
       for m in g.get("matches", [])]
m201b = next((m for m in ms2 if m.get("id") == 201), None)
check("ensemble жив і після тротлінгу",
      bool((m201b or {}).get("ensemble")))

# ---------- 5. /api/strategies: таблиця конкуренції ----------
r3 = client.get("/api/strategies")
check("GET /api/strategies -> 200", r3.status_code == 200, r3.status_code)
j3 = r3.get_json()
sectors = j3.get("sectors", {})
n_strats = sum(len(v) for v in sectors.values())
check("30 скриптів у статистиці", n_strats == 30, n_strats)
top3 = j3.get("top3", {})
check("top3 по 3 секторах",
      all(len(top3.get(s) or []) == 3 for s in ("outcomes", "totals", "btts")),
      top3)
rows_o = sectors.get("outcomes") or []
if len(rows_o) >= 2:
    check("сортування сектора за ROI (desc)",
          rows_o[0]["roi_pct"] >= rows_o[1]["roi_pct"],
          "%s=%.2f >= %s=%.2f" % (rows_o[0]["strategy"], rows_o[0]["roi_pct"],
                                  rows_o[1]["strategy"], rows_o[1]["roi_pct"]))

print()
if FAILS:
    print("FAILED: " + ", ".join(FAILS))
    sys.exit(1)
print("ALL V27 API SMOKE CHECKS PASSED")
