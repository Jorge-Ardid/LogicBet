"""ДІАГНОСТИКА ТА АВТО-ПАРСИНГ СТАТИСТИКИ ЗАВЕРШЕНИХ МАТЧІВ.

Фонове довантаження детальної статистики (кутові, ЖК/ЧК, xG, удари,
володіння) для щойно завершених матчів. Створено тому, що пайплайн
(main.py --force) біжить лише двічі на добу, а старий sync_match_stats
мітив матч як \"stats_fetched\" навіть коли джерело ще НЕ виклало цифри —
у результаті карти завершених матчів назавжди лишалися з нулями.

Правила циклу оновлення (retry mechanism):
  • перша спроба — не раніше ніж через MIN_AGE_MINUTES хвилин після
    фінального свистка (джерело часто публікує статистику із запізненням);
  • повторні спроби кожні REFRESH_INTERVAL_SEC секунд (5-15 хвилин),
    поки вікно MAX_AGE_HOURS не закриється;
  • повторюються ТАКОЖ матчі, заблоковані раніше з нулями (легасі-баг);
  • денний ліміт запитів DAILY_BUDGET захищає безкоштовну квоту API.

Парсер пише ДЕТАЛЬНІ warning/error логи на будь-який збій мапінгу."""
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("logicbet.stats")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] logicbet.stats: %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

# --- Налаштування циклу (можна перекривати env) ---
REFRESH_INTERVAL_SEC = int(os.environ.get("LOGICBET_STATS_SWEEP_SEC", "600"))
MIN_AGE_MINUTES = float(os.environ.get("LOGICBET_STATS_MIN_AGE_MIN", "10"))
MAX_AGE_HOURS = float(os.environ.get("LOGICBET_STATS_MAX_AGE_HOURS", "48"))
MAX_PER_SWEEP = int(os.environ.get("LOGICBET_STATS_MAX_PER_SWEEP", "6"))
DAILY_BUDGET = int(os.environ.get("LOGICBET_STATS_DAILY_BUDGET", "60"))

STAT_TYPE_MAP = {
    "corner kicks": "corners",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "shots on goal": "shots_on",
    "shots off goal": "shots_off",
    "expected_goals": "xg",
    "expected goals": "xg",
    "ball possession": "possession",
}
CORE_FIELDS = ("corners", "yellow_cards", "shots_on")


def load_api_key():
    """API-ключ: env API_FOOTBALL_KEY -> data/api_config.json -> None."""
    k = os.environ.get("API_FOOTBALL_KEY")
    if k and k.strip() and k != "PLACEHOLDER_KEY":
        return k.strip()
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "api_config.json")
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            k = (json.load(f).get("api_keys") or {}).get("api_football")
    except Exception as e:                       # noqa: BLE001
        logger.error("Не можу прочитати %s: %s", cfg, e)
        return None
    return k if (k and k != "PLACEHOLDER_KEY") else None


def _parse_utc_naive(value):
    """ISO-рядок -> naive-UTC datetime або None."""
    if not value:
        return None
    txt = str(value).strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(txt, fmt)
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None


def parse_fixture_statistics(stats_data, match_id):
    """Розбір відповіді fixtures/statistics -> dict полів матчу.

    Повертає dict (можливо, частковий) або None, коли структура
    непридатна для збереження (тоді матч лишається у черзі retry).
    Кожен аномальний елемент пишеться в лог warning/error."""
    if not isinstance(stats_data, list) or len(stats_data) < 2:
        logger.warning("match %s: очікується масив із 2 команд-сторон, "
                       "отримано %r — статистика ще не викладена?",
                       match_id, type(stats_data).__name__)
        return None

    parsed = {}
    known = []
    unknown_types = set()
    null_values = []
    sides_ok = 0
    for idx, team_stats in enumerate(stats_data[:2]):
        suffix = "_h" if idx == 0 else "_a"
        side = "home" if idx == 0 else "away"
        team_name = ((team_stats or {}).get("team") or {}).get("name")
        stats_list = (team_stats or {}).get("statistics")
        if not isinstance(stats_list, list) or not stats_list:
            logger.warning(
                "match %s side=%s(%s): 'statistics' порожній/відсутній — "
                "сторона залишиться нулями", match_id, side, team_name)
            continue
        sides_ok += 1
        for stat in stats_list:
            t_raw = stat.get("type")
            val = stat.get("value")
            t = str(t_raw or "").strip().lower()
            field = STAT_TYPE_MAP.get(t)
            if field is None:
                if t:
                    unknown_types.add(t_raw)
                continue
            known.append(field + suffix)
            if val is None:
                null_values.append((side, t_raw))
                continue
            sval = str(val).replace("%", "").strip()
            try:
                parsed[field + suffix] = (
                    float(sval) if "." in sval else int(float(sval)))
            except (TypeError, ValueError):
                logger.error(
                    "match %s side=%s: НЕ розпарсив %s=%r для поля %s%s",
                    match_id, side, t_raw, val, field, suffix)

    for ut in sorted(str(u) for u in unknown_types):
        logger.warning("match %s: невідомий тип статистики %r — "
                       "розшир мапінг STAT_TYPE_MAP?", match_id, ut)
    for side, t_raw in null_values:
        logger.warning("match %s side=%s: %s має value=None — "
                       "джерело не завантажило цифру", match_id, side, t_raw)
    missing_core = [f for f in CORE_FIELDS
                    if not any(k.startswith(f) for k in parsed)]
    if missing_core and sides_ok:
        logger.warning("match %s: відсутні КЛЮЧОВІ поля %s після парсингу",
                       match_id, missing_core)
    if sides_ok == 0 or (not parsed and not null_values):
        return None
    return parsed


def store_stats(conn, match_id, stats):
    """Запис розпарсених цифр у канонічну БД (та сама схема, що й
    database.update_match_stats, але по явному з'єднанню)."""
    conn.execute("""
        UPDATE matches SET
            corners_h=?, corners_a=?,
            yellow_cards_h=?, yellow_cards_a=?,
            red_cards_h=?, red_cards_a=?,
            shots_on_h=?, shots_on_a=?,
            shots_off_h=?, shots_off_a=?,
            xg_h=?, xg_a=?,
            possession_h=?, possession_a=?,
            stats_fetched=1
        WHERE id=?
    """, (
        stats.get("corners_h", 0), stats.get("corners_a", 0),
        stats.get("yellow_cards_h", 0), stats.get("yellow_cards_a", 0),
        stats.get("red_cards_h", 0), stats.get("red_cards_a", 0),
        stats.get("shots_on_h", 0), stats.get("shots_on_a", 0),
        stats.get("shots_off_h", 0), stats.get("shots_off_a", 0),
        stats.get("xg_h", 0.0), stats.get("xg_a", 0.0),
        stats.get("possession_h", 50), stats.get("possession_a", 50),
        match_id))


def stats_are_missing(conn, match_id):
    """Чи фактично відсутня корисна статистика в матчі (легасі-нули)."""
    row = conn.execute(
        "SELECT COALESCE(corners_h,0)+COALESCE(corners_a,0)"
        "+COALESCE(yellow_cards_h,0)+COALESCE(yellow_cards_a,0)"
        "+COALESCE(shots_on_h,0)+COALESCE(shots_on_a,0) FROM matches "
        "WHERE id=?", (match_id,)).fetchone()
    return not row or row[0] == 0


def _day_used(get_config):
    """Скільки запитів на статистику вже витрачено СЬОГОДНІ."""
    if not get_config:
        return 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if get_config("stats_api_day") != today:
        return 0
    try:
        return int(get_config("stats_api_used") or 0)
    except (TypeError, ValueError):
        return 0


def daily_budget_left(get_config):
    """Скільки запитів лишилось у денному бюджеті."""
    return max(0, DAILY_BUDGET - _day_used(get_config))


def refresh_missing_stats(data_db_path, get_config=None, set_config=None,
                          force=False, api_key=None,
                          max_matches=None, min_age_minutes=None,
                          max_age_hours=None):
    """Головний цикл авто-парсингу. Повертає summary-dict.

    Кандидати: завершені матчі останніх MAX_AGE_HOURS годин з remote_id,
    у яких статистика відсутня АБО дорівнює нулям (легасі-баг блокування).
    Перша спроба не раніше MIN_AGE_MINUTES після фінального свистка,
    бо джерело публікує детальні цифри із запізненням (5-15 хв)."""
    api_key = api_key or load_api_key()
    if not api_key:
        logger.warning("API-ключ відсутній (env API_FOOTBALL_KEY / "
                       "data/api_config.json) — автопарсинг вимкнено")
        return {"skipped": "no_api_key"}

    max_matches = int(max_matches or MAX_PER_SWEEP)
    min_age = float(min_age_minutes if min_age_minutes is not None
                    else MIN_AGE_MINUTES)
    max_age = float(max_age_hours if max_age_hours is not None
                    else MAX_AGE_HOURS)

    used = _day_used(get_config)
    remaining_today = DAILY_BUDGET - used
    if remaining_today <= 0:
        logger.warning("Денний ліміт запитів статистики вичерпано "
                       "(%d/%d) — цикл пропущено", used, DAILY_BUDGET)
        return {"skipped": "daily_budget_exhausted"}

    conn = sqlite3.connect(data_db_path)
    fetched, failed, too_fresh, too_old = [], [], [], []
    attempts = 0
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    limit = min(max_matches, remaining_today)
    try:
        rows = conn.execute("""
            SELECT m.id, m.remote_id,
                   COALESCE(m.finished_at, m.date) AS fin_ts,
                   COALESCE(m.corners_h,0)+COALESCE(m.corners_a,0)
                   +COALESCE(m.yellow_cards_h,0)+COALESCE(m.yellow_cards_a,0)
                   +COALESCE(m.shots_on_h,0)+COALESCE(m.shots_on_a,0) AS sig
            FROM matches m
            WHERE m.status IN ('FT','AET','PEN','FINISHED')
              AND m.remote_id IS NOT NULL
              AND (m.stats_fetched = 0 OR sig = 0)
            ORDER BY fin_ts DESC LIMIT 40
        """).fetchall()

        for m_id, r_id, fin_ts, _sig in rows:
            if attempts >= limit:
                break
            ts = _parse_utc_naive(fin_ts)
            age_min = ((now_utc - ts).total_seconds() / 60.0
                       if ts else max_age * 60.0 + 1)
            if age_min < min_age:
                too_fresh.append(m_id)      # retry вікно ще не відкрилось
                continue
            if age_min > max_age * 60.0:
                too_old.append(m_id)        # вікно 24-48 годин закрите
                continue

            attempts += 1
            logger.info("match %s (remote=%s, %.0f хв після свистка): "
                        "завантажую детальну статистику…",
                        m_id, r_id, age_min)
            try:
                from api_client import APIFootballClient
                data = APIFootballClient(api_key).fetch_match_statistics(
                    int(r_id))
                parsed = parse_fixture_statistics(data, m_id)
            except Exception as e:                      # noqa: BLE001
                logger.error("match %s: виняток завантаження/парсингу: %s",
                             m_id, e)
                failed.append({"match": m_id, "remote": r_id,
                               "reason": "exception: %s" % e})
                continue
            if parsed is None:
                # ЧЕСНО лишаємо у черзі retry — НЕ блокуємо назавжди!
                failed.append({"match": m_id, "remote": r_id,
                               "reason": "not_published_yet"})
                continue
            store_stats(conn, m_id, parsed)
            conn.commit()
            fetched.append({
                "match": m_id,
                "corners": [parsed.get("corners_h", 0),
                            parsed.get("corners_a", 0)],
                "yellows": [parsed.get("yellow_cards_h", 0),
                            parsed.get("yellow_cards_a", 0)],
                "xg": [parsed.get("xg_h"), parsed.get("xg_a")]})
    finally:
        conn.close()

    if set_config and attempts:
        set_config("stats_api_day",
                   datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        set_config("stats_api_used", str(used + attempts))

    if fetched:
        logger.info("Цикл завершено: ОНОВЛЕНО %d (%s), не готово %d, "
                    "занадто свіжі/старі %d/%d",
                    len(fetched), [f["match"] for f in fetched],
                    len(failed), len(too_fresh), len(too_old))
    else:
        logger.info("Цикл без оновлень: candidates=%d, not_ready=%d, "
                    "fresh=%d, old=%d, budget_used=%d/%d",
                    len(rows), len(failed), len(too_fresh), len(too_old),
                    used + attempts, DAILY_BUDGET)

    return {"fetched": fetched, "failed": failed,
            "too_fresh": too_fresh, "too_old": too_old,
            "attempts": attempts, "budget_used": used + attempts,
            "budget_limit": DAILY_BUDGET}


