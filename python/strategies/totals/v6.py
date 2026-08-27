# -*- coding: utf-8 -*-
"""v6 «Home Attack Focus».

Ваговий лямбда тоталу з акцентом на домашню атаку проти вирина оборони
(62 %) та вирину атаку проти домашньої оборони (38 % зі знижкою 0.9).
"""
import math

ID = "totals_v6"
NAME = "Home Attack Focus"
SECTOR = "totals"


def predict(ctx):
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    xh = 0.5 * (ctx.get("home_gf") + ctx.get("away_ga"))
    xa = 0.5 * (ctx.get("away_gf") + ctx.get("home_ga"))
    total = 0.62 * xh + 0.38 * xa * 0.9
    p_over = 1.0 / (1.0 + math.exp(-1.3 * (total - 2.5)))
    pick = "ТБ 2.5" if p_over >= 0.5 else "ТМ 2.5"
    return {"pick": pick, "prob": round(max(p_over, 1 - p_over), 4)}
