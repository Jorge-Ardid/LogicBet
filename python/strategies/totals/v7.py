# -*- coding: utf-8 -*-
"""v7 «Short-Term Hot Form».

Останні 4 матчі (гаряча форма) мають вагу 0.6, 8-матчевий середній — 0.4.
Реагує на те, коли команда «вогненна» або втомлена.
"""
import math

ID = "totals_v7"
NAME = "Short-Term Hot Form"
SECTOR = "totals"


def predict(ctx):
    hn4 = ctx.get("home_n4") or 0
    an4 = ctx.get("away_n4") or 0
    if hn4 < 2 or an4 < 2 or (ctx.get("home_n") or 0) < 2 or (ctx.get("away_n") or 0) < 2:
        return None
    t4 = (ctx.get("home_gf4") + ctx.get("home_ga4") +
          ctx.get("away_gf4") + ctx.get("away_ga4")) / 4.0
    t8 = (ctx.get("home_gf") + ctx.get("home_ga") +
          ctx.get("away_gf") + ctx.get("away_ga")) / 4.0
    total = 0.6 * t4 + 0.4 * t8
    p_over = 1.0 / (1.0 + math.exp(-1.15 * (total - 2.5)))
    pick = "ТБ 2.5" if p_over >= 0.5 else "ТМ 2.5"
    return {"pick": pick, "prob": round(max(p_over, 1 - p_over), 4)}
