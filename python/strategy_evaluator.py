# -*- coding: utf-8 -*-
"""Модуль конкуренції та еволюції прогнозних моделей (logicbet v27).

Виконує три ролі:

1. **Генерація віртуальних ставок** — проганяє всі 10 скриптів кожного
   з трьох секторів (``outcomes``/``totals``/``btts``, файли
   ``python/strategies/<sector>/v1.py … v10.py``) по майбутнім матчам і
   зберігає їхні прогнози в таблицю ``strategy_shadow_bets`` фіксованим
   стейком.
2. **Сетлмент** — після авто-розрахунку закритих матчів (викликається з
   ``settle_pending_bets()`` у ``app.py``) підраховує ROI, Winrate та
   підсумковий банк для кожного з 10 скриптів і знімає снапшот у
   ``strategy_stats``.
3. **Ensemble Consensus** — для ``/api/matches`` формує «головний прогноз»
   на основі консенсусу ТОП-3 найкращих скриптів сектора (за ROI).

Сам модуль автономний (stdlib + ``strategies``).
"""
from __future__ import annotations

import importlib
import math
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from strategies import SECTORS  # noqa: E402

# --- Параметри конкурентної арени ----------------------------------------
SHADOW_STAKE = 10.0          # віртуальний стейк однієї тіні
SHADOW_START_BANK = 1000.0   # початковий банк кожного скрипта
LOOKAHEAD_DAYS = 10          # вікно майбутніх матчів
FORM_GAMES = 8               # останні ігри у формі
FORM_GAMES_SHORT = 4         # ще і для "гарячої" форми (v7 totals)
H2H_LIMIT = 5                # історичні H2H‑матчі
MIN_SETTLED_FOR_RANK = 3     # мін. замкнутих трофіїв для входу в ТОП
_MARGIN = 0.95               # маржа «букмекера» у синтетичних коефіцієнтах
_FINISHED_STATUSES = ("FT", "AET", "PEN", "FINISHED")
_CYCLE_THROTTLE_SEC = 60.0   # run_cycle з API-шляхів — не частіше 1 раз/хв
_last_cycle_ts = 0.0


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategy_shadow_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector TEXT            NOT NULL,
            strategy TEXT          NOT NULL,
            match_id INTEGER       NOT NULL,
            market TEXT,
            selection TEXT,
            odd REAL,
            prob REAL,
            stake REAL DEFAULT %f,
            status TEXT DEFAULT 'PENDING',
            profit REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(strategy, match_id)
        )
    """ % SHADOW_STAKE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategy_stats (
            sector TEXT NOT NULL, strategy TEXT NOT NULL,
            settled INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
            winrate_pct REAL, staked REAL, profit REAL,
            roi_pct REAL, bank REAL, pending INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (sector, strategy)
        )
    """)
    conn.commit()


# ===========================================================================
#  Динамічне завантаження 10 скриптів кожного сектора.
# ===========================================================================
def load_strategies():
    """Повертає {sector: [module, …]} впорядкованих за ID (v1..v10)."""
    out = {}
    for sector in SECTORS:
        modules = []
        for i in range(1, 11):
            try:
                mod = importlib.import_module("strategies.%s.v%d" % (sector, i))
            except Exception as exc:  # один зламаний скрипт не зупиняє арену
                print("[STRAT] failed to import strategies.%s.v%d: %s"
                      % (sector, i, exc))
                continue
            if not (hasattr(mod, "predict") and hasattr(mod, "SECTOR")
                    and hasattr(mod, "ID")):
                print("[STRAT] strategies.%s.v%d: пропущено інтерфейс" % (sector, i))
                continue
            modules.append(mod)
        modules.sort(key=lambda m: m.ID)
        out[sector] = modules
    return out


# ===========================================================================
#  Побудова контексту матчу з БД (форма, Elo, AI, коефіцієнти).
# ===========================================================================
def _norm_selection(market, sel):
    """Букмекерські/АI назви варіантів → канонічні назви logicbet."""
    s = str(sel).upper()
    if market == "1X2":
        if s in ("1", "HOME", "П1") or "ДОМ" in s:
            return "П1"
        if s in ("2", "AWAY", "П2") or "ВИ" in s:
            return "П2"
        if s in ("X", "DRAW", "Н"):
            return "X"
        return None
    if market in ("TOTAL_GOALS", "TOTAL", "U2.5"):
        if "OVER" in s or "ТБ" in s:
            return "ТБ 2.5"
        if "UNDER" in s or "ТМ" in s:
            return "ТМ 2.5"
        return None
    if market in ("BTTS", "BOTH"):
        if s == "YES" or "ТАК" in s:
            return "ОЗ - Так"
        if s == "NO" or "НІ" in s or "NI" in s:
            return "ОЗ - Ні"
        return None
    return None


def _form_map(conn, team_ids):
    """{team_id: {gf,ga,ppg,cs,n}} за останні FORM_GAMES завершених матчів."""
    ids = ",".join("?" * len(team_ids)) if team_ids else "NULL"
    rows = conn.execute(
        """SELECT team_id, home_score, away_score, pts FROM (
              SELECT home_team_id AS team_id, home_score, away_score,
                     home_score - away_score AS pts, date
              FROM matches WHERE status IN (%s) AND home_score IS NOT NULL
                AND home_team_id IN (%s)
              UNION ALL
              SELECT away_team_id AS team_id, away_score, home_score,
                     away_score - home_score AS pts, date
              FROM matches WHERE status IN (%s) AND home_score IS NOT NULL
                AND away_team_id IN (%s)
          ) t ORDER BY date DESC"""
        % (",".join("?" * len(_FINISHED_STATUSES)), ids,
           ",".join("?" * len(_FINISHED_STATUSES)), ids),
        list(_FINISHED_STATUSES) + list(team_ids)
        + list(_FINISHED_STATUSES) + list(team_ids)).fetchall()
    agg = {tid: {"gf": 0.0, "ga": 0.0, "pts": 0.0, "cs": 0, "n": 0}
           for tid in team_ids}
    counts = {tid: 0 for tid in team_ids}
    seen = {tid: 0 for tid in team_ids}
    for tid, hs, as_, pts in rows:
        if tid not in agg or seen[tid] >= FORM_GAMES:
            continue
        seen[tid] += 1
        agg[tid]["gf"] += (hs or 0)
        agg[tid]["ga"] += (as_ or 0)
        agg[tid]["pts"] += (pts or 0)
        if (hs or 0) == 0:
            agg[tid]["cs"] += 1
        agg[tid]["n"] += 1
    for tid, a in agg.items():
        if a["n"]:
            a["gf"] = round(a["gf"] / a["n"], 3)
            a["ga"] = round(a["ga"] / a["n"], 3)
            a["ppg"] = round(a["pts"] / (a["n"] * 3.0), 3) + 1.0
    return agg


def _form_short_full(conn, home_id, away_id):
    """{(home|away)_gf4, ga4, n4} за останні 4 матчі — для v7 totals."""

    def _team(tid):
        rows = conn.execute(
            """SELECT home_team_id, home_score, away_score FROM matches
               WHERE status IN (%s) AND home_score IS NOT NULL
                 AND (home_team_id=? OR away_team_id=?)"""
            % ",".join("?" * len(_FINISHED_STATUSES)),
            list(_FINISHED_STATUSES) + [tid, tid]).fetchall()
        rows = rows[:FORM_GAMES_SHORT]
        gf = ga = cs = n = 0
        for hid, hs, as_ in rows:
            hs, as_ = hs or 0, as_ or 0
            if hid == tid:          # команда грала дома
                gf += hs; ga += as_; cs += 1 if (hs == 0) else 0
            else:                   # команда грала виїздем
                gf += as_; ga += hs; cs += 1 if (as_ == 0) else 0
            n += 1
        n = len(rows)
        return {"gf": round(gf / n, 3) if n else 0.0,
                "ga": round(ga / n, 3) if n else 0.0,
                "n": n}

    return _team(home_id), _team(away_id)


def _h2h(conn, home_id, away_id):
    rows = conn.execute(
        """SELECT home_score, away_score FROM matches
           WHERE status IN (%s) AND home_score IS NOT NULL
             AND ((home_team_id=? AND away_team_id=?)
                  OR (home_team_id=? AND away_team_id=?))"""
        % ",".join("?" * len(_FINISHED_STATUSES)),
        list(_FINISHED_STATUSES) + [home_id, away_id, away_id, home_id]).fetchall()
    rows = rows[:H2H_LIMIT]
    return {"avg": round(sum((r[0] or 0) + (r[1] or 0) for r in rows) / len(rows), 3)
            if len(rows) >= 2 else None, "n": len(rows)}


def _ai_map(conn, match_ids):
    if not match_ids:
        return {}
    marks = ",".join("?" * len(match_ids))
    rows = conn.execute(
        """SELECT match_id, market, selection, AVG(calculated_prob)
           FROM predictions WHERE match_id IN (%s)
           GROUP BY match_id, market, selection""" % marks, list(match_ids)).fetchall()
    out = {mid: {"outcomes": {}, "totals": {}, "btts": {}} for mid in match_ids}
    for mid, market, sel, prob in rows:
        opt = _norm_selection(market, sel)
        if not opt:
            continue
        slot = "outcomes" if opt in ("П1", "X", "П2") \
            else "totals" if opt in ("ТБ 2.5", "ТМ 2.5") else "btts"
        out[mid][slot][opt] = prob
    return out


def _odds_map(conn, match_ids):
    if not match_ids:
        return {}
    marks = ",".join("?" * len(match_ids))
    # Пріоритет — закриті/відкриті коефіцієнти v24; на легасі-схемах
    # (без opening_odd/closing_odd) відкат на колонку odd, далі — без коеф.
    try:
        rows = conn.execute(
            """SELECT match_id, market, selection,
                      COALESCE(closing_odd, opening_odd)
               FROM odds WHERE match_id IN (%s)""" % marks,
            list(match_ids)).fetchall()
    except sqlite3.OperationalError:
        try:
            rows = conn.execute(
                "SELECT match_id, market, selection, odd "
                "FROM odds WHERE match_id IN (%s)" % marks,
                list(match_ids)).fetchall()
        except sqlite3.OperationalError:
            rows = []
    out = {mid: {} for mid in match_ids}
    for mid, market, sel, odd in rows:
        opt = _norm_selection(market, sel)
        if opt and odd:
            out[mid][opt] = out[mid].get(opt) or float(odd)
    return out


def _build_context(conn, row):
    mid = row[0]
    home_id, away_id = row[8], row[9]
    h_elo, a_elo = row[10] or 1500.0, row[11] or 1500.0
    form = _form_map(conn, [home_id, away_id])
    hf, af = form.get(home_id), form.get(away_id)
    h4, a4 = _form_short_full(conn, home_id, away_id)
    h2h = _h2h(conn, home_id, away_id)
    return {
        "match_id": mid, "date": row[1], "league": row[2],
        "home": row[6], "away": row[7], "home_id": home_id, "away_id": away_id,
        "home_elo": h_elo, "away_elo": a_elo,
        "home_gf": (hf or {}).get("gf", 0.0), "home_ga": (hf or {}).get("ga", 0.0),
        "home_ppg": (hf or {}).get("ppg", 0.0),
        "home_cs": (hf or {}).get("cs", 0), "home_n": (hf or {}).get("n", 0),
        "away_gf": (af or {}).get("gf", 0.0), "away_ga": (af or {}).get("ga", 0.0),
        "away_ppg": (af or {}).get("ppg", 0.0),
        "away_cs": (af or {}).get("cs", 0), "away_n": (af or {}).get("n", 0),
        "home_gf4": h4["gf"], "home_ga4": h4["ga"], "home_n4": h4["n"],
        "away_gf4": a4["gf"], "away_ga4": a4["ga"], "away_n4": a4["n"],
        "h2h_n": h2h["n"], "h2h_avg_goals": h2h["avg"],
        "ai": {"outcomes": {}, "totals": {}, "btts": {}},
        "odds": {},
    }


_UPCOMING_SQL = """
    SELECT m.id, m.date, m.league, m.status,
           m.home_score, m.away_score,
           t1.name AS home, t2.name AS away,
           m.home_team_id, m.away_team_id,
           t1.elo_rating, t2.elo_rating
    FROM matches m
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    WHERE m.status = 'NS' AND m.date IS NOT NULL
      AND m.date BETWEEN ? AND ?
      AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL
    ORDER BY m.date
"""


# ===========================================================================
#  1. Генерація віртуальних ставок по майбутнім матчам.
# ===========================================================================
def generate_shadow_bets(db, lookahead_days=LOOKAHEAD_DAYS):
    """Запускає всі стратегії по майбутнім матчам -> strategy_shadow_bets."""
    now = datetime.utcnow()
    now_s = now.strftime("%Y-%m-%d %H:%M")
    end_s = (now + timedelta(days=lookahead_days)).strftime("%Y-%m-%d %H:%M")
    strategies = load_strategies()
    inserted = 0
    with db.get_connection() as conn:
        _ensure_tables(conn)
        rows = conn.execute(_UPCOMING_SQL, (now_s, end_s)).fetchall()
        ai_all = _ai_map(conn, [r[0] for r in rows])
        odds_all = _odds_map(conn, [r[0] for r in rows])
        for row in rows:
            mid = row[0]
            ctx = _build_context(conn, row)
            ctx["ai"] = ai_all.get(mid, ctx["ai"])
            ctx["odds"] = odds_all.get(mid, ctx["odds"])
            for sector, mods in strategies.items():
                options = SECTORS[sector]["options"]
                for mod in mods:
                    try:
                        res = mod.predict(ctx)
                    except Exception as exc:
                        print("[STRAT] %s predict error: %s" % (mod.ID, exc))
                        res = None
                    if not res or "pick" not in res:
                        continue
                    pick = res["pick"]
                    if pick not in options:
                        continue
                    prob = max(0.02, min(0.98, float(res.get("prob") or 0.5)))
                    odd = ctx["odds"].get(pick)
                    if not odd:
                        odd = round(max(1.05, 1.0 / prob) * _MARGIN, 2)
                    conn.execute(
                        "INSERT OR IGNORE INTO strategy_shadow_bets "
                        "(sector, strategy, match_id, market, selection, "
                        "odd, prob, stake, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')",
                        (sector, mod.ID, mid, SECTORS[sector]["market"], pick,
                         odd, prob, SHADOW_STAKE))
                    inserted += 1
        conn.commit()
    return {"inserted": inserted, "matches": len(rows)}


# ===========================================================================
#  2. Сетлмент віртуальних ставок + підрахунок ROI/Winrate/банк.
# ===========================================================================
def _resolve_hit(sector, selection, hs, as_):
    """Чи виграла віртуальна ставка з урахуванням футбольної логіки сектора."""
    if hs is None or as_ is None:
        return None
    if sector == "outcomes":
        if selection == "П1":
            return hs > as_
        if selection == "П2":
            return hs < as_
        if selection == "X":
            return hs == as_
    if sector == "totals":
        tot = hs + as_
        if selection == "ТБ 2.5":
            return tot >= 3
        if selection == "ТМ 2.5":
            return tot <= 2
    if sector == "btts":
        yes = hs > 0 and as_ > 0
        if selection == "ОЗ - Так":
            return yes
        if selection == "ОЗ - Ні":
            return not yes
    return None


def settle_shadow_bets(db):
    """Оновлює статус/профіт PENDING‑тіней, у яких матч вже завершився."""
    settled = wins = los = 0
    with db.get_connection() as conn:
        _ensure_tables(conn)
        rows = conn.execute(
            """SELECT sb.id, sb.sector, sb.selection, sb.odd, sb.stake,
                      m.home_score, m.away_score
               FROM strategy_shadow_bets sb
               JOIN matches m ON m.id = sb.match_id
               WHERE sb.status='PENDING'
                 AND m.status IN (%s)
                 AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL"""
            % ",".join("?" * len(_FINISHED_STATUSES)),
            list(_FINISHED_STATUSES)).fetchall()
        for sb_id, sector, selection, odd, stake, hs, as_ in rows:
            hit = _resolve_hit(sector, selection, hs, as_)
            if hit is None:
                status, profit = "CANCELLED", 0.0
            elif hit:
                status, profit = "WON", round(stake * (float(odd or 1.0) - 1.0), 2)
                wins += 1
            else:
                status, profit = "LOST", -stake
                los += 1
            conn.execute("UPDATE strategy_shadow_bets SET status=?, profit=? "
                         "WHERE id=?", (status, profit, sb_id))
            settled += 1
        conn.execute(
            """UPDATE strategy_shadow_bets SET status='CANCELLED', profit=0.0
               WHERE status='PENDING' AND match_id IN (
                   SELECT id FROM matches WHERE status IN ('CANCELLED','POSTPONED'))""")
        conn.commit()
    return {"settled": settled, "wins": wins, "losses": los}


def _stats_rows(conn):
    rows = conn.execute(
        """SELECT sector, strategy,
                  SUM(CASE WHEN status IN ('WON','LOST') THEN 1 ELSE 0 END),
                  SUM(CASE WHEN status='WON' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN status IN ('WON','LOST') THEN stake ELSE 0 END),
                  SUM(CASE WHEN status IN ('WON','LOST') THEN profit ELSE 0 END),
                  SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END)
           FROM strategy_shadow_bets
           GROUP BY sector, strategy""").fetchall()
    out = []
    for sector, strat, settled, wins, staked, profit, pending in rows:
        settled, wins = settled or 0, wins or 0
        staked = staked or 0.0
        profit = profit or 0.0
        roi = (profit / staked * 100.0) if staked > 0 else 0.0
        wr = (wins / settled * 100.0) if settled > 0 else 0.0
        out.append({
            "sector": sector, "strategy": strat,
            "settled": settled, "wins": wins,
            "winrate_pct": round(wr, 2), "staked": round(staked, 2),
            "profit": round(profit, 2), "roi_pct": round(roi, 2),
            "bank": round(SHADOW_START_BANK + profit, 2),
            "pending": pending or 0,
        })
    out.sort(key=lambda r: (-r["roi_pct"], -r["settled"], -r["bank"]))
    return out


def snapshot_stats(db):
    """Знімає свіжий снапшот ROI/Winrate/банк у strategy_stats."""
    rows = get_stats(db)  # живий агрегат
    with db.get_connection() as conn:
        _ensure_tables(conn)
        for r in rows:
            conn.execute(
                """INSERT INTO strategy_stats
                   (sector, strategy, settled, wins, winrate_pct,
                    staked, profit, roi_pct, bank, pending)
                   VALUES (%s)
                   ON CONFLICT(sector, strategy) DO UPDATE SET
                     settled=excluded.settled, wins=excluded.wins,
                     winrate_pct=excluded.winrate_pct, staked=excluded.staked,
                     profit=excluded.profit, roi_pct=excluded.roi_pct,
                     bank=excluded.bank, pending=excluded.pending,
                     updated_at=datetime('now')"""
                                                % (",".join(["?"] * 10)),
                (r["sector"], r["strategy"], r["settled"], r["wins"],
                 r["winrate_pct"], r["staked"], r["profit"], r["roi_pct"],
                 r["bank"], r["pending"]))
        conn.commit()
    return {"snapshot": len(rows)}


def get_stats(db, sector=None):
    """Свіжі ROI/Winrate/банк по кожному скрипту (прямий агрегат з тіней).

    Гарантовано містить УСІ 30 скриптів: той, хто ще жодного разу не
    поставив тінь, отримує нульові стати і стартовий банк — таблиця
    конкуренції завжди повна.
    """
    with db.get_connection() as conn:
        _ensure_tables(conn)
        rows = _stats_rows(conn)
    known = {(r["sector"], r["strategy"]) for r in rows}
    for sec, mods in load_strategies().items():
        if sector and sec != sector:
            continue
        for mod in mods:
            sid = getattr(mod, "ID", None)
            if sid and (sec, sid) not in known:
                known.add((sec, sid))
                rows.append({
                    "sector": sec, "strategy": sid,
                    "settled": 0, "wins": 0, "winrate_pct": 0.0,
                    "staked": 0.0, "profit": 0.0, "roi_pct": 0.0,
                    "bank": SHADOW_START_BANK, "pending": 0,
                })
    if sector:
        rows = [r for r in rows if r["sector"] == sector]
    rows.sort(key=lambda r: (-r["roi_pct"], -r["settled"], -r["bank"]))
    return rows


def top_strategies(db, sector, k=3, min_settled=MIN_SETTLED_FOR_RANK):
    """ТОП-k стратегій сектору за поточним ROI (з мінімальним порогом)."""
    rows = get_stats(db, sector=sector)
    qualified = [r for r in rows if r["settled"] >= min_settled][:k]
    if len(qualified) < k:
        rest = [r for r in rows if r not in qualified and r["settled"] >= 1]
        qualified += rest[: k - len(qualified)]
    if len(qualified) < k:
        qualified += [r for r in rows if r not in qualified][: k - len(qualified)]
    return [r["strategy"] for r in qualified]





# ===========================================================================
#  3. Ensemble Consensus для /api/matches.
# ===========================================================================
def _picks_for_match(conn, match_id, sector, strat_ids):
    """Остання віртуальна прогноз на матч для кожного з strat_ids."""
    if not strat_ids:
        return []
    q = ",".join("?" * len(strat_ids))
    rows = conn.execute(
        "SELECT strategy, selection, prob FROM strategy_shadow_bets "
        "WHERE match_id=? AND sector=? AND strategy IN (%s)" % q,
        (match_id, sector) + tuple(strat_ids)).fetchall()
    return [{"strategy": r[0], "pick": r[1],
             "prob": float(r[2] or 0.0)} for r in rows if r[1]]


def ensemble_consensus(db, match_ids):
    """{match_id: {"outcomes": {...}, ...}} — консенсус ТОП-3 з кожного сектору."""
    if not match_ids:
        return {}
    result = {}
    with db.get_connection() as conn:
        _ensure_tables(conn)
        for sector in SECTORS:
            top = top_strategies(db, sector, k=3)
            if not top:
                continue
            ids = ",".join("?" * len(top))
            rows = conn.execute(
                "SELECT match_id, strategy, selection, prob FROM strategy_shadow_bets "
                "WHERE sector=? AND strategy IN (%s) AND match_id IN (%s)"
                % (ids, ",".join(["?"] * len(match_ids))),
                (sector,) + tuple(top) + tuple(match_ids)).fetchall()
            grouped = {mid: [] for mid in match_ids}
            for mid, strat, sel, prob in rows:
                grouped.setdefault(mid, []).append(
                    {"strategy": strat, "pick": sel, "prob": float(prob or 0.0)})
            for mid, picks in grouped.items():
                picks = [p for p in picks if p["pick"]]
                if not picks:
                    continue
                counts = {}
                probsum = {}
                for p in picks:
                    counts[p["pick"]] = counts.get(p["pick"], 0) + 1
                    probsum[p["pick"]] = probsum.get(p["pick"], 0.0) + p["prob"]
                # мажоритет: pick з найбільшою кількістю голосів (ранг — сума prob)
                majority = sorted(counts.items(),
                                  key=lambda kv: (-kv[1], -probsum[kv[0]]))[0][0]
                n_votes = counts[majority]
                prob = round(probsum[majority] / n_votes, 4)
                result.setdefault(mid, {})[sector] = {
                    "pick": majority, "prob": prob,
                    "votes": "%d/%d" % (n_votes, len(top)),
                    "strategies": picks,
                }
    return {mid: v for mid, v in result.items() if v}


# ===========================================================================
#  Композиційний цикл: settle → snapshot → generate.
# ===========================================================================
def run_cycle(db, force=False):
    """Композиційний цикл: settle → snapshot → generate.

    Викликається з ``settle_pending_bets()`` (app.py) та з ``/api/matches``.
    Тротлінг 60 с, щоб щохвилинні оновлення сторінок не проганяли арену
    по 30 скриптах щоразу; ``force=True`` — без тротлінгу (CLI/тести).
    """
    global _last_cycle_ts
    now = time.time()
    if not force and now - _last_cycle_ts < _CYCLE_THROTTLE_SEC:
        return {"skipped": "throttled"}
    _last_cycle_ts = now
    settle = settle_shadow_bets(db)
    snap = snapshot_stats(db)
    gen = generate_shadow_bets(db)
    return {"settle": settle, "stats_snapshot": snap, "generate": gen}


if __name__ == "__main__":
    from database import LogicBetDB

    _db = LogicBetDB(os.path.join(os.getcwd(), "user_data.db"))
    print(run_cycle(_db))





