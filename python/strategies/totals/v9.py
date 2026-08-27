# -*- coding: utf-8 -*-
"""v9 «H2H Goals».

Скасовується, якщо менше ніж 2 історичні матчі цих команд.
Якщо є — бере середній сумарний рахунок по H2H і йде ТБ/ТМ 2.5.
"""
import math

ID = "totals_v9"
NAME = "H2H Goals"
SECTOR = "totals"


def predict(ctx):
    n = ctx.get("h2h_n") or 0
    avg = ctx.get("h2h_avg_goals")
    if n < 2 or not avg:
        return None
    p_over = 1.0 / (1.0 + math.exp(-1.4 * (float(avg) - 2.5)))
    pick = "ТБ 2.5" if p_over >= 0.5 else "ТМ 2.5"
    return {"pick": pick, "prob": round(max(p_over, 1 - p_over), 4)}
