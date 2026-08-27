# -*- coding: utf-8 -*-
"""v10 «Blend Committee» (сектор ОЗ).

Комітет: Poisson-модель (v1-style), Leaky Defenses (v4), AI (якщо є)
та ринкова ймовірність з коефіцієнтів (якщо є).
"""
import math

ID = "btts_v10"
NAME = "Blend Committee"
SECTOR = "btts"
_W = {"poisson": 1.0, "leaky": 1.0, "ai": 0.6, "market": 0.5}


def _dp(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict(ctx):
    h_ga = ctx.get("home_ga")
    a_ga = ctx.get("away_ga")
    if h_ga is None or a_ga is None:
        return None
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.2, min(3.0, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.2, min(3.0, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    p_yes_poisson = 0.0
    for i in range(1, 10):
        for j in range(1, 10):
            p_yes_poisson += _dp(i, lh) * _dp(j, la)
    p_yes_leaky = 1.0 / (1.0 + math.exp(-1.6 * ((h_ga + a_ga) / 2.0 - 1.30)))
    ai = (ctx.get("ai") or {}).get("btts") or {}
    p_yes_ai = ai.get("ОЗ - Так")
    odds = ctx.get("odds") or {}
    p_yes_mkt = None
    if odds.get("ОЗ - Так") and odds.get("ОЗ - Ні"):
        try:
            it = 1.0 / float(odds["ОЗ - Так"])
            in_ = 1.0 / float(odds["ОЗ - Ні"])
            p_yes_mkt = it / (it + in_)
        except (TypeError, ValueError, ZeroDivisionError):
            p_yes_mkt = None

    acc = p_yes_poisson * _W["poisson"]; wsum = _W["poisson"]
    acc += p_yes_leaky * _W["leaky"]; wsum += _W["leaky"]
    if p_yes_ai:
        acc += float(p_yes_ai) * _W["ai"]; wsum += _W["ai"]
    if p_yes_mkt:
        acc += p_yes_mkt * _W["market"]; wsum += _W["market"]
    p_yes = max(0.01, min(0.99, acc / wsum))
    pick = "ОЗ - Так" if p_yes >= 0.5 else "ОЗ - Ні"
    return {"pick": pick, "prob": round(p_yes, 4)}
