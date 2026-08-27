# -*- coding: utf-8 -*-
"""v2 «AI Consensus Mirror» (сектор ОЗ).

Вибирає ОЗ — Так/Ні з AI-прогнозу ``predictions`` для маркету BTTS.
Скасовується, коли AI-даних немає.
"""
import math

ID = "btts_v2"
NAME = "AI Consensus Mirror"
SECTOR = "btts"


def predict(ctx):
    ai = (ctx.get("ai") or {}).get("btts") or {}
    if not ai:
        return None
    pick = max(ai, key=ai.get)
    prob = max(0.05, min(0.95, float(ai[pick])))
    return {"pick": pick, "prob": round(prob, 4)}
