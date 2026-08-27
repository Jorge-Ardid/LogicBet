# -*- coding: utf-8 -*-
"""v8 «AI Contrarian» (сектор ОЗ).

Бере найпопулярніший вибір AI і йде у протилежну сторону. Скасовується
без AI-даних.
"""
import math

ID = "btts_v8"
NAME = "AI Contrarian"
SECTOR = "btts"


def predict(ctx):
    ai = (ctx.get("ai") or {}).get("btts") or {}
    if not ai:
        return None
    pick = max(ai, key=ai.get)
    prob = float(ai[pick])
    opposite = "ОЗ - Ні" if pick == "ОЗ - Так" else "ОЗ - Так"
    p_opp = max(0.30, min(0.70, 1.0 - prob))
    return {"pick": opposite, "prob": round(p_opp, 4)}
