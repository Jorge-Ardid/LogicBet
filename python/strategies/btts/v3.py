# -*- coding: utf-8 -*-
"""v3 «Market Value EV» (сектор ОЗ).

EV = model_prob · odd − 1; вибирає ОЗ — Так/Ні з кращим EV серед
реальних коефіцієнтів bet365. Скасовується без коефіцієнтів.
"""
import math

ID = "btts_v3"
NAME = "Market Value EV"
SECTOR = "btts"


def predict(ctx):
    odds = ctx.get("odds") or {}
    if not all(odds.get(s) for s in ("ОЗ - Так", "ОЗ - Ні")):
        return None
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.2, min(3.0, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.2, min(3.0, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    p_yes = (1 - math.exp(-lh)) * (1 - math.exp(-la))
    base = {"ОЗ - Так": p_yes, "ОЗ - Ні": 1 - p_yes}
    ev = {s: base[s] * float(odds[s]) - 1.0 for s in base}
    pick = max(ev, key=ev.get)
    return {"pick": pick, "prob": round(base[pick], 4)}
