# -*- coding: utf-8 -*-
"""v1 «Goals Average».

Очікуваний загальний рахунок = середнє з чотирьох середніх
(домашній GF+GA, вирина GA+GF). Поріг 2.5 → ТБ/ТМ через сигмоїду.
"""
import math

ID = "totals_v1"
NAME = "Goals Average"
SECTOR = "totals"


def predict(ctx):
    if (ctx.get("home_n") or 0) < 3 or (ctx.get("away_n") or 0) < 3:
        return None
    t = (ctx.get("home_gf") + ctx.get("home_ga") +
         ctx.get("away_gf") + ctx.get("away_ga")) / 4.0
    p_over = 1.0 / (1.0 + math.exp(-1.2 * (t - 2.5)))
    pick = "ТБ 2.5" if p_over >= 0.5 else "ТМ 2.5"
    return {"pick": pick, "prob": round(max(p_over, 1 - p_over), 4)}
