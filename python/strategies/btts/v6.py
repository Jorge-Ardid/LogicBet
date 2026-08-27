# -*- coding: utf-8 -*-
"""v6 «Clean Sheet Watch».

Очищення мережі (CS) в останній серії: сума CS кожної команді.
Більше сухих матчів → ОЗ — Ні.
"""
import math

ID = "btts_v6"
NAME = "Clean Sheet Watch"
SECTOR = "btts"


def predict(ctx):
    cs = (ctx.get("home_cs") or 0) + (ctx.get("away_cs") or 0)
    p_no = 1.0 / (1.0 + math.exp(-(0.5 * (cs - 4))))
    pick = "ОЗ - Ні" if p_no >= 0.5 else "ОЗ - Так"
    return {"pick": pick, "prob": round(max(p_no, 1 - p_no), 4)}
