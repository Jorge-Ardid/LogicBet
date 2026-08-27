# -*- coding: utf-8 -*-
"""v5 «Mismatch Under».

Екстремальна різниця рейтингів → одностороння гра → ТМ 2.5;
близькі рейтинги → відкрита гра → ТБ 2.5. Середина — скасування.
"""
import math

ID = "totals_v5"
NAME = "Mismatch Under"
SECTOR = "totals"


def predict(ctx):
    h = ctx.get("home_elo") or 1500.0
    a = ctx.get("away_elo") or 1500.0
    d = h - a
    ad = abs(d)
    if ad >= 120.0:
        prob = max(0.50, min(0.70, 0.56 + (ad - 120.0) / 1600.0))
        return {"pick": "ТМ 2.5", "prob": round(prob, 4)}
    if ad <= 40.0:
        prob = min(0.62, 0.54 + (40.0 - ad) / 900.0)
        return {"pick": "ТБ 2.5", "prob": round(prob, 4)}
    return None
