# -*- coding: utf-8 -*-
"""v9 «Poisson Cells».

Точна ймовірність «обидві заб’ють» з повного матричного розподілу Пуассона
(1 − P(h=0))·(1 − P(a=0)), або саме сума клітинок i≥1,j≥1.
"""
import math

ID = "btts_v9"
NAME = "Poisson Cells"
SECTOR = "btts"


def _dp(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict(ctx):
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.2, min(3.0, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.2, min(3.0, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    p_yes = 0.0
    for i in range(1, 10):
        for j in range(1, 10):
            p_yes += _dp(i, lh) * _dp(j, la)
    p_yes = max(0.01, min(0.99, p_yes))
    pick = "ОЗ - Так" if p_yes >= 0.5 else "ОЗ - Ні"
    return {"pick": pick, "prob": round(p_yes, 4)}
