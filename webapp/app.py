"""LogicBet Web — Flask backend reusing existing analytics/database modules.

The single source of truth remains the existing SQLite database
(godot_app/logicbet.db) that CI sync keeps updating. Local user data
(user_bets, config/bankroll) lives in the same DB on the server side and is
NEVER overwritten by this app — it only INSERTs user bets and updates the
explicitly protected config keys.
"""
import os
import sqlite3
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


def _form_str_for_team(conn, team_id, limit=5):
    """Поточна форма команди W/D/L (новіші спершу) за останні limit матчів."""
    hist = conn.execute("""
        SELECT home_score, away_score, home_team_id
        FROM matches
        WHERE (home_team_id = ? OR away_team_id = ?)
          AND status IN ('FT','AET','PEN','FINISHED')
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY date DESC LIMIT ?
    """, (team_id, team_id, limit)).fetchall()
    out = []
    for hs, ascore, hid in reversed(hist):
        is_h = (hid == team_id)
        mine, theirs = (hs, ascore) if is_h else (ascore, hs)
        out.append("W" if mine > theirs else ("L" if mine < theirs else "D"))
    return "".join(out)


def _ensure_elo_split_cols(conn):
    """Разова міграція роздільного Elo (Зміна A) у канонічній БД даних.

    Схемою передбачені teams.home_elo / teams.away_elo; для баз, де їх ще
    немає, колонки додаються ALTER-ом, а NULL-значення сідуються загальним
    elo_rating — до перших венюних перерахунків поведінка тотожна старій.
    Аналогічна міграція є в database.py для монолітного режиму пайплайну."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(teams)")
    tcols = [c[1] for c in cur.fetchall()]
    for col in ("home_elo", "away_elo"):
        if col not in tcols:
            cur.execute("ALTER TABLE teams ADD COLUMN %s REAL" % col)
            print("[WEB] Migration: added teams.%s" % col)
    cur.execute("UPDATE teams SET home_elo = elo_rating "
                "WHERE home_elo IS NULL AND elo_rating IS NOT NULL")
    cur.execute("UPDATE teams SET away_elo = elo_rating "
                "WHERE away_elo IS NULL AND elo_rating IS NOT NULL")
    conn.commit()


def _ai_pred_hit(sel, hs, as_t, hth, hta, ch, ca, yh, ya, rh, ra,
                 h_name, a_name, re_mod):
    """Чи пройшов конкретний прогноз ШІ. True/False; None — статистики бракує
    (HT/кутові/картки NULL) або формат нерозпізнано (is_hit лишається NULL).

    Гілки 1-в-1 повторюють оцінювач python/main.py: веб і CI-пайплайн
    ніколи не розходяться в оцінці одного прогнозу."""
    if hs is None or as_t is None:
        return None
    s = (sel or "").upper().strip()
    if not s:
        return None
    h_n = (h_name or "").upper().strip()
    a_n = (a_name or "").upper().strip()
    total_match = hs + as_t

    def _nums():
        return [float(x) for x in re_mod.findall(r"\d+\.\d+", s)]

    # ---------- 0. BTTS / ОЗ ----------
    if ("ОЗ" in s) or ("BTTS" in s) or ("ОБИДВІ" in s and "ЗАБ" in s):
        both_scored = (hs > 0 and as_t > 0)
        no_side = (("НЕ ОЗ" in s) or ("ОЗ - НІ" in s)
                   or s.startswith("НЕ ") or ("НЕ ЗАБ" in s))
        return (not both_scored) if no_side else both_scored

    # ---------- 1. 1st-Half Goals ----------
    elif ("1-Й" in s) or ("1ST HALF" in s) or ("(1ST HALF)" in s):
        if hth is None or hta is None:
            return None  # чекаємо HT-статистику — is_hit залишається NULL
        nums = _nums()
        thr = max(nums) if nums else 1.5
        return ((hth + hta) > thr) if (("ТБ" in s) or ("OVER" in s)) \
            else ((hth + hta) < thr)

    # ---------- 2. Corners ----------
    elif ("КУТОВ" in s) or ("CORNERS" in s):
        if ch is None or ca is None:
            return None
        nums = _nums()
        thr = max(nums) if nums else 9.5
        return ((ch + ca) > thr) if (("ТБ" in s) or ("OVER" in s)) \
            else ((ch + ca) < thr)

    # ---------- 3. Cards ----------
    elif ("КАРТК" in s) or ("CARDS" in s):
        if yh is None or ya is None:
            return None
        nums = _nums()
        thr = max(nums) if nums else 4.5
        tot_cards = yh + ya + (rh or 0) + (ra or 0)
        return (tot_cards > thr) if (("ТБ" in s) or ("OVER" in s)) \
            else (tot_cards < thr)

    # ---------- 4. Individual Team Totals ----------
    elif ((("ТБ" in s) or ("ТМ" in s) or ("OVER" in s) or ("UNDER" in s))
          and (h_n in s or a_n in s)):
        nums = _nums()
        thr = max(nums) if nums else 1.5
        is_h_team = bool(h_n and h_n in s)
        is_a_team = bool(a_n and a_n in s)
        if is_h_team and is_a_team:
            if len(h_n) >= len(a_n):
                is_a_team = False
            else:
                is_h_team = False
        team_score = hs if is_h_team else as_t
        return (team_score > thr) if (("ТБ" in s) or ("OVER" in s)) \
            else (team_score < thr)

    # ---------- 5. Double Chance (до 1X2: "1X" містить "1") ----------
    elif ("1X" in s) or ("1Х" in s) or ("1 X" in s) or ("1 Х" in s):
        return hs >= as_t
    elif ("X2" in s) or ("Х2" in s) or ("X 2" in s) or ("Х 2" in s):
        return as_t >= hs
    elif ("12" in s) or ("1 2" in s):
        return hs != as_t

    # ---------- 6. Основний 1X2 ----------
    elif ("П1" in s) or ("HOME" in s):
        return hs > as_t
    elif ("П2" in s) or ("AWAY" in s):
        return as_t > hs
    elif (("НІЧИЯ" in s) or s == "DRAW" or s.startswith("X (")
          or s.startswith("Х (") or s.startswith("X ")
          or s.startswith("Х ") or s in ("X", "Х")):
        return hs == as_t

    # ---------- 7. Загальні тотали голів ----------
    elif ("БІЛЬШЕ" in s) or ("OVER" in s) or ("ТБ" in s) or ("ТОТАЛ Б" in s):
        nums = _nums()
        thr = max(nums) if nums else 2.5
        return total_match > thr
    elif ("МЕНШЕ" in s) or ("UNDER" in s) or ("ТМ" in s) or ("ТОТАЛ М" in s):
        nums = _nums()
        thr = max(nums) if nums else 2.5
        return total_match < thr

    return None  # невідомий формат — чесно лишаємо без оцінки


def settle_ai_predictions():
    """ЗАВДАННЯ 3: повний авто-тест усіх прогнозів для навчання ШІ.

    Коли матч завершено, з фінальним рахунком/статистикою звіряються
    **ВСІ** маркети його картки (1X2/подвійні шанси, ОЗ, Тотал голів,
    Індивідуальні тотали, 1-й тайм, Кутові, Картки) — а не лише той,
    на який користувач поставив. Кожен варіант отримує is_hit=1/0; ці мітки
    далі живлять карму маркетів у analytics._compute_reputation (як віртуальні
    ставки ШІ), тож ваги алгоритму адаптуються на КОЖНОМУ власному сигналі.

    Працює напряму по канонічній DATA_DB окремим з'єднанням; повторні запуски
    ідемпотентні (обробляються лише рядки is_hit IS NULL)."""
    import re as _re
    conn = sqlite3.connect(DATA_DB_PATH)
    try:
        rows = conn.execute("""
            SELECT p.id, p.market, p.selection,
                   m.home_score, m.away_score, m.ht_score_h, m.ht_score_a,
                   m.corners_h, m.corners_a,
                   m.yellow_cards_h, m.yellow_cards_a,
                   m.red_cards_h, m.red_cards_a,
                   t1.name, t2.name
            FROM predictions p
            JOIN matches m ON p.match_id = m.id
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE p.is_hit IS NULL
              AND m.status IN ('FT','AET','PEN','FINISHED')
              AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
        """).fetchall()

        evaluated = hits = 0
        by_market = {}
        for (p_id, market, sel, hs, as_t, hth, hta, ch, ca, yh, ya, rh, ra,
             h_name, a_name) in rows:
            hit = _ai_pred_hit(sel, hs, as_t, hth, hta, ch, ca, yh, ya,
                               rh, ra, h_name, a_name, _re)
            if hit is None:
                continue
            conn.execute("UPDATE predictions SET is_hit = ? WHERE id = ?",
                         (1 if hit else 0, p_id))
            evaluated += 1
            mk = by_market.setdefault(market or "?", [0, 0])
            mk[0] += 1
            if hit:
                hits += 1
                mk[1] += 1
        conn.commit()
        if evaluated:
            print("[WEB] AI settlement: %d маркетів розраховано, %d влучних "
                  "(%.1f%%)" % (evaluated, hits, hits * 100.0 / evaluated))
        return {"evaluated": evaluated, "hits": hits, "by_market": by_market}
    finally:
        conn.close()


_FULL_RECALC_DONE = False


def full_elo_recalc(force=False):
    """Примусовий ПОВНИЙ перерахунок роздільного Elo по всій історії.

    Усі завершені матчі прогоняються від найстарішого до найновішого;
    кожен ДОМАШНІЙ матч змінює ТІЛЬКИ home_elo господаря, а ВИЇЗНИЙ —
    ТІЛЬКИ away_elo гостя (пара порівнюється саме по цих каналах).
    Загальний elo_rating власної динаміки більше не має: після кожного
    матчу він перераховується як середнє арифметичне двох венюних
    рейтингів команди. Перед прогоном канали скидаються у базові 1500,
    тож фінальні значення визначаються ВИКЛЮЧНО історією ігор.

    Автоматично виконується ОДИН раз за життя процесу при першому
    сетлменті; force=True дозволяє повторити примусово."""
    global _FULL_RECALC_DONE
    if _FULL_RECALC_DONE and not force:
        return {"skipped": True}
    import sqlite3 as _sq
    from analytics import BettingAnalytics
    _an = BettingAnalytics(db)
    conn = _sq.connect(DATA_DB_PATH)
    try:
        _ensure_elo_split_cols(conn)
        conn.execute("UPDATE teams SET home_elo = 1500, away_elo = 1500, "
                     "elo_rating = 1500")
        rows = conn.execute("""
            SELECT m.home_team_id, m.away_team_id,
                   m.home_score, m.away_score
            FROM matches m
            WHERE m.status IN ('FT','AET','PEN','FINISHED')
              AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
            ORDER BY m.date ASC, m.id ASC
        """).fetchall()

        r_home, r_away = {}, {}
        for (t_id,) in conn.execute("SELECT id FROM teams"):
            r_home[t_id] = 1500.0
            r_away[t_id] = 1500.0

        n_upd = 0
        for h_id, a_id, hs, asc in rows:
            # одночасний апдейт пари венюних каналів: home-канал господаря
            # проти away-каналу гостя (стандартна Elo-формула, K=20)
            eh, ea = r_home.get(h_id, 1500.0), r_away.get(a_id, 1500.0)
            new_eh, new_ea = _an.update_elo(eh, ea, int(hs), int(asc))
            r_home[h_id] = new_eh
            r_away[a_id] = new_ea
            n_upd += 1

        for t_id in list(r_home.keys()):
            he, ae = r_home[t_id], r_away[t_id]
            conn.execute(
                "UPDATE teams SET home_elo=?, away_elo=?, elo_rating=? "
                "WHERE id=?",
                (round(he, 4), round(ae, 4),
                 round((he + ae) / 2.0, 4), t_id))
        # Історія повністю врахована новими правилами — інкрементальний
        # пост-майтч хід далі працюватиме лише зі СВІЖИМИ результатами.
        conn.execute("""UPDATE matches SET elo_processed = 1
                        WHERE status IN ('FT','AET','PEN','FINISHED')""")
        conn.commit()
        print("[WEB] Full Elo recalc: %d матчів застосовано для %d команд"
              % (n_upd, len(r_home)))
        _FULL_RECALC_DONE = True
        return {"matches": n_upd, "teams": len(r_home)}
    finally:
        conn.close()


def recalc_team_elo_form():
    """Пост-майнотч перерахунок Elo та форми команд.

    Після того як ставка розрахувалась, а матч став завершеним (рахунок
    записано в канонічну logicbet.db), миттєво перераховується Elo обох
    команд і їх форма (останні 5). Тим самим веб ніколи не показує
    застарілу форму/рейтинг (фаворити з кількома перемогами — не аутсайдери).
    Це локальна копія логіки пайплайну recalculate_elo_from_history/main.py."""
    import sqlite3 as _sq
    from analytics import BettingAnalytics
    _an = BettingAnalytics(db)
    conn = _sq.connect(DATA_DB_PATH)
    _ensure_elo_split_cols(conn)  # Зміна A: гарантія колонок home/away_elo
    try:
        matches = conn.execute("""
            SELECT id, home_team_id, away_team_id, home_score, away_score
            FROM matches
            WHERE status IN ('FT','AET','PEN','FINISHED') AND elo_processed = 0
              AND home_score IS NOT NULL AND away_score IS NOT NULL
            ORDER BY date ASC
        """).fetchall()
        if not matches:
            return {"processed": 0}
        for m_id, h_id, a_id, hs, asc in matches:
            # Нова логіка: одна пара венюних каналів за стандартною формулою.
            # Домашній матч рухає ТІЛЬКИ home_elo господаря, виїзний —
            # ТІЛЬКИ away_elo гостя; загальний elo_rating одразу стає
            # середнім арифметичним двох венюних каналів кожної команди.
            hrow = conn.execute(
                "SELECT COALESCE(home_elo, elo_rating, 1500), "
                "COALESCE(away_elo, elo_rating, 1500) "
                "FROM teams WHERE id = ?", (h_id,)).fetchone()
            arow = conn.execute(
                "SELECT COALESCE(home_elo, elo_rating, 1500), "
                "COALESCE(away_elo, elo_rating, 1500) "
                "FROM teams WHERE id = ?", (a_id,)).fetchone()
            if not hrow or not arow:
                continue
            new_h_home, new_a_away = _an.update_elo(
                float(hrow[0]), float(arow[1]), int(hs), int(asc))
            dh = new_h_home - float(hrow[0])
            da = new_a_away - float(arow[1])
            conn.execute(
                "UPDATE teams SET home_elo = ?, elo_rating = ? WHERE id = ?",
                (round(new_h_home, 4),
                 round((new_h_home + float(hrow[1])) / 2.0, 4), h_id))
            conn.execute(
                "UPDATE teams SET away_elo = ?, elo_rating = ? WHERE id = ?",
                (round(new_a_away, 4),
                 round((float(arow[0]) + new_a_away) / 2.0, 4), a_id))
            conn.execute(
                "UPDATE matches SET h_elo_change = ?, a_elo_change = ? WHERE id = ?",
                (round(dh, 4), round(da, 4), m_id))
            for t_id in (h_id, a_id):
                conn.execute("UPDATE teams SET current_form = ? WHERE id = ?",
                             (_form_str_for_team(conn, t_id), t_id))
            conn.execute("UPDATE matches SET elo_processed = 1 WHERE id = ?",
                         (m_id,))
        conn.commit()
        return {"processed": len(matches)}
    finally:
        conn.close()


def settle_pending_bets():
    """Авто-розрахунок PENDING-ставок робочої БД проти фінальних рахунків
    канонічної logicbet.db. Викликається при кожному читанні /api/bets.

    Спершу — перерахунок Elo/форми команд (пост-майтч), потім повний сетлмент
    УСІХ прогнозів-маркетів ШІ (Завдання 3) і лише потім — сам сетлмент ставок
    користувача (див. recalc_team_elo_form / settle_ai_predictions).

    Порядок: ПОВНИЙ перерахунок роздільного Elo по історії (один раз за
    життя процесу) -> інкрементальні свіжі результати -> повний сетлмент
    маркетів ШІ -> сетлмент ставок користувача."""
    full_elo_recalc()
    recalc_team_elo_form()
    ai_res = settle_ai_predictions()

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
            return {"settled": 0, "wins": 0, "ai": ai_res}

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
    return {"settled": settled, "wins": wins, "ai": ai_res}


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
    (mid, date_str, league, status, hs, ascore, home, away, home_id, away_id) = row[:10]
    # Elo (для підсвічування фаворита в картці) — якщо присутній у рядку
    h_elo = row[10] if len(row) >= 11 else None
    a_elo = row[11] if len(row) >= 12 else None
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
        # актуальний Elo (для визначення фаворита в картці)
        "home_elo": round(float(h_elo), 1) if h_elo is not None else None,
        "away_elo": round(float(a_elo), 1) if a_elo is not None else None,
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
               t1.name, t2.name, m.home_team_id, m.away_team_id,
               t1.elo_rating, t2.elo_rating
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
    """Повертає ВСІ завершені матчі з LEFT JOIN user_bets"""
    settle_pending_bets()

    status_filter = request.args.get("status", "ALL").upper()
    where_clauses = ["m.status IN ('FT','AET','PEN','FINISHED')"]
    params = []

    if status_filter == "WON":
        where_clauses.append("ub.status = 'WON'")
    elif status_filter == "LOST":
        where_clauses.append("ub.status = 'LOST'")

    where_sql = " AND ".join(where_clauses)

    try:
        limit = min(max(int(request.args.get("limit", 300)), 1), 500)
    except (TypeError, ValueError):
        limit = 300
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    with db.get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM matches m LEFT JOIN user_bets ub ON m.id = ub.match_id WHERE " + where_sql,
            params).fetchone()[0]

        rows = conn.execute("""
            SELECT
              m.id, m.date, m.league, m.status, m.home_score, m.away_score,
              t1.name AS home, t2.name AS away,
              t1.id AS home_id, t2.id AS away_id,
              ub.id AS bet_id, ub.selection, ub.stake, ub.odd, ub.status AS bet_status, ub.profit
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            LEFT JOIN user_bets ub ON m.id = ub.match_id AND ub.status IN ('WON', 'LOST')
            WHERE """ + where_sql + """
            ORDER BY m.date DESC, m.id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        bets = []
        for row in rows:
            (mid, date_str, league, mstat, hs, ascore,
             home, away, home_tid, away_tid,
             bet_id, selection, stake, odd, bet_status, profit) = row

            label, key = status_info(mstat)
            kickoff = parse_dt(date_str)

            bet = None
            if bet_id is not None:
                bet = {
                    "id": bet_id,
                    "selection": selection,
                    "stake": float(stake or 0),
                    "odd": float(odd or 0),
                    "status": bet_status,
                    "profit": round(float(profit or 0), 2)
                }

            bets.append({
                "id": mid,
                "match": "%s — %s" % (home, away),
                # Окремі назви/id команд для КЛІКАБЕЛЬНОЇ Історії:
                # назва -> профіль команди (teamModal), рахунок -> деталі матчу.
                "home": home, "away": away,
                "home_id": home_tid, "away_id": away_tid,
                "league": league,
                "time": to_kyiv(kickoff).strftime("%d.%m %H:%M") if kickoff else "--:--",
                "match_status": label,
                "match_status_key": key,
                "score": "%s:%s" % (hs, ascore) if hs is not None and ascore is not None else None,
                "bet": bet,
            })

    next_offset = offset + len(bets)
    return jsonify({
        "bets": bets,
        "limit": limit,
        "offset": offset,
        "total": total,
        "has_more": next_offset < total,
        "next_offset": next_offset,
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
    try:
        t = conn.execute(
            "SELECT id, name, elo_rating, current_form, rank, points, "
            "home_elo, away_elo FROM teams WHERE id = ?",
            (team_id,)).fetchone()
    except sqlite3.OperationalError:
        # БД ще не мігрувала під роздільний Elo — деградуємо до загального,
        # тоді венюні бейджі просто не показуються у фронтенді.
        t = conn.execute(
            "SELECT id, name, elo_rating, current_form, rank, points, "
            "NULL, NULL FROM teams WHERE id = ?", (team_id,)).fetchone()
    if t is None:
        return None
    return {
        "id": t[0], "name": t[1],
        "elo": round(float(t[2] or 1500), 1),
        # Роздільний Elo (Зміна A): домашній канал господарів та виїзний
        # канал гостей для деталізації у профілі команди. Якщо колонки
        # порожні — підставляємо загальний рейтинг (поведінка як раніше).
        "home_elo": round(float(t[6] if t[6] is not None else (t[2] or 1500)), 1)
                    if t[6] is not None else None,
        "away_elo": round(float(t[7] if t[7] is not None else (t[2] or 1500)), 1)
                    if t[7] is not None else None,
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
