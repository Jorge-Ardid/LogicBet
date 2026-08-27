# -*- coding: utf-8 -*-
"""v4 «AI Consensus Mirror».

Дзеркало та найбільша ймовірна AI-прогнозу з таблиці ``predictions`` у
секторі 1X2. Коли немає AI-даних — скрипт вчинив би аліас v1, тому
просто скасовується (None), а не штука погану модель.
"""
import math

ID = "outcomes_v4"
NAME = "AI Consensus Mirror"
SECTOR = "outcomes"


def predict(ctx):
    ai = (ctx.get("ai") or {}).get("outcomes") or {}
    if not ai:
        return None
    pick = max(ai, key=ai.get)
    prob = max(0.05, min(0.95, float(ai[pick])))
    return {"pick": pick, "prob": round(prob, 4)}
