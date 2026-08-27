# -*- coding: utf-8 -*-
"""v3 «Form Momentum».

Замість Elo використовує різницю середнього очків за гру (PPG) у
останній серії матчів. Відкритий, «гарячий» — куди краще рухомий результат.
"""
import math

ID = "outcomes_v3"
NAME = "Form Momentum"
SECTOR = "outcomes"


def _norm(p1, px, p2):
    s = p1 + px + p2
    return p1 / s, px / s, p2 / s


def predict(ctx):
    hn, an = ctx.get("home_n") or 0, ctx.get("away_n") or 0
    if hn < 3 or an < 3:
        return None  # недостатньо даних про форму
    f = (ctx.get("home_ppg") or 1.33) - (ctx.get("away_ppg") or 1.33)
    p_home = 1.0 / (1.0 + math.exp(-0.9 * f))
    px = max(0.11, min(0.32, 0.27 - 0.0004 * abs(f)))
    p1, px, p2 = _norm((1 - px) * p_home, px, (1 - px) * (1 - p_home))
    opts = {"П1": p1, "X": px, "П2": p2}
    pick = max(opts, key=opts.get)
    return {"pick": pick, "prob": round(opts[pick], 4)}
