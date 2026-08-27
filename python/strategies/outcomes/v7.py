# -*- coding: utf-8 -*-
"""v7 «Strong Favorite Only».

Складає лише вибутнє переваги Elo достатньо велики (>).
Інакше скасовується — трохи «жорсткий» інвестор, що мінімізує ризик.
"""
import math

ID = "outcomes_v7"
NAME = "Strong Favorite Only"
SECTOR = "outcomes"
_THRESHOLD = 90.0


def predict(ctx):
    h = ctx.get("home_elo") or 1500.0
    a = ctx.get("away_elo") or 1500.0
    d = h - a
    if d > _THRESHOLD:
        prob = min(0.78, 0.62 + d / 2400.0)
        return {"pick": "П1", "prob": round(prob, 4)}
    if d < -_THRESHOLD:
        prob = min(0.78, 0.62 + abs(d) / 2400.0)
        return {"pick": "П2", "prob": round(prob, 4)}
    return None
