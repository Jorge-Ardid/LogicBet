# -*- coding: utf-8 -*-
"""v7 «Home Attack Only».

Асиметрична модель: ймовірність забити залежить переважно від домашньої
атаки + вириного пропущених (зі знижкою 0.9 для вирина).
"""
import math

ID = "btts_v7"
NAME = "Home Attack Only"
SECTOR = "btts"


def predict(ctx):
    h_gf = ctx.get("home_gf")
    h_ga = ctx.get("away_ga")  # домаці забивають, коли вирина пропускає
    a_gf = ctx.get("away_gf")
    a_ga = ctx.get("home_ga")
    if None in (h_gf, h_ga, a_gf, a_ga):
        return None
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    p_h = 1 - math.exp(-0.6 * h_gf - 0.4 * h_ga)
    p_a = (1 - math.exp(-0.6 * a_gf - 0.4 * a_ga)) * 0.9
    p_yes = p_h * p_a
    pick = "ОЗ - Так" if p_yes >= 0.5 else "ОЗ - Ні"
    return {"pick": pick, "prob": round(max(p_yes, 1 - p_yes), 4)}

