# -*- coding: utf-8 -*-
"""v5 «Market Value EV».

Вибирає варіант з найбільшим очікуваним значенням (EV = prob·odd − 1)
серед усіх трьох за допомогою букмекерських коефіцієнтів. Модель ймовірність —
це Elo-expectancy (v1), коефіцієнти — реальні. Сторве ходи, коли немає
коефіцієнтів.
"""
import math

ID = "outcomes_v5"
NAME = "Market Value EV"
SECTOR = "outcomes"


def _elo_exp(d):
    return 1.0 / (1.0 + 10.0 ** (-d / 400.0))


def predict(ctx):
    odds = ctx.get("odds") or {}
    if not all(odds.get(s) for s in ("П1", "X", "П2")):
        return None
    p_home = _elo_exp((ctx.get("home_elo") or 1500.0) - (ctx.get("away_elo") or 1500.0))
    px = max(0.12, min(0.30, 0.27 - 0.0003 * abs(
        (ctx.get("home_elo") or 1500.0) - (ctx.get("away_elo") or 1500.0))))
    base = {
        "П1": (1 - px) * p_home,
        "X": px,
        "П2": (1 - px) * (1 - p_home),
    }
    ev = {s: base[s] * float(odds[s]) - 1.0 for s in base}
    pick = max(ev, key=ev.get)
    return {"pick": pick, "prob": round(base[pick], 4)}
