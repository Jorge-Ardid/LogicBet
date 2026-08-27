# -*- coding: utf-8 -*-
"""v4 «Market Value EV» (сектор Тотали).

EV = model_prob · odd − 1; вибирає ТБ/ТМ з кращим EV серед реальних
коефіцієнтів bet365. Скасовується без коефіцієнтів.
"""
import math

ID = "totals_v4"
NAME = "Market Value EV"
SECTOR = "totals"


def predict(ctx):
    odds = ctx.get("odds") or {}
    if not all(odds.get(s) for s in ("ТБ 2.5", "ТМ 2.5")):
        return None
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.3, min(3.2, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.3, min(3.2, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    total = lh + la
    p_over = max(0.01, min(0.99, 1.0 - sum(
        math.exp(-total) * total ** k / math.factorial(k) for k in range(3))))
    base = {"ТБ 2.5": p_over, "ТМ 2.5": 1 - p_over}
    ev = {s: base[s] * float(odds[s]) - 1.0 for s in base}
    pick = max(ev, key=ev.get)
    return {"pick": pick, "prob": round(base[pick], 4)}
