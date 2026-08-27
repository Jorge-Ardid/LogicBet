# -*- coding: utf-8 -*-
"""v8 «AI Contrarian» (сектор Тотали).

Бере найпопулярніший вибір AI і йде у протилежну сторону — корисно, коли
AI є надмірно консенсусним. Без AI-даних скасовується (не штукує погану модель).
"""
import math

ID = "totals_v8"
NAME = "AI Contrarian"
SECTOR = "totals"


def predict(ctx):
    ai = (ctx.get("ai") or {}).get("totals") or {}
    if not ai:
        return None
    pick = max(ai, key=ai.get)
    prob = float(ai[pick])
    opposite = "ТМ 2.5" if pick == "ТБ 2.5" else "ТБ 2.5"
    p_opp = max(0.30, min(0.70, 1.0 - prob))
    return {"pick": opposite, "prob": round(p_opp, 4)}

