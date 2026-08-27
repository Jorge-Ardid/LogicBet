# -*- coding: utf-8 -*-
"""v2 «Poisson Lambda».

Лямбда загального рахунку з форми атаки/оборони (що входить у контекст),
перевірка P(total > 2.5) за допомогою розподілу Пуассона.
"""
import math

ID = "totals_v2"
NAME = "Poisson Lambda"
SECTOR = "totals"


def _dp(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict(ctx):
    if (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    lh = max(0.3, min(3.2, 0.6 * ctx.get("home_gf") + 0.4 * ctx.get("away_ga")))
    la = max(0.3, min(3.2, 0.6 * ctx.get("away_gf") + 0.4 * ctx.get("home_ga")))
    total = lh + la
    p_over = 1.0 - sum(_dp(k, total) for k in range(3))
    pick = "ТБ 2.5" if p_over >= 0.5 else "ТМ 2.5"
    return {"pick": pick, "prob": round(max(p_over, 1 - p_over), 4)}
