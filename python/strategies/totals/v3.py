# -*- coding: utf-8 -*-
"""v3 «AI Consensus Mirror» (сектор Тотали).

Вибирає ТБ/ТМ з AI-прогнозу ``predictions`` для маркету TOTAL_GOALS.
Скасовується, коли AI-даних немає.
"""
import math

ID = "totals_v3"
NAME = "AI Consensus Mirror"
SECTOR = "totals"


def predict(ctx):
    ai = (ctx.get("ai") or {}).get("totals") or {}
    if not ai:
        return None
    pick = max(ai, key=ai.get)
    prob = max(0.05, min(0.95, float(ai[pick])))
    return {"pick": pick, "prob": round(prob, 4)}
