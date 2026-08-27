# -*- coding: utf-8 -*-
"""v5 «Elo Balance».

Близькі рейтинги → відкрита гра → ОЗ — Так; велика різниця →
одностороння гра → ОЗ — Ні. Середина — скасування.
"""
import math

ID = "btts_v5"
NAME = "Elo Balance"
SECTOR = "btts"


def predict(ctx):
    h = ctx.get("home_elo") or 1500.0
    a = ctx.get("away_elo") or 1500.0
    ad = abs(h - a)
    if ad <= 50.0:
        prob = min(0.65, 0.55 + (50.0 - ad) / 400.0)
        return {"pick": "ОЗ - Так", "prob": round(prob, 4)}
    if ad >= 130.0:
        prob = min(0.65, 0.55 + (ad - 130.0) / 600.0)
        return {"pick": "ОЗ - Ні", "prob": round(prob, 4)}
    return None
