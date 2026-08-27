# -*- coding: utf-8 -*-
"""v6 «Draw Specialist».

Коли команди близькі за рейтингом (|elo_diff| < 40), піддає перевазі
нічиюй — найчастіше саме нічиї виникають на рівних матчах. Інакше —
fav through Elo.
"""
import math

ID = "outcomes_v6"
NAME = "Draw Specialist"
SECTOR = "outcomes"


def _fav(d):
    p_home = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
    return p_home, 1 - p_home


def predict(ctx):
    h = ctx.get("home_elo") or 1500.0
    a = ctx.get("away_elo") or 1500.0
    d = h - a
    if abs(d) < 40:
        prob = max(0.30, min(0.36, 0.30 + 0.0015 * (40 - abs(d))))
        return {"pick": "X", "prob": round(prob, 4)}
    ph, pa = _fav(d)
    pick = "П1" if d > 0 else "П2"
    return {"pick": pick, "prob": round(max(ph, pa), 4)}
