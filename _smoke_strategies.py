# -*- coding: utf-8 -*-
"""Smoke test v27: модуль конкуренції прогнозних стратегій (shadow-bets).
Перевіряє: 1) 30 скрипти + інтерфейс; 2) генерація тіней; 3) сетлмент +
математика; 4) stats / top3 / snapshot / ensemble; 5) холодний старт."""
import contextlib
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "python"))
TMP = tempfile.mkdtemp(prefix="logicbet_smoke_strat_")


class FakeDB:
    def __init__(self, path):
        self.path = path
        self._conn = sqlite3.connect(path)

    @contextlib.contextmanager
    def get_connection(self):
        yield self._conn


def build_db(db_path):
    con = FakeDB(db_path)
    con._conn.executescript("""
        CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, elo_rating REAL);
        CREATE TABLE matches (id INTEGER PRIMARY KEY, remote_id INTEGER UNIQUE,
            date TEXT, league TEXT, home_team_id INTEGER, away_team_id INTEGER,
            home_score INTEGER, away_score INTEGER, ht_score_h INTEGER,
            ht_score_a INTEGER, status TEXT, finished_at TEXT);
        CREATE TABLE predictions (id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER, algorithm TEXT, market TEXT, selection TEXT,
            calculated_prob REAL, bookmaker_odd REAL, value_percentage REAL,
            confidence_level TEXT, is_hit INTEGER);
        CREATE TABLE odds (match_id INTEGER, market TEXT, selection TEXT,
            opening_odd REAL, closing_odd REAL);
    """)
    con._conn.executemany("INSERT INTO teams (id,name,elo_rating) VALUES (?,?,?)",
        [(1, "Shakhtar", 1700.0), (2, "Dynamo", 1680.0),
         (3, "Lens", 1580.0), (4, "Real", 1720.0)])
    finished = [(201, "2026-08-01 18:00", 1, 2, 2, 1),
                (202, "2026-08-03 18:00", 2, 1, 1, 2),
                (203, "2026-08-05 18:00", 1, 2, 0, 0),
                (204, "2026-08-07 18:00", 1, 3, 3, 1),
                (205, "2026-08-08 18:00", 3, 1, 1, 2),
                (206, "2026-08-10 18:00", 2, 4, 2, 2),
                (207, "2026-08-11 18:00", 4, 2, 2, 2)]
    for i, (rid, d, h, a, hs, as_) in enumerate(finished, start=1):
        con._conn.execute("INSERT INTO matches (id,remote_id,date,league,"
            "home_team_id,away_team_id,home_score,away_score,ht_score_h,"
            "ht_score_a,status) VALUES (?,?,?,?,?,?,?,?,?,?, 'FT')",
            (i, rid, d, "UPL", h, a, hs, as_, None, None))
    f1 = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d 19:00")
    f2 = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d 20:00")
    con._conn.execute("INSERT INTO matches (id,remote_id,date,league,home_team_id,"
        "away_team_id,home_score,away_score,ht_score_h,ht_score_a,status) "
        "VALUES (101,901,?, 'UPL',1,2,NULL,NULL,NULL,NULL,'NS')", (f1,))
    preds = [(101, "base", "1X2", "П1", 0.52), (101, "blend", "1X2", "П1", 0.54),
        (101, "base", "1X2", "X", 0.28), (101, "base", "1X2", "П2", 0.20),
        (101, "base", "TOTAL_GOALS", "ТБ 2.5", 0.55),
        (101, "base", "TOTAL_GOALS", "ТМ 2.5", 0.45),
        (101, "base", "BTTS", "ОЗ - Так", 0.51),
        (101, "base", "BTTS", "ОЗ - Ні", 0.49)]
    con._conn.executemany("INSERT INTO predictions (match_id,algorithm,market,"
        "selection,calculated_prob) VALUES (?,?,?,?,?)", preds)
    odds = [(101, "1X2", "1", 1.85), (101, "1X2", "X", 3.50), (101, "1X2", "2", 4.20),
        (101, "TOTAL_GOALS", "Over 2.5", 1.90),
        (101, "TOTAL_GOALS", "Under 2.5", 1.95),
        (101, "BTTS", "Yes", 1.85), (101, "BTTS", "No", 2.10)]
    con._conn.executemany("INSERT INTO odds (match_id,market,selection,"
        "opening_odd,closing_odd) VALUES (?,?,?,?,?)",
        [(r[0], r[1], r[2], r[3], r[3]) for r in odds])
    con._conn.commit()
    return con, f1, f2

import strategy_evaluator as se  # noqa: E402

# 1. інтерфейси 30 скриптів
strats = se.load_strategies()
total = sum(len(v) for v in strats.values())
assert total == 30, "expected 30 strategies, got %d" % total
for sec, mods in strats.items():
    for m in mods:
        assert m.SECTOR == sec and hasattr(m, "predict") and m.ID
print("[1] 30 strategies OK; sectors:", sorted(strats))

# 2. генерація тіней по майбутньому матчу 101
db, f1, f2 = build_db(os.path.join(TMP, "t1.db"))
g = se.generate_shadow_bets(db)
assert g["matches"] == 1 and 0 < g["inserted"] <= 30, g
with db.get_connection() as c:
    cnt = c.execute("SELECT COUNT(*) FROM strategy_shadow_bets").fetchone()[0]
    dups = c.execute("SELECT strategy, COUNT(*) FROM strategy_shadow_bets "
                     "GROUP BY strategy HAVING COUNT(*)>1").fetchall()
assert cnt == g["inserted"] and not dups, (cnt, dups)
print("[2] generate:", g)

# 3. сетлмент матч 101 = 2:1 (дома 1 переміг, тотал 3, обидві заб)
with db.get_connection() as c:
    c.execute("UPDATE matches SET status='FT', home_score=2, away_score=1 "
              "WHERE id=101 AND status='NS'")
    c.commit()
st = se.settle_shadow_bets(db)
assert st["settled"] == g["inserted"], st
with db.get_connection() as c:
    sample = c.execute("SELECT sector,selection,odd,stake,profit "
                       "FROM strategy_shadow_bets WHERE match_id=101").fetchall()
won = sum(1 for r in sample if r[4] > 0)
los = sum(1 for r in sample if r[4] <= 0 and r[3] is not None)
assert won >= 1 and los >= 1, (won, los, sample[:3])
for sec, sel, odd, stake, profit in sample:
    if profit > 0:
        assert abs(profit - stake * (odd - 1)) < 0.01, (sec, sel, profit, stake, odd)
    elif sel is not None:
        assert abs(profit + stake) < 0.01, (sec, sel, profit, stake)
print("[3] settle math OK: won=%d lost=%d rows=%d" % (won, los, len(sample)))

# 4. статистика, snapshot, топ-3 по 3 секторах
stats = se.get_stats(db)
# v27: у статистиці завжди всі 30 скриптів (утриманці — з нульовими статами)
assert len(stats) == 30, ("stats rows", len(stats))
assert len([r for r in stats if r["settled"]]) == g["inserted"], \
    ("settled strategies", len([r for r in stats if r["settled"]]),
     g["inserted"])
for r in stats:
    for key in ("sector", "strategy", "roi_pct", "winrate_pct", "bank", "settled"):
        assert key in r, r
snap = se.snapshot_stats(db)
assert snap["snapshot"] == len(stats), (snap["snapshot"], len(stats))
top = {s: se.top_strategies(db, s, 3) for s in ("outcomes", "totals", "btts")}
for s, t in top.items():
    assert len(t) == 3, (s, t)
print("[4] stats=%d, snapshot=%d, top3=%s" % (len(stats), snap["snapshot"], top))

# 5. консенсус для майбутнього матчу 102
with db.get_connection() as c:
    c.execute("INSERT INTO matches (id,remote_id,date,league,home_team_id,"
              "away_team_id,home_score,away_score,ht_score_h,ht_score_a,status) "
              "VALUES (102,902,?, 'UPL',2,1,NULL,NULL,NULL,NULL,'NS')", (f2,))
    c.commit()
se.generate_shadow_bets(db)
ens = se.ensemble_consensus(db, [102])
assert 102 in ens and set(ens[102]) <= {"outcomes", "totals", "btts"}, ens
for sec, e in ens[102].items():
    assert e["pick"] in ("П1", "X", "П2", "ТБ 2.5", "ТМ 2.5", "ОЗ - Так", "ОЗ - Ні"), e
    assert 0.0 <= e["prob"] <= 1.0 and "/" in e["votes"], e
# при 2:1 (дома 1): ТБ 2.5 (тотал 3) та ОЗ — Так (обидві заб)
assert ens[102]["totals"]["pick"] == "ТБ 2.5", ens[102]["totals"]
assert ens[102]["btts"]["pick"] == "ОЗ - Так", ens[102]["btts"]
print("[5] ensemble[102]:", {k: (v["pick"], v["prob"], v["votes"])
                             for k, v in ens[102].items()})

# 6. холодний старт: без майбутніх матчів -> 0 тіней, порожній консенсус
db2 = FakeDB(os.path.join(TMP, "empty.db"))
db2._conn.executescript("CREATE TABLE teams(id INTEGER PRIMARY KEY, name TEXT,"
    "elo_rating REAL); CREATE TABLE matches(id INTEGER PRIMARY KEY, remote_id "
    "INTEGER UNIQUE, date TEXT, league TEXT, home_team_id INTEGER, "
    "away_team_id INTEGER, home_score INTEGER, away_score INTEGER, "
    "ht_score_h INTEGER, ht_score_a INTEGER, status TEXT, finished_at TEXT); "
    "CREATE TABLE predictions(id INTEGER PRIMARY KEY AUTOINCREMENT, match_id "
    "INTEGER, algorithm TEXT, market TEXT, selection TEXT, calculated_prob REAL, "
    "bookmaker_odd REAL, value_percentage REAL, confidence_level TEXT, is_hit "
    "INTEGER); CREATE TABLE odds(match_id INTEGER, market TEXT, selection TEXT, "
    "opening_odd REAL, closing_odd REAL);")
g2 = se.generate_shadow_bets(db2)
assert g2["matches"] == 0 and g2["inserted"] == 0, g2
assert se.ensemble_consensus(db2, [101]) == {}
print("[6] cold start OK")

print("\nALL STRATEGY SMOKE CHECKS PASSED (30 strategies, shadow bets, "
      "settle, ROI/stats, ensemble).")

