# -*- coding: utf-8 -*-
"""v8 «Underdog Hunter».

Шукає цінність на «підводі»: коли Elo-модель не вважає дану команду
білем, а коефіцієнт пропонує кращу ніж 1/prob — це цінність. Потребує
коефіцієнтів; має високу дисперсію.
"""
import math

ID = "outcomes_v8"
NAME = "Underdog Hunter"
SECTOR = "outcomes"


def _elo_exp(d):
    return 1.0 / (1.0 + 10.0 ** (-d / 400.0))


def predict(ctx):
    odds = ctx.get("odds") or {}
    if not all(odds.get(s) for s in ("П1", "X", "П2")):
        return None
    d = (ctx.get("home_elo") or 1500.0) - (ctx.get("away_elo") or 1500.0)
    p1 = _elo_exp(d)
    p2 = 1 - p1
    # домаця «підвода» = команда з меншою ймовірністю, але коеф. варта
    cands = []
    for sel, p in (("П1", p1), ("П2", p2)):
        if 0.22 <= p <= 0.46 and float(odds[sel]) > 1.0 / p:
            cands.append((sel, p))
    if not cands:
        return None
    cands.sort(key=lambda c: float(odds[c[0]]) * c[1], reverse=True)
    sel, p = cands[0]
    return {"pick": sel, "prob": round(p, 4)}
