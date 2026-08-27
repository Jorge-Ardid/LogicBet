# -*- coding: utf-8 -*-
"""v10 «Blend Committee» (outcomes).

Комітет з трьох сигналів (Elo, форма, AI), якщо AI є — інакше
залишається blend Elo + форма. Вибирає аргмакс.
"""
import math

ID = "outcomes_v10"
NAME = "Blend Committee"
SECTOR = "outcomes"


def _elo_probs(d):
    ph = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
    px = max(0.12, min(0.30, 0.27 - 0.0003 * abs(d)))
    return (1 - px) * ph, px, (1 - px) * (1 - ph)


def _form_probs(ctx):
    f = (ctx.get("home_ppg") or 1.33) - (ctx.get("away_ppg") or 1.33)
    ph = 1.0 / (1.0 + math.exp(-0.9 * f))
    px = max(0.12, min(0.30, 0.25 - 0.0003 * abs(f)))
    s = ((1 - px) * ph) + px + ((1 - px) * (1 - ph))
    return (1 - px) * ph / s, px / s, (1 - px) * (1 - ph) / s


def _blend(a, b, w):
    return {k: a[k] * w + b[k] * (1 - w) for k in a}


def predict(ctx):
    d = (ctx.get("home_elo") or 1500.0) - (ctx.get("away_elo") or 1500.0)
    e = _elo_probs(d)
    elo = {"П1": e[0], "X": e[1], "П2": e[2]}
    if (ctx.get("home_n") or 0) >= 3 and (ctx.get("away_n") or 0) >= 3:
        f = _form_probs(ctx)
        frm = {"П1": f[0], "X": f[1], "П2": f[2]}
        final = _blend(elo, frm, 0.55)
    else:
        final = elo
    ai = (ctx.get("ai") or {}).get("outcomes") or {}
    if ai:
        s = sum(final.values()) + sum(ai.values())
        final = {k: final[k] + ai.get(k, 0.0) * 0.6 for k in final}
        s2 = sum(final.values())
        final = {k: final[k] / s2 for k in final}
    pick = max(final, key=final.get)
    return {"pick": pick, "prob": round(max(0.05, min(0.95, final[pick])), 4)}
