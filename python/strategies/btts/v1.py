# -*- coding: utf-8 -*-
"""v1 «Both Score Model».

P(обидві команді заб'ють) ≈ (1 − e^{−lh})·(1 − e^{−la}), де lh/la —
очікувана кількість голів кожної команди з форми атаки/оборони.
"""
import math

ID = "btts_v1"
NAME = "Both Score Model"
SECTOR = "btts"


def predict(ctx):
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.2, min(3.0, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.2, min(3.0, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    p_yes = (1 - math.exp(-lh)) * (1 - math.exp(-la))
    pick = "ОЗ - Так" if p_yes >= 0.5 else "ОЗ - Ні"
    return {"pick": pick, "prob": round(max(p_yes, 1 - p_yes), 4)}
