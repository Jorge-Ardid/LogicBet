# -*- coding: utf-8 -*-
"""v4 «Leaky Defenses».

Команди, які часто пропускають (>1.30/матч в середньому), → ОЗ — Так.
Жорстка сигмоїда навколо порогу 1.30.
"""
import math

ID = "btts_v4"
NAME = "Leaky Defenses"
SECTOR = "btts"


def predict(ctx):
    h_ga = ctx.get("home_ga")
    a_ga = ctx.get("away_ga")
    if h_ga is None or a_ga is None:
        return None
    x = (h_ga + a_ga) / 2.0 - 1.30
    p_yes = 1.0 / (1.0 + math.exp(-1.6 * x))
    pick = "ОЗ - Так" if p_yes >= 0.5 else "ОЗ - Ні"
    return {"pick": pick, "prob": round(max(p_yes, 1 - p_yes), 4)}
