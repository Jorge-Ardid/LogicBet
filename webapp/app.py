"""LogicBet Web — Flask backend reusing existing analytics/database modules.

The single source of truth remains the existing SQLite database
(godot_app/logicbet.db) that CI sync keeps updating. Local user data
(user_bets, config/bankroll) lives in the same DB on the server side and is
NEVER overwritten by this app — it only INSERTs user bets and updates the
explicitly protected config keys.
"""
import os
import sys
from datetime import datetime, timedelta

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

from database import LogicBetDB  # noqa: E402

# Канонічна БД ДАНИХ (Godot/API): трекається git'ом, оновлюється CI-синком —
# саме через неї на сервер приходять свіжі матчі/команди/прогнози.
DATA_DB_PATH = os.environ.get("LOGICBET_DATA_DB") or os.path.join(
    ROOT, "godot_app", "logicbet.db")
# РОБОЧА БД ВЕБУ: ставки користувача + банкрол. НІКОЛИ не трекається git'ом
# (.gitignore), тому `git reset --hard` / `git pull` при деплої фізично не
# можуть їх перетерти. Якщо файлу нема — створюється порожня схема
# (CREATE TABLE IF NOT EXISTS); існуючий файл НІКОЛИ не перезаписується.
USER_DB_PATH = os.environ.get("LOGICBET_DB_PATH") or os.path.join(
    ROOT, "webapp", "user_data.db")
db = LogicBetDB(USER_DB_PATH, data_db_path=DATA_DB_PATH)

app = Flask(__name__)


@app.after_request
def _no_cache_api(resp):
    """Заборона кешування всіх JSON/API-відповідей на рівні HTTP,
    щоб браузер і проміжні CDN не віддавали застарілі дані (Історія,
    матчі, ставки). Статику (CSS/JS/PNG) це не чіпає — тут лише JSON."""
    if resp.mimetype == "application/json":
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp

FINISHED = ("FT", "AET", "PEN", "FINISHED")
LIVE = ("LIVE", "1H", "2H", "HT", "ET", "BT", "P")
KYIV_TZ_OFFSET = timedelta(hours=3)  # EEST (UTC+3)

STATUS_LABELS = {
    "FT": ("Завершено", "finished"),
    "AET": ("Завершено", "finished"),
    "PEN": ("Завершено", "finished"),
    "FINISHED": ("Завершено", "finished"),
    "CANCELLED": ("Скасовано", "cancelled"),
    "POSTPONED": ("Перенесено", "cancelled"),
    "NS": ("Очікується", "scheduled"),
    "LIVE": ("LIVE", "live"),
}


def parse_dt(value):
    """Parse stored ISO date ('2026-08-23T13:00:00Z' or '2026-08-23 13:00:00')."""
    if not value:
        return None
    txt = str(value).strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(txt, fmt)
            return dt if dt.tzinfo is None else dt.replace(tzinfo=None) - timedelta(hours=0)
        except ValueError:
            continue
    return None


def to_kyiv(dt):
    return dt + KYIV_TZ_OFFSET


def status_info(status):
    return STATUS_LABELS.get((status or "NS").upper(), ("Очікується", "scheduled"))


def cfg_float(key, default):
    val = db.get_config(key)
    try:
        return float(val) if val is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def _resolve_selection_hit(sel, hs, as_t, hth=None, hta=None):
    """Чи пройшов маркет: True/False; None — не розпізнано (лишаємо PENDING).

    Семантика 1-в-1 з evaluate_user_bets() у python/main.py (пайплайн),
    щоб веб і CI ніколи не розійшлися в оцінці однієї ставки."""
    s = (sel or "").upper().strip()
    if not s:
        return None
    # Комбо ("П1 / ТБ 2.5") — рахуємо за першим маркетом
    s = s.split("/")[0].strip()

    def _thr(default=2.5):
        for t in ("0.5", "1.5", "2.5", "3.5", "4.5", "5.5", "6.5"):
            if t in s:
                return float(t)
        return default

    # --- 1-й тайм ---
    if ("1-Й ТАЙМ" in s or "1-Й Т" in s or "1-Й" in s):
        if hth is None or hta is None:
            return None
        tot_ht = hth + hta
        if "ТБ" in s:
            return tot_ht > _thr()
        if "ТМ" in s:
            return tot_ht < _thr()
        return None
    # --- Подвійний шанс (до 1X2: '1X' містить '1'...) ---
    if "1X" in s or "1Х" in s or "1 X" in s or "1 Х" in s:
        return hs >= as_t
    if "X2" in s or "Х2" in s or "X 2" in s or "Х 2" in s:
        return as_t >= hs
    if "12" in s or "1 2" in s:
        return hs != as_t
    # --- Основний 1X2 ---
    if "П1" in s or "HOME" in s:
        return hs > as_t
    if "П2" in s or "AWAY" in s:
        return as_t > hs
    if ("НІЧИЯ" in s or s == "DRAW" or s.startswith("X (")
            or s.startswith("Х (") or s == "X" or s == "Х"):
        return hs == as_t
    # --- ОЗ / BTTS ('ОЗ - Так' / 'ОЗ - Ні'; legacy 'НЕ ОЗ…') ---
    if "ОЗ" in s or "BTTS" in s:
        both = hs > 0 and as_t > 0
        no = ("НЕ ОЗ" in s or "ОЗ - НІ" in s or "ОЗ - НI" in s
              or s.startswith("НЕ ") or "НЕ ЗАБ" in s)
        return (not both) if no else both
    # --- Загальні тотали ---
    if "БІЛЬШЕ" in s or "OVER" in s or "ТБ" in s or "ТОТАЛ Б" in s:
        return (hs + as_t) > _thr()
    if "МЕНШЕ" in s or "UNDER" in s or "ТМ" in s or "ТОТАЛ М" in s:
        return (hs + as_t) < _thr()
    return None


def settle_pending_bets():
    """Авто-розрахунок PENDING-ставок робочої БД проти фінальних рахунків
    канонічної logicbet.db. Викликається при кожному читанні /api/bets.

    Модель капіталу (заморожені кошти):
      • стейк PENDING-ставки ВЖЕ у загальному балансі (заморожений);
      • WON  -> банкрол += чистий виграш stake*(odd-1), заморозка знімається;
      • LOST -> банкрол -= stake (програний стейк списується).
    Тобто заморозка сама по собі НІКОЛИ не є просадкою і не штрафує систему —
    ефективність оцінюється лише по РОЗРАХОВАНИХ ставках (див. analytics)."""
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT ub.id, ub.selection, ub.stake, ub.odd,
                   m.home_score, m.away_score, m.ht_score_h, m.ht_score_a
            FROM user_bets ub
            JOIN matches m ON ub.match_id = m.id
            WHERE ub.status = 'PENDING'
              AND m.status IN ('FT','AET','PEN','FINISHED')
              AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        """).fetchall()
        if not rows:
            return {"settled": 0, "wins": 0}

        row = conn.execute(
            "SELECT value FROM config WHERE key = 'bankroll'").fetchone()
        bankroll = float(row[0]) if row else 1000.0

        settled = wins = 0
        for bid, sel, stake, odd, hs, as_t, hth, hta in rows:
            hit = _resolve_selection_hit(sel, int(hs), int(as_t), hth, hta)
            if hit is None:
                continue  # невідомий/custom маркет — залишається PENDING
            if hit:
                profit = round(stake * (odd - 1), 2)   # чистий виграш
                conn.execute(
                    "UPDATE user_bets SET status='WON', profit=? WHERE id=?",
                    (profit, bid))
                bankroll += profit
                wins += 1
            else:
                conn.execute(
                    "UPDATE user_bets SET status='LOST', profit=? WHERE id=?",
                    (-round(stake, 2), bid))
                bankroll -= float(stake)               # програний стейк
            settled += 1

        if settled:
            conn.execute("""
                INSERT INTO config (key, value) VALUES ('bankroll', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (str(round(bankroll, 2)),))
            conn.commit()
    return {"settled": settled, "wins": wins}


def predictions_by_match(match_ids):
    if not match_ids:
        return {}
    marks = ",".join("?" for _ in match_ids)
    # Reuse the same karma/reputation engine that analytics.py uses so that
    # confidence_score_pct is consistent between generation and serving.
    from analytics import BettingAnalytics
    _an = BettingAnalytics(db)
    _an._compute_reputation()  # build/refresh market karma from settled bets
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT match_id, market, selection, calculated_prob, bookmaker_odd, confidence_level "
            "FROM predictions WHERE match_id IN (%s) ORDER BY id" % marks,
            list(match_ids),
        ).fetchall()
    result = {}
    for mid, market, selection, prob, odd, conf in rows:
        prob_f = float(prob or 0)
        pct = round(prob_f * 100, 1)
        sel_txt = selection
        is_btts = (market == "BTTS") or ("ОЗ" in (selection or ""))
        if is_btts:
            sel_txt = "ОЗ - Так" if prob_f >= 0.5 else "ОЗ - Ні"
        token = _an._market_token(sel_txt) if is_btts else _an._market_token(selection)
        kb = _an._karma_bonus(token) if token else 0.0
        conf_pct = min(99.0, round(prob_f * (1 + kb) * 100, 1))
        result.setdefault(mid, []).append({
            "market": market,
            "selection": sel_txt,
            "prob": pct,
            "odd": float(odd) if odd else None,
            "confidence": conf or "",
            "btts": is_btts,
            "confidence_score_pct": conf_pct,
        })
    for mid in result:
        result[mid].sort(key=lambda p: p.get("confidence_score_pct", 0), reverse=True)
    return result


def match_payload(row, preds):
    (mid, date_str, league, status, hs, ascore, home, away, home_id, away_id) = row
    label, key = status_info(status)
    kickoff = parse_dt(date_str)
    show_score = key in ("finished", "live") and hs is not None and ascore is not None
    return {
        "id": mid,
        "date": date_str,
        "time": to_kyiv(kickoff).strftime("%H:%M") if kickoff else "--:--",
        "league": league,
        "status": label,
        "status_key": key,
        "home": home,
        "away": away,
        # public ids — клієнт будує посилання на профіль команди / аналіз матчу
        "home_id": home_id,
        "away_id": away_id,
        "score": "%s:%s" % (hs, ascore) if show_score else None,
        "predictions": preds,
        "summary": " • ".join(p["selection"] for p in preds[:5]),
        "top_prob": preds[0]["prob"] if preds else None,
        # internal only — consumed by load_matches to enrich form status;
        # popped out before sending to the client
        "_home_id": home_id,
        "_away_id": away_id,
    }


def load_matches(date_condition, params):
    query = """
        SELECT m.id, m.date, m.league, m.status, m.home_score, m.away_score,
               t1.name, t2.name, m.home_team_id, m.away_team_id
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE %s AND m.status NOT IN ('CANCELLED', 'POSTPONED')
        ORDER BY m.date, m.league
    """ % date_condition
    with db.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        # матчі, на які вже є активна ставка користувача (PENDING)
        betted = dict(conn.execute(
            "SELECT match_id, MAX(odd) FROM user_bets "
            "WHERE status='PENDING' GROUP BY match_id").fetchall())
        preds = predictions_by_match([r[0] for r in rows])
        payloads = [match_payload(r, preds.get(r[0], [])) for r in rows]
        for p in payloads:
            home_id = p.pop("_home_id", None)
            away_id = p.pop("_away_id", None)
            p["has_bet"] = p["id"] in betted
            p["bet_odd"] = betted.get(p["id"])
            if home_id:
                fs_h = db.get_team_form_status(home_id)
                p["home_form_status"] = fs_h["status"]
                p["home_form_points"] = fs_h["points"]
            if away_id:
                fs_a = db.get_team_form_status(away_id)
                p["away_form_status"] = fs_a["status"]
                p["away_form_points"] = fs_a["points"]
    return payloads


UK_WEEKDAYS = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"]


def day_label(dt_utc):
    local = to_kyiv(dt_utc)
    return "%s, %s" % (UK_WEEKDAYS[local.weekday()], local.strftime("%d.%m.%Y"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(app.root_path, "static"), "manifest.json")


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(os.path.join(app.root_path, "static"), "sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.route("/api/state")
def api_state():
    with db.get_connection() as conn:
        acc = conn.execute("""
            SELECT SUM(CASE WHEN p.is_hit = 1 THEN 1 ELSE 0 END), COUNT(p.is_hit)
            FROM predictions p JOIN matches m ON m.id = p.match_id
            WHERE m.status IN ('FT','AET','PEN','FINISHED') AND p.is_hit IS NOT NULL
        """).fetchone()
        pending = conn.execute("SELECT COUNT(*) FROM user_bets WHERE status='PENDING'").fetchone()[0]
        today_n = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE DATE(date)=DATE('now') AND status NOT IN ('CANCELLED','POSTPONED')"
        ).fetchone()[0]
        # Капітал: загальний баланс (включно із замороженими у PENDING),
        # вільні кошти та ROI за РОЗРАХОВАНИМИ ставками.
        money = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN status='PENDING' THEN stake END), 0),
                   COALESCE(SUM(stake), 0),
                   COALESCE(SUM(profit), 0)
            FROM user_bets
            WHERE status IN ('PENDING','WON','LOST')
        """).fetchone()
    hits, total = (acc[0] or 0), (acc[1] or 0)
    bankroll = cfg_float("bankroll", 1000.0)
    frozen_stake = round(float(money[0] or 0), 2)
    settled_stake = round(float(money[1] or 0) - frozen_stake, 2)
    settled_net = round(float(money[2] or 0), 2)
    roi_pct = round(settled_net / settled_stake * 100.0, 1) if settled_stake > 0 else None
    return jsonify({
        "bankroll": bankroll,
        # Загальний баланс (включно із замороженим під PENDING портфелем)
        "balance_total": round(bankroll, 2),
        # Заморожено під активними ставками (відкритий портфель — не просадка)
        "frozen": frozen_stake,
        # Доступні кошти (Free Capital)
        "free_capital": round(bankroll - frozen_stake, 2),
        # Settled ROI %: чистий прибуток / сума розрахованих ставок
        "settled_roi_pct": roi_pct,
        "default_stake": cfg_float("default_stake", 10.0),
        "accuracy": {"hits": hits, "total": total,
                     "pct": round(hits * 100.0 / total, 1) if total else 0.0},
        "pending_bets": pending,
        "today_matches": today_n,
    })


@app.route("/api/matches")
def api_matches():
    flt = request.args.get("filter", "all")
    groups = []
    if flt in ("all", "today"):
        rows = load_matches("DATE(m.date) = DATE('now')", [])
        groups.append({"key": "today", "title": "Сьогодні",
                       "label": day_label(datetime.utcnow()), "matches": rows})
    if flt in ("all", "tomorrow"):
        rows = load_matches("DATE(m.date) = DATE('now', '+1 day')", [])
        groups.append({"key": "tomorrow", "title": "Завтра",
                       "label": day_label(datetime.utcnow() + timedelta(days=1)), "matches": rows})
    return jsonify({"groups": groups})


@app.route("/api/bets", methods=["POST"])
def api_place_bet():
    data = request.get_json(silent=True) or {}
    try:
        match_id = int(data.get("match_id") or 0)
        stake = float(data.get("stake") or 0)
        odd = float(data.get("odd") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Некоректні числа"}), 400
    selection = str(data.get("selection") or "").strip()
    if not match_id or len(selection) < 2:
        return jsonify({"error": "Вкажіть матч і вибір"}), 400
    if stake <= 0 or stake > 100000:
        return jsonify({"error": "Ставка має бути > 0"}), 400
    if odd < 1.01:
        return jsonify({"error": "Коефіцієнт має бути ≥ 1.01"}), 400

    with db.get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM matches WHERE id=?", (match_id,)).fetchone()
        if not exists:
            return jsonify({"error": "Матч не знайдено"}), 404
        # Upsert: if the user already has a PENDING bet on this match — rewrite it
        # (keeps the last placed coefficient until the match is sent to history).
        prev = conn.execute(
            "SELECT id FROM user_bets WHERE match_id=? AND status='PENDING' "
            "ORDER BY id LIMIT 1", (match_id,)).fetchone()
        if prev:
            bet_id = prev[0]
            conn.execute(
                "UPDATE user_bets SET selection=?, stake=?, odd=? WHERE id=?",
                (selection, stake, odd, bet_id))
            conn.commit()
            return jsonify({"ok": True, "id": bet_id, "updated": True}), 200
        cur = conn.execute(
            "INSERT INTO user_bets (match_id, selection, stake, odd, status, profit) "
            "VALUES (?, ?, ?, ?, 'PENDING', 0.0)",
            (match_id, selection, stake, odd))
        conn.commit()
        bet_id = cur.lastrowid
    return jsonify({"ok": True, "id": bet_id}), 201


@app.route("/api/bets/<int:bet_id>", methods=["DELETE"])
def api_delete_bet(bet_id):
    with db.get_connection() as conn:
        row = conn.execute("SELECT status FROM user_bets WHERE id=?", (bet_id,)).fetchone()
        if not row:
            return jsonify({"error": "Ставку не знайдено"}), 404
        if row[0] != "PENDING":
            return jsonify({"error": "Можна скасувати лише PENDING"}), 400
        conn.execute("DELETE FROM user_bets WHERE id=?", (bet_id,))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/bets")
def api_history():
    # Авто-розрахунок: PENDING-ставки звіряються з фінальними рахунками
    # канонічної БД; WON/LOST + банкрол оновлюються до формування відповіді.
    settle_pending_bets()

    status = request.args.get("status", "ALL").upper()
    filters, params = [], []
    if status in ("PENDING", "WON", "LOST"):
        filters.append("ub.status = ?")
        params.append(status)
    cond = ("WHERE " + " AND ".join(filters)) if filters else ""

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(max(int(request.args.get("per_page", 50)), 1), 200)
    except (TypeError, ValueError):
        per_page = 50

    base_from = """
        FROM user_bets ub
        JOIN matches m ON ub.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
    """
    with db.get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) " + base_from + (cond + " " if cond else ""),
            params).fetchone()[0]
        rows = conn.execute("""
            SELECT ub.id, ub.selection, ub.stake, ub.odd, ub.status, ub.profit,
                   m.id, m.date, m.league, m.status, m.home_score, m.away_score,
                   t1.name, t2.name
        """ + base_from + """
            %s ORDER BY m.date DESC, m.id DESC, ub.id DESC
            LIMIT ? OFFSET ?
        """ % cond, params + [per_page, (page - 1) * per_page]).fetchall()
    bets = []
    for (bid, sel, stake, odd, bstat, profit, mid, date_str, league,
         mstat, hs, ascore, home, away) in rows:
        label, key = status_info(mstat)
        kickoff = parse_dt(date_str)
        bets.append({
            "id": bid, "selection": sel,
            "stake": float(stake or 0), "odd": float(odd or 0),
            "status": bstat, "profit": round(float(profit or 0), 2),
            "match": "%s — %s" % (home, away),
            "league": league,
            "time": to_kyiv(kickoff).strftime("%d.%m %H:%M") if kickoff else "--:--",
            "match_status": label, "match_status_key": key,
            "score": "%s:%s" % (hs, ascore) if hs is not None and ascore is not None else None,
        })
    return jsonify({
        "bets": bets,
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_more": page * per_page < total,
    })


@app.route("/api/stats")
def api_stats():
    with db.get_connection() as conn:
        counts = dict(conn.execute(
            "SELECT status, COUNT(*) FROM user_bets GROUP BY status").fetchall())
        profit = conn.execute(
            "SELECT COALESCE(SUM(profit),0) FROM user_bets WHERE status IN ('WON','LOST')"
        ).fetchone()[0]
        acc = conn.execute("""
            SELECT SUM(CASE WHEN p.is_hit=1 THEN 1 ELSE 0 END), COUNT(p.is_hit)
            FROM predictions p JOIN matches m ON m.id=p.match_id
            WHERE m.status IN ('FT','AET','PEN','FINISHED') AND p.is_hit IS NOT NULL
        """).fetchone()
        markets = conn.execute("""
            SELECT p.market, SUM(CASE WHEN p.is_hit=1 THEN 1 ELSE 0 END), COUNT(p.is_hit)
            FROM predictions p JOIN matches m ON m.id=p.match_id
            WHERE m.status IN ('FT','AET','PEN','FINISHED') AND p.is_hit IS NOT NULL
            GROUP BY p.market ORDER BY 3 DESC LIMIT 8
        """).fetchall()
    won, lost = counts.get("WON", 0), counts.get("LOST", 0)
    decided = won + lost
    hits, total = (acc[0] or 0), (acc[1] or 0)
    return jsonify({
        "bankroll": cfg_float("bankroll", 1000.0),
        "bets": {"won": won, "lost": lost,
                 "pending": counts.get("PENDING", 0)},
        "winrate_pct": round(won * 100.0 / decided, 1) if decided else 0.0,
        "profit": round(float(profit or 0), 2),
        "model_accuracy": {"hits": hits, "total": total,
                           "pct": round(hits * 100.0 / total, 1) if total else 0.0},
        "by_market": [{"market": mk, "hits": h or 0, "total": t}
                      for mk, h, t in markets],
    })


@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"matches": []})
    like = "%" + q + "%"
    rows = load_matches(
        "(t1.name LIKE ? OR t2.name LIKE ?) "
        "AND DATE(m.date) BETWEEN DATE('now','-7 day') AND DATE('now','+14 day')",
        [like, like])
    return jsonify({"matches": rows[:50]})


@app.route("/bet/<int:match_id>")
def bet_page(match_id):
    with db.get_connection() as conn:
        row = conn.execute("""
            SELECT m.id, m.date, m.league, m.status, m.home_score, m.away_score,
                   t1.name, t2.name, m.home_team_id, m.away_team_id
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE m.id = ?
        """, (match_id,)).fetchone()
    if row is None:
        abort(404)
    preds = predictions_by_match([match_id]).get(match_id, [])
    m = match_payload(row, preds)
    # current PENDING bet (if any) so the user can review & fix the coefficient
    cur_bet = None
    with db.get_connection() as conn:
        b = conn.execute(
            "SELECT selection, stake, odd FROM user_bets "
            "WHERE match_id=? AND status='PENDING' ORDER BY id LIMIT 1",
            (match_id,)).fetchone()
        if b:
            cur_bet = {"selection": b[0], "stake": b[1], "odd": b[2]}
    return render_template("bet.html", m=m,
                           default_stake=cfg_float("default_stake", 10.0),
                           cur_bet=cur_bet)


# ============== MATCH DETAILS / TEAM PROFILE (модалки) ==============

FINISHED_SQL = "m.status IN ('FT','AET','PEN','FINISHED')"


def _form_letters(conn, team_id, limit=5):
    """Останні завершені матчі команди -> ['W','D','L',...] (новіші спершу)."""
    rows = conn.execute("""
        SELECT m.home_team_id, m.home_score, m.away_score
        FROM matches m
        WHERE (m.home_team_id = ? OR m.away_team_id = ?) AND %s
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        ORDER BY m.date DESC LIMIT ?
    """ % FINISHED_SQL, (team_id, team_id, limit)).fetchall()
    out = []
    for hid, hs, ascore in rows:
        if hs is None or ascore is None:
            continue
        mine, theirs = (hs, ascore) if hid == team_id else (ascore, hs)
        out.append("W" if mine > theirs else ("D" if mine == theirs else "L"))
    return out


def _team_averages(conn, team_id, limit=10):
    """Середні кутові/картки/xG за останні limit завершених матчів зі статистикою."""
    row = conn.execute("""
        SELECT AVG(CASE WHEN m.home_team_id = ? THEN m.corners_h ELSE m.corners_a END),
               AVG(CASE WHEN m.home_team_id = ? THEN m.yellow_cards_h ELSE m.yellow_cards_a END),
               AVG(CASE WHEN m.home_team_id = ? THEN m.red_cards_h ELSE m.red_cards_a END),
               AVG(CASE WHEN m.home_team_id = ? THEN m.xg_h ELSE m.xg_a END),
               COUNT(*)
        FROM (
            SELECT * FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND stats_fetched = 1 AND status IN ('FT','AET','PEN','FINISHED')
            ORDER BY date DESC LIMIT ?
        ) m
    """, (team_id, team_id, team_id, team_id, team_id, team_id, limit)).fetchone()
    avg = lambda v: round(float(v), 2) if v is not None else None  # noqa: E731
    return {"corners": avg(row[0]), "yellow_cards": avg(row[1]),
            "red_cards": avg(row[2]), "xg": avg(row[3]), "sample": row[4] or 0}


def _team_side(conn, team_id):
    """Загальний блок даних команди для порівняння та профілю."""
    t = conn.execute(
        "SELECT id, name, elo_rating, current_form, rank, points "
        "FROM teams WHERE id = ?", (team_id,)).fetchone()
    if t is None:
        return None
    return {
        "id": t[0], "name": t[1],
        "elo": round(float(t[2] or 1500), 1),
        "current_form": t[3] or "",
        "rank": t[4] or 0, "points": t[5] or 0,
        "form_letters": _form_letters(conn, team_id, 5),
        "avg": _team_averages(conn, team_id, 10),
    }


@app.route("/api/match/<int:match_id>/details")
def api_match_details(match_id):
    """Статистика завершеного матчу або порівняння команд до матчу."""
    with db.get_connection() as conn:
        r = conn.execute("""
            SELECT m.id, m.date, m.league, m.status, m.home_score, m.away_score,
                   m.ht_score_h, m.ht_score_a,
                   t1.id, t1.name, t1.elo_rating,
                   t2.id, t2.name, t2.elo_rating,
                   m.corners_h, m.corners_a,
                   m.yellow_cards_h, m.yellow_cards_a,
                   m.red_cards_h, m.red_cards_a,
                   m.shots_on_h, m.shots_on_a,
                   m.shots_off_h, m.shots_off_a,
                   m.xg_h, m.xg_a,
                   m.possession_h, m.possession_a,
                   m.stats_fetched, m.h_elo_change, m.a_elo_change
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE m.id = ?
        """, (match_id,)).fetchone()
        if r is None:
            return jsonify({"error": "Матч не знайдено"}), 404

        (mid, date_str, league, status, hs, ascore, ht_h, ht_a,
         h_id, h_name, h_elo, a_id, a_name, a_elo,
         c_h, c_a, yc_h, yc_a, rc_h, rc_a, so_h, so_a, soff_h, soff_a,
         xg_h, xg_a, pos_h, pos_a, stf, elo_chg_h, elo_chg_a) = r

        label, key = status_info(status)
        kickoff = parse_dt(date_str)
        d = {
            "id": mid, "date": date_str, "league": league,
            "status": label, "status_key": key,
            "time": to_kyiv(kickoff).strftime("%H:%M") if kickoff else "--:--",
            "home": {"id": h_id, "name": h_name,
                     "elo": round(float(h_elo or 1500), 1)},
            "away": {"id": a_id, "name": a_name,
                     "elo": round(float(a_elo or 1500), 1)},
            "score": [hs, ascore] if hs is not None else None,
            "ht": [ht_h, ht_a] if ht_h is not None else None,
        }

        if key == "finished":
            d["elo_change"] = [round(float(elo_chg_h or 0), 1),
                               round(float(elo_chg_a or 0), 1)]

        if key == "finished" and stf:
            d["stats"] = {
                "possession": [pos_h, pos_a],
                "xg": [round(float(xg_h or 0), 2), round(float(xg_a or 0), 2)],
                "shots_total": [(so_h or 0) + (soff_h or 0),
                                (so_a or 0) + (soff_a or 0)],
                "shots_on": [so_h or 0, so_a or 0],
                "shots_off": [soff_h or 0, soff_a or 0],
                "corners": [c_h or 0, c_a or 0],
                "yellow": [yc_h or 0, yc_a or 0],
                "red": [rc_h or 0, rc_a or 0],
            }
        else:
            # Матч не зіграно (або статистику не зібрано) -> порівняння до матчу
            d["comparison"] = {"home": _team_side(conn, h_id),
                               "away": _team_side(conn, a_id)}
    return jsonify(d)


@app.route("/api/team/<int:team_id>/profile")
def api_team_profile(team_id):
    """Профіль команди: Elo, форма W/D/L, середні кутові/картки/xG, наступний матч."""
    with db.get_connection() as conn:
        side = _team_side(conn, team_id)
        if side is None:
            return jsonify({"error": "Команду не знайдено"}), 404
        recent = []
        for date_str, hid, h_name, a_name, hs, ascore in conn.execute("""
                SELECT m.date, m.home_team_id, t1.name, t2.name,
                       m.home_score, m.away_score
                FROM matches m
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                WHERE (m.home_team_id = ? OR m.away_team_id = ?) AND %s
                  AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
                ORDER BY m.date DESC LIMIT 8
            """ % FINISHED_SQL, (team_id, team_id)).fetchall():
            mine, theirs = (hs, ascore) if hid == team_id else (ascore, hs)
            recent.append({
                "date": str(date_str)[:10] if date_str else "",
                "opp": a_name if hid == team_id else h_name,
                "venue": "H" if hid == team_id else "A",
                "score": "%s:%s" % (mine, theirs),
                "r": "W" if mine > theirs else ("D" if mine == theirs else "L"),
            })
        nxt = conn.execute("""
            SELECT m.date, t1.name, t2.name, m.home_team_id
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
              AND m.status NOT IN ('FT','AET','PEN','FINISHED','CANCELLED','POSTPONED')
            ORDER BY m.date ASC LIMIT 1
        """, (team_id, team_id)).fetchone()
        side["recent"] = recent
        side["next"] = (
            {"date": str(nxt[0])[:16] if nxt[0] else "",
             "opp": nxt[2] if nxt[3] == team_id else nxt[1],
             "venue": "H" if nxt[3] == team_id else "A"}
            if nxt else None)
    return jsonify(side)


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            bankroll = float(data.get("bankroll"))
            stake = float(data.get("default_stake"))
        except (TypeError, ValueError):
            return jsonify({"error": "Введіть числа"}), 400
        if bankroll <= 0 or stake <= 0:
            return jsonify({"error": "Значення мають бути > 0"}), 400
        db.set_config("bankroll", str(bankroll))
        db.set_config("default_stake", str(stake))
    return jsonify({"bankroll": cfg_float("bankroll", 1000.0),
                    "default_stake": cfg_float("default_stake", 10.0)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print("LogicBet Web: http://localhost:%d  (DB: %s)" % (port, db.db_path))
    app.run(host="0.0.0.0", port=port, debug=False)
