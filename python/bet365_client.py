"""BET365 / RAPIDAPI — НАКОПИЧУВАЛЬНИЙ КАЛЕНДАР (WEEKEND ACCUMULATOR, v30).

Модель бюджету: 50 запитів/тиждень: Пн 3, Вт 3, Ср 1, Чт 1, Пт 12, Сб 18, Нд 12.
(Ср-Чт — економія/накопичення; Пт-Нд — масований забір свіжих ліній.)

1 запит = 1 ЛІГА (EPL, La Liga, Serie A, Bundesliga, Ligue 1, єврокубки).
Базові маркет-вектори (1X2, ТБ/ТМ 2.5, ОЗ) зберігаються в `odds` з
fetched_at; де матч зіставлено за назвами — прив'язується match_id.
Лічильники бюджету — у `config` (ключі bet365_*), переживають рестарти.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

import requests

logger = logging.getLogger("logicbet.bet365")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] logicbet.bet365: %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

RAPID_BASE = os.environ.get(
    "BET365_RAPID_BASE", "https://bet36528.p.rapidapi.com")
RAPID_HOST = os.environ.get("BET365_RAPID_HOST", "bet36528.p.rapidapi.com")
RAPID_HEADER_KEY = os.environ.get(
    "BET365_RAPID_HEADER_KEY", "X-RapidAPI-Key")
RAPID_HEADER_HOST = os.environ.get(
    "BET365_RAPID_HEADER_HOST", "x-rapidapi-host")
TIMEOUT_SEC = float(os.environ.get("BET365_TIMEOUT_SEC", "15"))
LEAGUE_ENDPOINT = os.environ.get(
    "BET365_LEAGUE_ENDPOINT", "/v1/bet365/prematch")

WEEK_CAP = int(os.environ.get("BET365_WEEK_CAP", "50"))
# weekday(): Пн=0 .. Нд=6. Сума = 50 запитів/тиждень.
DAILY_PLAN = {0: 3, 1: 3, 2: 1, 3: 1, 4: 12, 5: 18, 6: 12}
if os.environ.get("BET365_DAILY_PLAN"):
    try:
        DAILY_PLAN = {int(k): int(v) for k, v in
                      json.loads(os.environ["BET365_DAILY_PLAN"]).items()}
    except Exception as e:                       # noqa: BLE001
        logger.error("BET365_DAILY_PLAN не розпарсив (%s) — дефолт", e)

# code -> (канонічна назва у matches.league, bet365 league_id)
LEAGUES = [
    ("EPL", "Premier League", 10041810),
    ("LALIGA", "La Liga", 10041760),
    ("SERIEA", "Serie A", 10041750),
    ("BUNDESLIGA", "Bundesliga", 10041710),
    ("LIGUE1", "Ligue 1", 10041700),
    ("UCL", "UEFA Champions League", 10041800),
    ("UEL", "UEFA Europa League", 10041790),
]
LEAGUE_NAMES = {code: name for code, name, _i in LEAGUES}

def load_league_ids():
    """{code: bet365_id} — дефолти перекриваються конфігом/env."""
    ids = {code: lid for code, _n, lid in LEAGUES}
    raw = os.environ.get("BET365_LEAGUE_IDS")
    if raw:
        try:
            ids.update({k: int(v) for k, v in json.loads(raw).items()})
        except Exception as e:                   # noqa: BLE001
            logger.error("BET365_LEAGUE_IDS не розпарсив (%s)", e)
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "api_config.json")
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            custom = (json.load(f).get("api_keys") or {}).get(
                "bet365_league_ids")
        if isinstance(custom, dict):
            ids.update({k: int(v) for k, v in custom.items()})
    except Exception:                            # noqa: BLE001
        pass
    return ids


def load_bet365_key():
    """Ключ RapidAPI: env -> data/api_config.json (rapidapi_generic)."""
    for env in ("BET365_RAPIDAPI_KEY", "RAPIDAPI_KEY"):
        k = os.environ.get(env)
        if k and k.strip() and k != "PLACEHOLDER_KEY":
            return k.strip()
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "api_config.json")
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            k = (json.load(f).get("api_keys") or {}).get("rapidapi_generic")
    except Exception as e:                       # noqa: BLE001
        logger.error("Не можу прочитати %s: %s", cfg, e)
        return None
    return k if (k and k != "PLACEHOLDER_KEY") else None


class Bet365Client:
    """Тонкий HTTP-клієнт до bet365 RapidAPI з x-rapidapi-заголовками."""

    def __init__(self, api_key):
        self.api_key = api_key or ""
        self.base = RAPID_BASE.rstrip("/")
        self.headers = {
            RAPID_HEADER_HOST: RAPID_HOST,
            RAPID_HEADER_KEY: self.api_key,
        }
        self.last_error_code = None

    def _make_request(self, endpoint, params):
        url = "%s%s" % (self.base, endpoint)
        self.last_error_code = None
        try:
            resp = requests.get(url, headers=self.headers, params=params,
                                timeout=TIMEOUT_SEC)
            if resp.status_code == 429:
                self.last_error_code = "RATE_LIMIT"
                logger.error("Bet365: HTTP 429 Too Many Requests")
                return None
            if resp.status_code >= 400:
                self.last_error_code = "HTTP_%s" % resp.status_code
                logger.error("Bet365: HTTP %s on %s: %s",
                             resp.status_code, endpoint, resp.text[:300])
                return None
            data = resp.json()
            if isinstance(data, dict) and data.get("errors"):
                self.last_error_code = "BUSINESS_ERROR"
                logger.error("Bet365 Business Error: %s", data["errors"])
                return None
            return data
        except requests.RequestException as e:
            self.last_error_code = "NETWORK_ERROR"
            logger.error("Bet365 network error (%s): %s", endpoint, e)
            return None
        except ValueError as e:
            self.last_error_code = "BAD_JSON"
            logger.error("Bet365 bad JSON (%s): %s", endpoint, e)
            return None


def _f(x):
    """float або None — без виключень."""
    try:
        v = float(x)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None

def parse_league_payload(payload, league_code):
    """Розбір відповіді ліги -> [(home, away, market, selection, odd), ...].

    Гнучко шукає 1X2 / ТБ-ТМ 2.5 / ОЗ у типових вкладеннях RapidAPI bet365
    (odds.prematch.{1,X,2}, goals/overUnder 2.5, btts yes/no). Аномалії ->
    warning/error логи, парсинг не падає.
    """
    rows = []
    if payload is None:
        logger.error("%s: payload порожній (None)", league_code)
        return rows
    events = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                events.extend(item.get("events") or [item])
    elif isinstance(payload, dict):
        events = (payload.get("events") or payload.get("fixtures")
                  or payload.get("data") or [payload])

    for ev in events:
        if not isinstance(ev, dict):
            continue
        home = str(ev.get("home") or ev.get("homeTeam") or
                   (ev.get("teams") or {}).get("home") or "")[:60]
        away = str(ev.get("away") or ev.get("awayTeam") or
                   (ev.get("teams") or {}).get("away") or "")[:60]
        odds = ev.get("odds") or ev.get("Odds") or {}
        prem = odds.get("prematch") or odds.get("Prematch") or odds
        if not isinstance(prem, dict):
            prem = {}

        map_1x2 = None
        for k in ("1X2", "FullTimeResult", "full_time", "match_winner"):
            if isinstance(prem.get(k), dict):
                map_1x2 = prem[k]
                break
        if map_1x2 is None and all(_f(prem.get(x)) for x in ("1", "X", "2")):
            map_1x2 = {"1": prem.get("1"), "X": prem.get("X"),
                       "2": prem.get("2")}
        if isinstance(map_1x2, dict):
            for key, canon in (("1", "П1"), ("home", "П1"), ("X", "X"),
                               ("draw", "X"), ("2", "П2"), ("away", "П2")):
                odd = _f(map_1x2.get(key))
                if odd:
                    rows.append((home, away, "1X2", canon, odd))

        tot = prem.get("goals") or prem.get("totals") or \
            prem.get("overUnder") or {}
        if isinstance(tot, dict):
            node = tot.get("2.5")
            if isinstance(node, dict):
                o25, u25 = _f(node.get("over")), _f(node.get("under"))
            else:
                o25, u25 = _f(tot.get("over2.5")), _f(tot.get("under2.5"))
            if o25:
                rows.append((home, away, "Total Goals", "ТБ 2.5", o25))
            if u25:
                rows.append((home, away, "Total Goals", "ТМ 2.5", u25))

        bt = prem.get("btts") or prem.get("bothTeamsToScore") or \
            prem.get("bothTeamsScore") or {}
        if isinstance(bt, dict):
            yes = _f(bt.get("yes") or bt.get("Yes"))
            no = _f(bt.get("no") or bt.get("No"))
            if yes:
                rows.append((home, away, "BTTS", "ОЗ - Так", yes))
            if no:
                rows.append((home, away, "BTTS", "ОЗ - Ні", no))

    if not rows:
        logger.warning("%s: не знайдено жодного маркет-вектора в payload",
                       league_code)
    else:
        logger.info("%s: розпарсено %d маркет-векторів",
                    league_code, len(rows))
    return rows

def get_budget(get_config):
    """(used_day, day_key, day_cap, used_week, week_key) з config-таблиці.

    Денний ліміт — DAILY_PLAN[weekday]; тиждень — ISO-тиждень. При зміні
    доби/тижня лічильники автоматично скидаються.
    """
    now = datetime.now(timezone.utc)
    wd = now.weekday()                          # Пн=0 .. Нд=6
    day_key = now.strftime("%Y-%m-%d")
    week_key = "%d-W%02d" % now.isocalendar()[:2]
    day_cap = int(DAILY_PLAN.get(wd, 0))

    ud = int(get_config("bet365_day_used") or 0)
    if get_config("bet365_day") != day_key:
        ud = 0
    uw = int(get_config("bet365_week_used") or 0)
    if get_config("bet365_week") != week_key:
        uw = 0
    return ud, day_key, day_cap, uw, week_key


def save_budget(set_config, day_key, week_key, used_day, used_week):
    set_config("bet365_day", day_key)
    set_config("bet365_day_used", str(used_day))
    set_config("bet365_week", week_key)
    set_config("bet365_week_used", str(used_week))


def accumulator_plan(get_config):
    """План/стан бюджету на сьогодні — для логів, cron і діагностики."""
    ud, day_key, day_cap, uw, week_key = get_budget(get_config)
    return {"weekday": datetime.now(timezone.utc).weekday(),
            "day_key": day_key, "day_cap": day_cap, "day_used": ud,
            "week_key": week_key, "week_cap": WEEK_CAP, "week_used": uw,
            "allowance": max(0, min(day_cap - ud, WEEK_CAP - uw))}


def _cfg_get(conn, key):
    row = conn.execute(
        "SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _cfg_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                 (key, str(value)))


def _ensure_odds_columns(cur):
    """Міграція: odds.league / odds.fetched_at (для старих БД)."""
    cols = {r[1] for r in cur.execute("PRAGMA table_info(odds)").fetchall()}
    if "league" not in cols:
        cur.execute("ALTER TABLE odds ADD COLUMN league TEXT")
        logger.info("odds: додано колонку league")
    if "fetched_at" not in cols:
        cur.execute("ALTER TABLE odds ADD COLUMN fetched_at TEXT")
        logger.info("odds: додано колонку fetched_at")

def _match_id_by_names(cur, home, away):
    """match_id майбутнього матчу за парамою назв команд (або None)."""
    if not home or not away:
        return None
    r = cur.execute("""
        SELECT m.id FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE lower(t1.name) = lower(?) AND lower(t2.name) = lower(?)
          AND m.status IN ('NS', 'TBD')
        ORDER BY m.date DESC LIMIT 1
    """, (home, away)).fetchone()
    return r[0] if r else None


def store_vectors(cur, league_code, vectors, now_iso):
    """Зберігає маркет-вектори в `odds` (з league та fetched_at).

    Матч-рівневі записи (match_id знайдено) — INSERT OR REPLACE по PK
    (свіжий кф замінює старий); лігові знімки (match_id NULL) — звичайний
    INSERT: UNIQUE не дедуплікує NULL, а потрібна історія знімків.
    """
    n_match = n_league = 0
    for home, away, market, selection, odd in vectors:
        mid = _match_id_by_names(cur, home, away)
        if mid is not None:
            cur.execute("""
                INSERT OR REPLACE INTO odds
                    (match_id, league, market, selection, opening_odd,
                     closing_odd, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (mid, league_code, market, selection, odd, odd, now_iso))
            n_match += 1
        else:
            cur.execute("""
                INSERT INTO odds
                    (match_id, league, market, selection, opening_odd,
                     closing_odd, fetched_at)
                VALUES (NULL, ?, ?, ?, ?, ?, ?)
            """, (league_code, market, selection, odd, odd, now_iso))
            n_league += 1
    return n_match, n_league

def sync_accumulator(db_path, get_config=None, set_config=None, force=False):
    """ГОЛОВНА ТОЧКА ВХОДУ v30: накопичувальний ліговий забір.

    • добовий ліміт з DAILY_PLAN (Пн3 Вт3 Ср1 Чт1 Пт12 Сб18 Нд12),
      тижневий — 50; лічильники в `config` (bet365_day/week*).
    • 1 запит = 1 ліга; ліги беруться циклічно зі зсувом від дня тижня.
    • force=True — ігнорує денний ліміт (тижневий лишається).
    Повертає dict-summary або None (нема ключа / бюджет вичерпано).
    """
    api_key = load_bet365_key()
    if not api_key:
        logger.error("Немає ключа RapidAPI (rapidapi_generic) — пропускаю sync")
        return None

    own = False
    if get_config is None or set_config is None:
        _conn = sqlite3.connect(db_path)
        get_config = lambda k: _cfg_get(_conn, k)        # noqa: E731
        set_config = lambda k, v: _cfg_set(_conn, k, v)  # noqa: E731
        own = True

    plan = accumulator_plan(get_config)
    allowance = plan["allowance"] if not force else \
        max(0, WEEK_CAP - plan["week_used"])
    if allowance <= 0:
        logger.info("Bet365 бюджет вичерпано: day=%d/%d week=%d/%d",
                    plan["day_used"], plan["day_cap"],
                    plan["week_used"], WEEK_CAP)
        if own:
            _conn.close()
        return {"skipped": True, **plan}

    # Циклічний зсув списку ліг від дня тижня — рівномірне покриття.
    wd = plan["weekday"]
    ordered = LEAGUES[wd % len(LEAGUES):] + LEAGUES[:wd % len(LEAGUES)]
    todo = ordered[:allowance]

    ids = load_league_ids()
    client = Bet365Client(api_key)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    _ensure_odds_columns(cur)

    done = vectors_saved = m_rows = l_rows = 0
    failed = []
    for code, _name, _def_id in todo:
        lid = ids.get(code)
        if not lid:
            failed.append({"league": code, "reason": "no_league_id"})
            continue
        logger.info("Bet365: запит ліги %s (id=%s)...", code, lid)
        data = client._make_request(
            LEAGUE_ENDPOINT, {"sport": "1", "league_id": lid})
        done += 1                                    # запит витрачено
        if data is None:
            failed.append({"league": code,
                           "reason": client.last_error_code})
            continue
        vectors = parse_league_payload(data, code)
        nm, nl = store_vectors(cur, code, vectors, now_iso)
        m_rows += nm
        l_rows += nl
        vectors_saved += len(vectors)

    ud, day_key, day_cap, uw, week_key = (
        plan["day_used"], plan["day_key"], plan["day_cap"],
        plan["week_used"], plan["week_key"])
    save_budget(set_config, day_key, week_key, ud + done, uw + done)
    conn.commit()
    cur.close()
    conn.close()
    if own:
        _conn.close()

    summary = {"leagues_done": done, "vectors": vectors_saved,
               "match_rows": m_rows, "league_rows": l_rows,
               "failed": failed,
               "budget_day": "%d/%d" % (ud + done, day_cap),
               "budget_week": "%d/%d" % (uw + done, WEEK_CAP)}
    logger.info("Bet365 accumulator: %s", summary)
    return summary


# Сумісність зі старими імпортами (веб до v30 викликав це ім'я).
sync_odds_for_new_matches = sync_accumulator


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(
        description="Bet365 weekend accumulator sync")
    ap.add_argument("--force", action="store_true",
                    help="ігнорувати денний ліміт (тижневий лишається)")
    ap.add_argument("--plan", action="store_true",
                    help="лише показати план бюджету на сьогодні")
    a = ap.parse_args()
    _p = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "godot_app", "logicbet.db")
    if a.plan:
        _c = sqlite3.connect(_p)
        print(json.dumps(accumulator_plan(
            lambda k: _cfg_get(_c, k)), ensure_ascii=False, indent=2))
        _c.close()
    else:
        print(json.dumps(sync_accumulator(_p, force=a.force),
                         ensure_ascii=False, indent=2))
