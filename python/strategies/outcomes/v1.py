# -*- coding: utf-8 -*-
"""v1 «Elo Favorite (raw)» — базовий бенчмарк сектора.

Чиста різниця загальних ``elo_rating`` команд, перетворена в ймовірності 1X2
через логітик очікування Elo. Без домашньої переваги, без форми —
канона, з якою порівнюються всі інші скрипти сектора.
"""
import math

ID = "outcomes_v1"
NAME = "Elo Favorite (raw)"
SECTOR = "outcomes"


def _elo_probs(d_elo):
    p_home = 1.0 / (1.0 + 10.0 ** (-d_elo / 400.0))
    px = max(0.12, min(0.30, 0.27 - 0.0003 * abs(d_elo)))
    p1 = (1.0 - px) * p_home
    p2 = (1.0 - px) * (1.0 - p_home)
    return p1, px, p2


def predict(ctx):
    h = ctx.get("home_elo") or 1500.0
    a = ctx.get("away_elo") or 1500.0
    p1, px, p2 = _elo_probs(h - a)
    opts = {"П1": p1, "X": px, "П2": p2}
    pick = max(opts, key=opts.get)
    return {"pick": pick, "prob": round(opts[pick], 4)}
