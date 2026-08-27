# -*- coding: utf-8 -*-
"""v9 «Poisson 1X2».

Побудова ймовірностей 1X2 з повного матричного розподілу Пуассона
(0..8 голів). Лямбди похідні з форми атаки/оборони.
"""
import math

ID = "outcomes_v9"
NAME = "Poisson 1X2"
SECTOR = "outcomes"


def _dp(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict(ctx):
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.3, min(3.0, 0.55 * ctx.get("home_gf") + 0.45 * ctx.get("away_ga")))
    la = max(0.3, min(3.0, 0.55 * ctx.get("away_gf") + 0.45 * ctx.get("home_ga")))
    p1 = px = p2 = 0.0
    for i in range(9):
        for j in range(9):
            pr = _dp(i, lh) * _dp(j, la)
            if i > j:
                p1 += pr
            elif i == j:
                px += pr
            else:
                p2 += pr
    s = p1 + px + p2
    p1, px, p2 = p1 / s, px / s, p2 / s
    opts = {"П1": p1, "X": px, "П2": p2}
    pick = max(opts, key=opts.get)
    return {"pick": pick, "prob": round(opts[pick], 4)}
