"""БЕТ365 / RAPIDAPI КЛІЄНТ КОЕФІЦІЄНТІВ З ЖОРСТКИМ БЮДЖЕТОМ.

Завдання:
  1. Запити йдуть на RapidAPI хост `bet36528.p.rapidapi.com` з заголовками
     `X-RapidAPI-Key` та `x-rapidapi-host`.
  2. Жорстка економія ліміту (200 запитів/міс):
       • максимум BET365_DAY_CAP запитів на добу (за замовчуванням 5-6);
       • коефіцієнти запитуються ВИКЛЮЧНО для нових/майбутніх матчів;
       • лише 1 запит per match — якщо для матчу вже є рядки в `odds`,
         повторний запит НІКОЛИ не робиться;
       • отримані коефіцієнти зберігаються в локальну `odds` таблицю
         канонічної БД (godot_app/logicbet.db).

Денний і місячний лічильники прозоро зберігаються в `config` таблиці
(ключі bet365_*) тієї ж БД, тому бюджет переживає рестарти процесу.
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

# --- Налаштування (можна перекривати env) ---
RAPID_BASE = os.environ.get(
    "BET365_RAPID_BASE", "https://bet36528.p.rapidapi.com")
RAPID_HOST = os.environ.get("BET365_RAPID_HOST", "bet36528.p.rapidapi.com")
RAPID_HEADER_KEY = os.environ.get(
    "BET365_RAPID_HEADER_KEY", "X-RapidAPI-Key")
RAPID_HEADER_HOST = os.environ.get("BET365_RAPID_HEADER_HOST", "x-rapidapi-host")
TIMEOUT_SEC = float(os.environ.get("BET365_TIMEOUT_SEC", "15"))

DAY_CAP = int(os.environ.get("BET365_DAY_CAP", "6"))        # 5-6/добу
MONTH_CAP = int(os.environ.get("BET365_MONTH_CAP", "200"))  # 200/міс
MAX_PER_SWEEP = int(os.environ.get("BET365_MAX_PER_SWEEP", "5"))


def load_bet365_key():
    """Ключ RapidAPI: env BET365_RAPIDAPI_KEY / RAPIDAPI_KEY ->
    data/api_config.json (rapidapi_generic) -> None."""
    for env in ("BET365_RAPIDAPI_KEY", "RAPIDAPI_KEY"):
        k = os.environ.get(env)
        if k and k.strip() and k != "PLACEHOLDER_KEY":
            return k.strip()
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "api_config.json")
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            k = (json.load(f).get("api_keys") or {}).get("rapidapi_generic")
    except Exception as e:                          # noqa: BLE001
        logger.error("Не можу прочитати %s: %s", cfg, e)
        return None
    return k if (k and k != "PLACEHOLDER_KEY") else None
def get_budget(get_config):
    """(used_today, used_month, today, month_key) з config таблиці."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    ut = int(get_config("bet365_day_used") or 0)
    um = int(get_config("bet365_month_used") or 0)
    if get_config("bet365_day") != today:
        ut = 0                                 # нова доба -> скинути денний
    if get_config("bet365_month") != month:
        um = 0                                 # новий місяць -> скинути
    return ut, um, today, month


def _save_budget(set_config, today, month, used_today, used_month):
    set_config("bet365_day", today)
    set_config("bet365_day_used", str(used_today))
    set_config("bet365_month", month)
    set_config("bet365_month_used", str(used_month))


def parse_odds_payload(payload, match_id):
    """Розбір відповіді bet365/RapidAPI -> список рядків `odds`.

    Типова структура RapidAPI bet365:
        [{ "events": [ { "id": ..., "home": "..", "away": "..",
              "odds": { "prematch": { "1": 1.85, "X": 3.4, "2": 4.2 } } } ]}]
    Гнучко шукаємо 1X2 у різних вкладеннях. Невдачі -> warning/error лог.
    """
    rows = []                                 # (match_id, market, sel, odd)
    if payload is None:
        logger.error("match %s: payload порожній (None)", match_id)
        return rows
    events = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                events.extend(item.get("events") or [item])
    elif isinstance(payload, dict):
        events = payload.get("events") or [payload]

    found_any = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        odds = ev.get("odds") or ev.get("Odds") or {}
        prem = odds.get("prematch") or odds.get("Prematch") or odds
        if not isinstance(prem, dict):
            prem = {}
        map_1x2 = None
        for k in ("1X2", "FullTimeResult", "full_time", "match_winner"):
            if isinstance(prem.get(k), dict):
                map_1x2 = prem[k]
                break
        if map_1x2 is None and any(
                "1" in str(kk).upper() or "X" in str(kk).upper()
                for kk in list(prem.keys())[:6]):
            map_1x2 = prem
        if isinstance(map_1x2, dict):
            found_any = True
            for sel, odd in map_1x2.items():
                try:
                    odd = float(odd)
                except (TypeError, ValueError):
                    logger.warning("match %s: кф %r не число — пропускаю",
                                   match_id, odd)
                    continue
                rows.append((match_id, "1X2", str(sel).upper(), odd))
    if not found_any and not rows:
        logger.warning("match %s: не знайдено жодного 1X2 в payload", match_id)
    else:
        logger.info("match %s: розпарсено %d рядків 1X2 з bet365",
                    match_id, len(rows))
    return rows


def has_odds(conn, match_id):
    """Чи має матч уже збережені коефіцієнти? (ніколи не перезапитуємо.)"""
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM odds WHERE match_id = ? LIMIT 1", (match_id,))
    return cur.fetchone() is not None


def fetch_match_odds(client, remote_id):
    """Один запит коефіцієнтів для конкретного remote-матчу."""
    endpoint = os.environ.get("BET365_ODDS_ENDPOINT", "/v1/bet365/prematch")
    params = {"sport": "1", "event_id": remote_id}
    return client._make_request(endpoint, params)


def store_odds(conn, match_id, rows):
    """INSERT OR IGNORE рядків в `odds` (PK match_id/market/selection)."""
    cur = conn.cursor()
    n = 0
    for match_id_, market, sel, odd in rows:
        cur.execute(
            "INSERT OR IGNORE INTO odds (match_id, market, selection,"
            " opening_odd, closing_odd) VALUES (?,?,?,?,?)",
            (match_id_, market, sel, odd, odd))
        n += 1
    return n


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
        url = f"{self.base}{endpoint}"
        self.last_error_code = None
        try:
            resp = requests.get(url, headers=self.headers, params=params,
                                timeout=TIMEOUT_SEC)
            if resp.status_code == 429:
                self.last_error_code = "RATE_LIMIT"
                logger.error("Bet365: HTTP 429 Too Many Requests")
                return None
            if resp.status_code >= 400:
                self.last_error_code = f"HTTP_{resp.status_code}"
                logger.error("Bet365: HTTP %s on %s: %s",
                             resp.status_code, endpoint,
                             resp.text[:300])
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
def sync_odds_for_new_matches(db_path, get_config=None, set_config=None):
    """ГОЛОВНА ТОЧКА ВХОДУ: оновлення коефіцієнтів для нових матчів.

    Правила:
      • жорсткий бюджет (день + місяць), прозоро в `config`;
      • бере ТІЛЬКИ майбутні (NS) матчі без наявних коефіцієнтів;
      • на кожен — рівно 1 запит; повторно ніколи не питає;
      • результат зберігається в `odds`; budget оновлюється прозоро.

    Повертає dict-summary або None (бюджет вичерпано / нема ключа).
    """
    api_key = load_bet365_key()
    if not api_key:
        logger.error("Немає ключа RapidAPI (rapidapi_generic) — пропускаю sync")
        return None

    own_cfg = False
    if get_config is None or set_config is None:
        cur = sqlite3.connect(db_path)
        cfg = {"cur": cur}
        get_config = lambda k: _cfg_get(cfg, k)          # noqa: E731
        set_config = lambda k, v: _cfg_set(cfg, k, v)    # noqa: E731
        own_cfg = True
    else:
        cur = sqlite3.connect(db_path)

    used_today, used_month, today, month = get_budget(get_config)
    allowance = min(DAY_CAP - used_today, MONTH_CAP - used_month,
                    MAX_PER_SWEEP)
    if allowance <= 0:
        logger.info("Bet365 бюджет вичерпано: day=%d/%d month=%d/%d",
                    used_today, DAY_CAP, used_month, MONTH_CAP)
        cur.close()
        return {"skipped": True, "budget_day": used_today,
                "budget_day_cap": DAY_CAP, "budget_month": used_month,
                "budget_month_cap": MONTH_CAP}

    rows = cur.execute(
        """
        SELECT m.id, m.remote_id
        FROM matches m
        WHERE m.status IN ('NS','TBD')
          AND m.remote_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM odds o WHERE o.match_id = m.id)
          AND date(m.date) >= date('now')
        ORDER BY m.date ASC
        LIMIT ?
        """, (allowance * 4,)).fetchall()

    client = Bet365Client(api_key)
    attempts, fetched, failed = 0, [], []
    for m_id, r_id in rows:
        if attempts >= allowance:
            break
        if has_odds(cur, m_id):                    # вже є — не питаємо
            continue
        attempts += 1
        logger.info("Bet365 match %s (remote=%s): запит коефіцієнтів…",
                    m_id, r_id)
        data = fetch_match_odds(client, int(r_id))
        if data is None:
            failed.append({"match": m_id, "reason": client.last_error_code})
            continue
        parsed = parse_odds_payload(data, m_id)
        if not parsed:
            failed.append({"match": m_id, "reason": "no_1x2_parsed"})
            continue
        store_odds(cur, m_id, parsed)
        fetched.append(m_id)

    _save_budget(set_config, today, month,
                 used_today + attempts, used_month + attempts)
    cur.commit()
    cur.close()

    logger.info(
        "Bet365 sync: fetched=%d, failed=%d, budget(day)=%d/%d, budget(month)=%d/%d",
        len(fetched), len(failed), used_today + attempts, DAY_CAP,
        used_month + attempts, MONTH_CAP)
    return {"fetched": fetched, "failed": failed, "attempts": attempts,
            "budget_day": used_today + attempts, "budget_day_cap": DAY_CAP,
            "budget_month": used_month + attempts,
            "budget_month_cap": MONTH_CAP}


def _cfg_get(cfg, key):
    row = cfg["cur"].execute(
        "SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _cfg_set(cfg, key, value):
    cfg["cur"].execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, str(value)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _p = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "godot_app", "logicbet.db")
    print(json.dumps(sync_odds_for_new_matches(_p),
                     ensure_ascii=False, indent=2))