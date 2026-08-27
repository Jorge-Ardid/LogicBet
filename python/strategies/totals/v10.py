# -*- coding: utf-8 -*-
"""v10 «Blend Committee» (сектор Тотали).

Комітет: модель загального рахунку з форми, Poisson-модель, AI (якщо є)
та ринкова імовірність з коефіцієнтів (якщо є). Ваги нормуються динамічно.
"""
import math

ID = "totals_v10"
NAME = "Blend Committee"
SECTOR = "totals"
_W = {"model": 1.0, "poisson": 1.0, "ai": 0.6, "market": 0.5}


def _dp(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict(ctx):
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    g = (ctx.get("home_gf") + ctx.get("home_ga") +
         ctx.get("away_gf") + ctx.get("away_ga")) / 4.0
    lh = max(0.3, min(3.2, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.3, min(3.2, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    lam = lh + la
    p_over_pois = 1.0 - sum(_dp(k, lam) for k in range(3))
    p_over_model = 1.0 / (1.0 + math.exp(-1.2 * (g - 2.5)))
    p_over_ai = (ctx.get("ai") or {}).get("totals", {}).get("ТБ 2.5")
    odds = ctx.get("odds") or {}
    p_over_mkt = None
    if odds.get("ТБ 2.5") and odds.get("ТМ 2.5"):
        try:
            io = 1.0 / float(odds["ТБ 2.5"])
            in_ = 1.0 / float(odds["ТМ 2.5"])
            p_over_mkt = io / (io + in_)
        except (TypeError, ValueError, ZeroDivisionError):
            p_over_mkt = None

    acc = 0.0
    wsum = 0.0
    acc += p_over_model * _W["model"]; wsum += _W["model"]
    acc += p_over_pois * _W["poisson"]; wsum += _W["poisson"]
    if p_over_ai:
        acc += float(p_over_ai) * _W["ai"]; wsum += _W["ai"]
    if p_over_mkt:
        acc += p_over_mkt * _W["market"]; wsum += _W["market"]
    p_over = acc / wsum
    pick = "ТБ 2.5" if p_over >= 0.5 else "ТМ 2.5"
    return {"pick": pick, "prob": round(max(p_over, 1 - p_over), 4)}
