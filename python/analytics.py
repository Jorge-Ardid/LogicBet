import random
import math

# Зміна B: половина періоду розпаду ваги давності матчу (днів).
# 30 днів => свіжий матч (до ~3 тижнів) має майже повну вагу (>0.6),
# а матч 3–6 місячної давнини — тільки 0.13…0.02 (згасаючий множник).
TIME_DECAY_HALF_LIFE_DAYS = 30.0


class BettingAnalytics:
    def __init__(self, db):
        self.db = db
        self._reputation = None
        self.uk_dict = {
            "Home": "П1 (Господарі)",
            "Away": "П2 (Гості)",
            "Draw": "X (Нічия)",
            "1X": "1X (Подвійний шанс)",
            "X2": "X2 (Подвійний шанс)",
            "Premier League": "Прем'єр-ліга (Англія)",
            "Primeira Liga": "Прімейра-ліга (Португалія)",
            "Championship": "Чемпіоншип (Англія)",
            "Eredivisie": "Ередивізі (Нідерланди)",
            "Champions League": "Ліга Чемпіонів",
            "Europa League": "Ліга Європи",
            "Conference League": "Ліга Конференцій",
            "La Liga": "Ла Ліга (Іспанія)",
            "Bundesliga": "Бундесліга (Німеччина)",
            "Serie A": "Серія А (Італія)",
            "Ligue 1": "Ліга 1 (Франція)",
            "OVER": "ТБ",
            "UNDER": "ТМ",
            "GOALS (AI)": "ГОЛИ (AI)",
            "INDIVIDUAL TOTAL (AI)": "ІНД. ТОТАЛ (AI)",
            "GOALS (1ST HALF)": "ГОЛИ (1-й ТАЙМ)",
            "CORNERS (AI+)": "КУТОВІ (AI+)",
            "CARDS (AI)": "КАРТКИ (AI)",
            "STATISTICS": "СТАТИСТИКА",
            "VALUE": "💎 ЦІННІСТЬ",
            "RISK": "🔥 РИЗИК",
            "PARITY": "⚖️ ПАРИТЕТ",
            "ANALYSIS": "АНАЛІЗ",
            "H2H": "📊 H2H"
        }

    def translate(self, text):
        # Handle OVER/UNDER translation in selection strings
        if "OVER" in text:
            text = text.replace("OVER", "ТБ")
        elif "UNDER" in text:
            text = text.replace("UNDER", "ТМ")
        elif "1st half" in text:
            text = text.replace("1st half", "1-й тайм")
        elif "Corners" in text:
            text = text.replace("Corners", "Кутові")
        elif "Cards" in text:
            text = text.replace("Cards", "Картки")
        
        # Apply dictionary for other terms
        return self.uk_dict.get(text, text)

    # ------------------------------------------------------------------
    # Зміна B (Вага давності / Exponential Decay): множник ваги матчу за
    # його віком. Свіжі матчі (останні 1–3 тижні) впливають майже на повну
    # силу, а матчі 3–6 місячної давнини отримують сильно згасаючий ваговий
    # коефіцієнт (0.13 → 0.02). Використовується і для форми/моментуму,
    # і для зважених середніх тоталів (голы/xG/кутові/картки).
    # ------------------------------------------------------------------
    @staticmethod
    def _time_weight(age_days):
        try:
            age = max(0.0, float(age_days))
        except (TypeError, ValueError):
            age = 0.0
        return math.exp(-math.log(2) * age / TIME_DECAY_HALF_LIFE_DAYS)

    # ------------------------------------------------------------------
    # Reward & Penalty engine: per-market "karma" learned from settled user bets.
    #   WON  -> karma += (odd - 1) * confidence      (reward; higher odd is sweeter)
    #   LOST -> karma -= odd * confidence             (penalty; higher odd hurts more)
    # A negative karma acts as a market weight downgrade: the more expensive a lost
    # bet was (high odd), the stronger the market's internal trust drops and the more
    # the model hesitates / hedges on that market until it proves itself again.
    # ------------------------------------------------------------------
    def _market_token(self, selection):
        """Map a prediction selection string to its 1X2/karma market token."""
        if not selection:
            return None
        s = str(selection).strip()
        if s.startswith("П1") or s == "Home":
            return "П1"
        if s.startswith("П2") or s == "Away":
            return "П2"
        if s.startswith("1X"):
            return "1X"
        if s.startswith("X2"):
            return "X2"
        if s.startswith("12"):
            return "12"
        if s.startswith("Х") or s.startswith("X ") or s in ("X", "Х") or s == "Draw":
            return "X"
        for tok in ("ТБ", "ТМ", "ОЗ"):
            if tok in s:
                return tok
        return None

    def _compute_reputation(self):
        """Reward & Penalty engine: rebuild market karma from settled user bets.

        User bets store a COMBO string ("П1 / ТБ 2.5 / ...") — each part is matched
        against that match's predictions; confidence = prediction's own probability,
        so reward/penalty is scaled by how sure the AI was on that pick.
        Also keeps a 5-match sliding penalty balance per market (for the risk switch).
        WON  -> karma += (odd - 1) * confidence
        LOST -> karma -= odd * confidence
        """
        with self.db.get_connection() as conn:
            bets = conn.execute(
                "SELECT match_id, selection, odd, stake, status FROM user_bets "
                "WHERE status IN ('WON','LOST') "
                "  AND odd IS NOT NULL AND odd > 0"
            ).fetchall()
            pred_rows = conn.execute(
                "SELECT match_id, selection, calculated_prob, is_hit "
                "FROM predictions WHERE calculated_prob IS NOT NULL"
            ).fetchall()

        # index predictions per match by normalized selection text
        preds_by_match = {}
        for mid, sel, prob, _p_hit in pred_rows:
            key = " ".join((sel or "").upper().split())
            preds_by_match.setdefault(mid, {})[key] = float(prob)

        # Оцінка ефективності — ВИКЛЮЧНО за РОЗРАХОВАНИМИ ставками (WON/LOST).
        # Активні ставки (PENDING) — це заморожений інвестиційний портфель:
        # вони ніколи не потрапляють сюди і не створюють ані штрафів, ані бонусів.
        rep = {}
        for mid, combo, odd, stake, status in bets:
            parts = [p.strip() for p in (combo or "").split("/") if p.strip()]
            lookup = preds_by_match.get(mid, {})
            known = [p for p in parts
                     if self._market_token(p) and (" ".join(p.upper().split()) in lookup)]
            if not known:
                continue
            # Комбо-ставку чесно ділимо порівну між розпізнаними маркетами,
            # щоб Yield кожного сигналу рахувався без подвійного обліку грошей.
            share = float(stake or 0.0) / len(known)
            for part in known:
                rec = lookup.get(" ".join(part.upper().split()))
                tok = self._market_token(part)
                conf = float(rec or 0.0)
                delta = (float(odd) - 1.0) * conf if status == "WON" else -float(odd) * conf
                entry = rep.setdefault(tok, {
                    "karma": 0.0, "recent": [],
                    "staked": 0.0, "returned": 0.0, "net": 0.0,
                    "bets": 0, "wins": 0,
                })
                entry["karma"] += delta
                entry["recent"].append((float(odd), status, conf))
                # --- Money-метрики для ROI / Yield (тільки settled) ---
                entry["bets"] += 1
                entry["staked"] += share
                if status == "WON":
                    payout = share * float(odd)
                    entry["returned"] += payout
                    entry["net"] += payout - share
                    entry["wins"] += 1
                else:
                    entry["net"] -= share

        # ------------------------------------------------------------------
        # ЗАВДАННЯ 3 (навчання ШІ): «віртуальні ставки» за is_hit усіх
        # маркетів. Кожен РОЗРАХОВАНИЙ прогноз картки матчу (predictions.is_hit,
        # заповнюється повним сетлментом webapp.settle_ai_predictions) стає
        # ставкою ШІ на 1 од. з модельним коефіцієнтом ~1/prob. Внесок
        # послаблений (W_VIRTUAL): реальні гроші користувача лишаються
        # головним сигналом, але карма вчиться на КОЖНОМУ варіанті — і на тих,
        # що ніколи не потрапляли в купон.
        # ------------------------------------------------------------------
        W_VIRTUAL = 0.35
        for _mid, _sel, _prob, _p_hit in pred_rows:
            if _p_hit is None:
                continue  # прогноз ще пройшов крізь повний сетлмент
            tok = self._market_token(_sel)
            if not tok:
                continue
            conf_ai = max(0.05, min(0.99, float(_prob or 0.5)))
            odd_ai = round(min(10.0, max(1.05, 1.0 / conf_ai)), 2)
            won_ai = bool(_p_hit)
            entry_ai = rep.setdefault(tok, {
                "karma": 0.0, "recent": [],
                "staked": 0.0, "returned": 0.0, "net": 0.0,
                "bets": 0, "wins": 0,
            })
            delta_ai = ((odd_ai - 1.0) * conf_ai) if won_ai \
                else (-odd_ai * conf_ai)
            entry_ai["karma"] += W_VIRTUAL * delta_ai
            entry_ai["recent"].append(
                (odd_ai, "WON" if won_ai else "LOST", conf_ai))
            entry_ai["bets"] += 1
            entry_ai["staked"] += 1.0
            if won_ai:
                payout_ai = odd_ai
                entry_ai["returned"] += payout_ai
                entry_ai["net"] += payout_ai - 1.0
                entry_ai["wins"] += 1
            else:
                entry_ai["net"] -= 1.0

        for tok, entry in rep.items():
            recent = entry["recent"][-5:]
            entry["penalty_last5"] = sum(
                -o * c for o, st, c in recent if st == "LOST"
            )
            entry["recent"] = recent
            staked = entry.pop("staked")
            returned = entry.pop("returned")
            net = entry.pop("net")
            entry["staked"] = round(staked, 2)
            entry["returned"] = round(returned, 2)
            entry["net"] = round(net, 2)
            # Yield = чистий прибуток / загальна сума РОЗРАХОВАНИХ ставок * 100
            entry["yield_pct"] = (
                round(net / staked * 100.0, 2) if staked > 0 else None)
        self._reputation = rep
        return rep

    def _learned_threshold(self, selection, base=0.65, span=0.12, floor=0.55, cap=0.80):
        """Adaptively calibrate the confidence threshold from market karma.

        Positive market karma lowers the required confidence (model earns trust);
        negative karma raises it (market penalized -> require more evidence before
        issuing a HIGH-confidence pick on that type).
        """
        tok = self._market_token(selection)
        karma = (self._reputation or {}).get(tok, {}).get("karma", 0.0) if tok else 0.0
        shift = max(-span, min(span, karma * 0.015))
        return max(floor, min(cap, base - shift))

    def _karma_bonus(self, token_or_selection):
        """Confidence multiplier from market karma + Settled ROI / Yield.

        Confidence Score formula (user-approved): prob * (1 + karma_bonus).
        База — старий karma-сигнал (clamped ±20%). Зверху — грошова оцінка
        дистанції ВИКЛЮЧНО за РОЗРАХОВАНИМИ ставками (PENDING не рахується
        і ніколи не штрафується):
          • Yield < 0  -> ШТРАФ: бонус примусово від'ємний (до −20%), глибина
            просадки (|Yield|) посилює покарання;
          • Yield >= 0 -> ПОХВАЛА: позитивний Yield на дистанції додає бонус
            (до +10% поверх karma-бази, загалом не вище +20%)."""
        tok = self._market_token(token_or_selection)
        if not tok:
            return 0.0
        entry = (self._reputation or {}).get(tok)
        if not entry:
            return 0.0
        base = max(-0.20, min(0.20, entry.get("karma", 0.0) * 0.03))
        y = entry.get("yield_pct")
        if y is None:
            return base
        if y < 0:
            raw = base - min(0.15, abs(y) * 0.005)
            return max(-0.20, min(0.0, raw))
        raw = base + min(0.10, y * 0.0025)
        return max(0.0, min(0.20, raw))

    def calculate_elo_probability(self, elo_a, elo_b):
        exponent = (elo_b - elo_a) / 400.0
        expected_a = 1.0 / (1.0 + 10 ** exponent)
        return expected_a

    def calculate_local_trends(self, team_id, match_id=None, match_date=None):
        """Calculates form using a blend of Season Averages and Recent Matches.
        Excludes the match being predicted to prevent data leakage/hindsight bias."""
        with self.db.get_connection() as conn:
            # 1. Get Season Averages (Baseline from Standings)
            team_data = conn.execute("SELECT name, attack_rating, defense_rating, elo_rating FROM teams WHERE id = ?", (team_id,)).fetchone()
            t_name = team_data[0] if team_data else "Unknown"
            season_atk = team_data[1] if team_data and team_data[1] else 1.2
            season_def = team_data[2] if team_data and team_data[2] else 1.2
            my_elo = team_data[3] if team_data and team_data[3] else 1500.0
            
            # 2. Get Recent Match Form (Last 5 played matches strictly BEFORE this match)
            params = [team_id, team_id]
            extra_where = ""
            if match_id is not None:
                extra_where += " AND m.id != ?"
                params.append(match_id)
            if match_date is not None:
                extra_where += " AND m.date < ?"
                params.append(match_date)
                
            query = f"""
                SELECT m.home_score, m.away_score, m.home_team_id, 
                       (CASE WHEN m.home_team_id = ? THEN t2.elo_rating ELSE t1.elo_rating END) as opp_elo,
                       m.xg_h, m.xg_a, m.corners_h, m.corners_a, m.yellow_cards_h, m.yellow_cards_a, m.shots_on_h, m.shots_on_a,
                       m.ht_score_h, m.ht_score_a, m.date
                FROM matches m
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                WHERE (m.home_team_id = ? OR m.away_team_id = ?) 
                AND m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
                AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
                {extra_where}
                ORDER BY m.date DESC LIMIT 5
            """
            matches = conn.execute(query, tuple([team_id] + params)).fetchall()
        
        if not matches:
            # Fallback to pure Season Averages
            return {
                "team_name": t_name,
                "atk_power": season_atk,
                "def_power": season_def,
                "momentum": 1.0,
                "label": "Новачок 🆕",
                "avg_goals": season_atk,
                "avg_goals_ht": season_atk * 0.45,
                "avg_corners": 9.5,
                "avg_corners_conceded": 4.8,
                "avg_cards": 4.5,
                "avg_shots": 12.0
            }
            
        # Filter out matches with null scores (e.g. NS matches auto-closed as FINISHED)
        matches = [m for m in matches if m[0] is not None and m[1] is not None]
        
        if not matches:
            return {
                "team_name": t_name,
                "atk_power": season_atk,
                "def_power": season_def,
                "momentum": 1.0,
                "label": "Новачок 🆕",
                "avg_goals": season_atk,
                "avg_goals_ht": season_atk * 0.45,
                "avg_corners": 9.5,
                "avg_corners_conceded": 4.8,
                "avg_cards": 4.5,
                "avg_shots": 12.0
            }

        recent_goals = []
        weighted_points = 0.0
        total_weight = 0.0
        weight_step = 5.0 # Max weight for the most recent match
        
        giant_killer_bonus = 0.0
        inconsistent_penalty = 0.0
        bully_count = 0
        

        from datetime import datetime as _dt, timezone as _tz
        def _parse_dt(x):
            d = _dt.fromisoformat(str(x).replace("Z", ""))
            return d.astimezone(_tz.utc).replace(tzinfo=None) if d.tzinfo else d
        parsed_dates = []
        for _m in matches:
            try:
                parsed_dates.append(_parse_dt(_m[14]))
            except Exception:
                parsed_dates.append(None)
        _valid = [d for d in parsed_dates if d]
        if match_date:
            try:
                ref_date = _parse_dt(match_date)
            except Exception:
                ref_date = max(_valid) if _valid else _dt.utcnow()
        else:
            ref_date = max(_valid) if _valid else _dt.utcnow()
        # Зміна B: half-life затухання піднято з 7 до 30 днів — матчи дворіч
        # лишаються майже повновагими, півсезонна давнина — сильно тліє.
        LAMBDA = math.log(2) / TIME_DECAY_HALF_LIFE_DAYS
        goal_weights = []
        for idx, m in enumerate(matches):
            # Result from query now has 15 columns (m.date added at index 14)
            h_s, a_s, h_id, opp_elo = m[0], m[1], m[2], m[3]
            is_home = (h_id == team_id)
            goals = h_s if is_home else a_s
            opp_goals = a_s if is_home else h_s
            recent_goals.append(goals)
            
            # Points
            pts = 0
            if goals > opp_goals: pts = 3
            elif goals == opp_goals: pts = 1
            
            # 1. Streak Weighting
            # Time-decay (Зміна B): свіжіші матчі важать більше
            m_date = parsed_dates[idx]
            age_days = max(0.0, (ref_date - m_date).days) if m_date else 0.0
            w_time = math.exp(-LAMBDA * age_days)
            goal_weights.append(w_time)
            eff_weight = weight_step * w_time
            weighted_points += pts * eff_weight
            total_weight += 3.0 * eff_weight
            
            # 2. Opposition Quality checking
            elo_diff = my_elo - opp_elo
            
            if pts == 3: # Win
                if elo_diff < -100: giant_killer_bonus += 0.10 # Won against much stronger
                elif elo_diff < -50: giant_killer_bonus += 0.05
                elif elo_diff > 150: bully_count += 1 # Won against much weaker
            elif pts == 0: # Loss
                if elo_diff > 150: inconsistent_penalty += 0.15 # Lost to much weaker
                elif elo_diff > 80: inconsistent_penalty += 0.05
            elif pts == 1: # Draw
                if elo_diff < -150: giant_killer_bonus += 0.05 # Drew against much stronger
                elif elo_diff > 150: inconsistent_penalty += 0.05 # Drew against much weaker

            weight_step -= 1.0
            
        _g_wsum = sum(goal_weights)
        avg_recent = (
            sum(g * w for g, w in zip(recent_goals, goal_weights)) / _g_wsum
            if _g_wsum > 0
            else (sum(recent_goals) / len(recent_goals) if recent_goals else season_atk)
        )
        points_pct = weighted_points / total_weight if total_weight > 0 else 0
        
        # Extended Stats (Averages over last matches)
        # Results from query: 0:h_s, 1:a_s, 2:h_id, 3:opp_elo, 4:xg_h, 5:xg_a, 6:cor_h, 7:cor_a, 8:y_h, 9:y_a, 10:sh_h, 11:sh_a
        def _get_stat(m, home_idx, away_idx, team_id):
            return m[home_idx] if m[2] == team_id else m[away_idx]

        # Filter matches that actually have stats (if corners + shots > 0, we assume stats exist)
        # Зміна B: для зважених середніх тримаємо ІНДЕКСИ матчів зі статистикою,
        # щоб вага давності бралась з parsed_dates за тим самим порядком.
        stats_idx = [i for i, m in enumerate(matches)
                     if (m[6] or 0) + (m[7] or 0) + (m[10] or 0) + (m[11] or 0) > 0]
        stats_weights = []
        for i in stats_idx:
            d_i = parsed_dates[i]
            stats_weights.append(self._time_weight(
                max(0.0, (ref_date - d_i).days) if d_i else 0.0))

        def _wavg(idx_list, weights, home_idx, away_idx):
            """Зважене (за давністю) середнє статпоказника — Зміна B."""
            w_total = sum(weights)
            if not idx_list or w_total <= 0:
                return None
            return sum((_get_stat(matches[i], home_idx, away_idx, team_id) or 0) * w
                       for i, w in zip(idx_list, weights)) / w_total

        avg_xg = _wavg(stats_idx, stats_weights, 4, 5)
        if avg_xg is None:
            avg_xg = season_atk
        
        # Blend: 40% Season Consistency, 30% Recent Goals, 30% Recent xG (Quality of chances)
        # xG is often a better predictor of future performance than actual goals.
        final_atk = (season_atk * 0.4) + (avg_recent * 0.3) + (avg_xg * 0.3)
        
        momentum = 1.0
        label = "Норма"
        
        # Only set special flags if we have enough recent data (min 3 matches)
        if len(matches) >= 3:
            if points_pct >= 0.70: momentum, label = 1.15, "Hot 🔥"
            elif points_pct <= 0.30: momentum, label = 0.85, "Cold ❄️"
            
            # Context Modifiers override simple hot/cold
            if giant_killer_bonus >= 0.10:
                momentum += giant_killer_bonus
                label = "Вбивця Гігантів 🗡️"
            elif inconsistent_penalty >= 0.10:
                momentum -= inconsistent_penalty
                label = "Нестабільні ⚠️"
            elif points_pct >= 0.60 and bully_count >= 2 and giant_killer_bonus == 0:
                momentum = 1.00 # Cancels out the "Hot" momentum because wins were too easy
                label = "Хулігани (Bully) 🦁"
                
        avg_corners = _wavg(stats_idx, stats_weights, 6, 7)
        if avg_corners is None:
            avg_corners = 4.8
        avg_corners_conceded = _wavg(stats_idx, stats_weights, 7, 6)
        if avg_corners_conceded is None:
            avg_corners_conceded = 4.8
        avg_y_cards = _wavg(stats_idx, stats_weights, 8, 9)
        if avg_y_cards is None:
            avg_y_cards = 1.8
        avg_shots = _wavg(stats_idx, stats_weights, 10, 11)
        if avg_shots is None:
            avg_shots = 11.0

        # Half-Time data: теж зважено за давністю (Зміна B)
        ht_idx = [i for i, m in enumerate(matches)
                  if m[12] is not None and m[13] is not None]
        ht_weights = []
        for i in ht_idx:
            d_i = parsed_dates[i]
            ht_weights.append(self._time_weight(
                max(0.0, (ref_date - d_i).days) if d_i else 0.0))
        avg_goals_ht = _wavg(ht_idx, ht_weights, 12, 13)
        if avg_goals_ht is None:
            avg_goals_ht = (season_atk * 0.45)

        # Cap momentum logically
        momentum = max(0.6, min(1.4, momentum))
        
        return {
            "team_name": t_name,
            "atk_power": final_atk,
            "def_power": season_def,
            "momentum": momentum,
            "label": label,
            "avg_goals": final_atk,
            "avg_goals_ht": avg_goals_ht,
            "avg_corners": avg_corners,
            "avg_corners_conceded": avg_corners_conceded,
            "avg_cards": avg_y_cards,
            "avg_shots": avg_shots
        }


    def _calculate_home_away_factor(self, home_id, away_id, match_id=None, match_date=None):
        base_bonus = 50.0
        
        params_h = [home_id]
        extra_h = ""
        if match_id is not None:
            extra_h += " AND id != ?"
            params_h.append(match_id)
        if match_date is not None:
            extra_h += " AND date < ?"
            params_h.append(match_date)
            
        params_a = [away_id]
        extra_a = ""
        if match_id is not None:
            extra_a += " AND id != ?"
            params_a.append(match_id)
        if match_date is not None:
            extra_a += " AND date < ?"
            params_a.append(match_date)

        with self.db.get_connection() as conn:
            # Get last 10 HOME matches for home team strictly before this match
            h_matches = conn.execute(f"""
                SELECT home_score, away_score, date
                FROM matches
                WHERE home_team_id = ? AND status IN ('FT', 'AET', 'PEN', 'FINISHED')
                AND home_score IS NOT NULL AND away_score IS NOT NULL
                {extra_h}
                ORDER BY date DESC LIMIT 10
            """, tuple(params_h)).fetchall()

            # Get last 10 AWAY matches for away team strictly before this match
            a_matches = conn.execute(f"""
                SELECT home_score, away_score, date
                FROM matches
                WHERE away_team_id = ? AND status IN ('FT', 'AET', 'PEN', 'FINISHED')
                AND home_score IS NOT NULL AND away_score IS NOT NULL
                {extra_a}
                ORDER BY date DESC LIMIT 10
            """, tuple(params_a)).fetchall()
            
        # Filter out matches with NULL scores (NS matches that were auto-closed)
        h_matches = [m for m in h_matches if m[0] is not None and m[1] is not None]
        a_matches = [m for m in a_matches if m[0] is not None and m[1] is not None]

        from datetime import datetime as _dtf

        def _w_by_date(dstr):
            """Вага давності конкретного матчу (Зміна B)."""
            try:
                d = _dtf.fromisoformat(str(dstr).replace("Z", ""))
                age = max(0.0, (_dtf.utcnow() - d).days)
            except Exception:
                age = 0.0
            return self._time_weight(age)

        def _venue_wr(rows):
            """Winrate, зважений експоненційно за давністю (Зміна B)."""
            pts = wsum = 0.0
            for hs_v, as_v, dstr in rows:
                w = _w_by_date(dstr)
                res = 1.0 if hs_v > as_v else (0.5 if hs_v == as_v else 0.0)
                pts += res * w
                wsum += w
            return (pts / wsum) if wsum > 0 else None

        h_winrate = _venue_wr(h_matches) if h_matches else None
        a_winrate = _venue_wr(a_matches) if a_matches else None
        if h_winrate is None:
            h_winrate = 0.5
        if a_winrate is None:
            a_winrate = 0.3
            
        # Home team strength at home: avg is ~0.5. 
        # Range: -25 to +25
        h_mod = (h_winrate - 0.5) * 50.0 
        
        # Away team weakness away: avg is ~0.3. 
        # Range: -35 to +15
        a_mod = (0.3 - a_winrate) * 50.0
        
        final_bonus = base_bonus + h_mod + a_mod
        
        # Clamp between 0 and 110
        return max(0.0, min(110.0, final_bonus))

    def calculate_win_probabilities(self, home_id, away_id, home_form="", away_form="", match_id=None, match_date=None):
        """Зміна A (Роздільний ELO): ймовірності рахуємо, порівнюючи
        ДОМАШНІЙ канал рейтингу господарів (teams.home_elo) з ВИЇЗНИМ
        каналом гостей (teams.away_elo). COALESCE робить запит безпечним
        для баз, де канали ще не мігрували/не наповнені."""
        with self.db.get_connection() as conn:
            h_data = conn.execute(
                "SELECT COALESCE(home_elo, elo_rating), name FROM teams WHERE id = ?",
                (home_id,)).fetchone()
            a_data = conn.execute(
                "SELECT COALESCE(away_elo, elo_rating), name FROM teams WHERE id = ?",
                (away_id,)).fetchone()

        if not h_data or not a_data:
            default_trend = {
                "atk_power": 1.2, 
                "def_power": 1.2, 
                "momentum": 1.0, 
                "label": "Unknown",
                "avg_goals": 1.25, 
                "avg_goals_ht": 0.5, 
                "avg_corners": 4.8, 
                "avg_cards": 1.8, 
                "avg_shots": 11.0,
                "team_name": "Unknown"
            }
            return {
                "home": 0.4, "draw": 0.2, "away": 0.4,
                "home_elo": 1500, "away_elo": 1500,
                "h_trend": default_trend,
                "a_trend": default_trend,
                "h2h_count": 0
            }

        # Зміна A: ці значення вже є венюними рейтингами
        # (home-канал господарів / away-канал гостей)
        home_elo = float(h_data[0])
        away_elo = float(a_data[0])

        # Dynamic Home Advantage (without leakage)
        home_bonus = self._calculate_home_away_factor(home_id, away_id, match_id=match_id, match_date=match_date)
        # Зміна A: home_bonus додається саме до домашнього каналу господарів
        win_prob = self.calculate_elo_probability(home_elo + home_bonus, away_elo)
        
        # Hybrid Trends (without leakage)
        h_trend = self.calculate_local_trends(home_id, match_id=match_id, match_date=match_date)
        a_trend = self.calculate_local_trends(away_id, match_id=match_id, match_date=match_date)
        
        # Calculate Multipliers (Scale productivity: 1.2 is baseline)
        h_mult = 1.0 + (h_trend['atk_power'] - 1.2) * 0.2
        a_mult = 1.0 + (a_trend['atk_power'] - 1.2) * 0.2
        
        h_def = 1.0 - (h_trend['def_power'] - 1.2) * 0.1
        a_def = 1.0 - (a_trend['def_power'] - 1.2) * 0.1
        
        combined_h = h_mult * h_def * h_trend['momentum']
        combined_a = a_mult * a_def * a_trend['momentum']
        
        adjusted_win = win_prob * (combined_h / combined_a)
        adjusted_win = max(0.05, min(0.95, adjusted_win))
        
        # Metadata for UI
        self._last_meta = {
            "h_avg": h_trend['avg_goals'],
            "a_avg": a_trend['avg_goals'],
            "h_trend": h_trend['label'],
            "a_trend": a_trend['label'],
            "h_bonus": home_bonus
        }

        # 3. Dynamic Draw Probability (Poisson calculation)
        # Based on average goals of both teams. High-scoring teams draw less.
        h_lmb = h_trend['avg_goals']
        a_lmb = a_trend['avg_goals']
        
        # Calculate prob of 0-0, 1-1, 2-2, 3-3
        p00 = self._poisson_pmf(0, h_lmb) * self._poisson_pmf(0, a_lmb)
        p11 = self._poisson_pmf(1, h_lmb) * self._poisson_pmf(1, a_lmb)
        p22 = self._poisson_pmf(2, h_lmb) * self._poisson_pmf(2, a_lmb)
        p33 = self._poisson_pmf(3, h_lmb) * self._poisson_pmf(3, a_lmb)
        draw_prob = max(0.15, min(0.35, p00 + p11 + p22 + p33))
        
        # 4. H2H Adjustment
        h2h = self.db.fetch_h2h_matches(home_id, away_id, 5,
                                        before_date=match_date)
        h2h_mult = 1.0
        if h2h:
            h2h_pts = 0
            for m in h2h:
                hs, ascores, h_id_match, a_id_match, date = m
                is_home_match = (h_id_match == home_id)
                my_s = hs if is_home_match else ascores
                op_s = ascores if is_home_match else hs
                if my_s > op_s: h2h_pts += 3
                elif my_s == op_s: h2h_pts += 1
            
            h2h_pct = h2h_pts / (len(h2h) * 3.0)
            h2h_mult = 0.9 + (h2h_pct * 0.2) # 0.9 to 1.1 multiplier
        
        # Final Blend
        remaining = 1.0 - draw_prob
        home_final = adjusted_win * remaining * h2h_mult
        away_final = (1.0 - adjusted_win) * remaining * (2.0 - h2h_mult)
        
        # Re-normalize to ensure sum is 1.0
        total = home_final + away_final + draw_prob
        home_final /= total
        away_final /= total
        draw_prob /= total
        
        return {
            "home": home_final,
            "draw": draw_prob,
            "away": away_final,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "h_trend": h_trend,
            "a_trend": a_trend,
            "h2h_count": len(h2h)
        }

    def _poisson_pmf(self, k, lmb):
        """Poisson Probability Mass Function."""
        return (lmb ** k * math.exp(-lmb)) / math.factorial(k)

    def _poisson_over(self, lmb, threshold):
        """Calculate probability that X > threshold using Poisson."""
        prob_under_eq = 0
        for k in range(int(threshold) + 1):
            prob_under_eq += self._poisson_pmf(k, lmb)
        return 1.0 - prob_under_eq

    def _calculate_optimal_total(self, expected_value, market_name="Total Goals"):
        """
        Знаходить оптимальний варіант тоталу (ТБ або ТМ) на основі очікуваного значення.
        Розглядає варіанти відповідно до типу ринку і обирає найкращий баланс між ймовірністю та потенційним коефіцієнтом.
        Тепер враховує "цінність ставки" - баланс між ризиком та винагородою.
        """
        # Визначаємо пороги залежно від типу ринку
        if "Corners" in market_name:
            thresholds = [7.5, 8.5, 9.5, 10.5, 11.5]
            balance_range = (8.5, 10.5)
        elif "Cards" in market_name:
            thresholds = [2.5, 3.5, 4.5, 5.5, 6.5]
            balance_range = (3.5, 5.5)
        elif "Individual" in market_name:  # Individual Team Totals - інші правила
            thresholds = [0.5, 1.5, 2.5, 3.5]
            balance_range = (1.5, 2.5)  # для індивідуальних тоталів 1.5-2.5 це норма
        else:  # Total Goals
            thresholds = [0.5, 1.5, 2.5, 3.5, 4.5]
            balance_range = (2.0, 3.0)
        
        best_option = None
        best_score = -1
        
        for threshold in thresholds:
            # Ймовірність ТБ
            prob_over = self._poisson_over(expected_value, threshold)
            # Ймовірність ТМ
            prob_under = 1.0 - prob_over
            
            # Оцінюємо "цінність" варіанту з точки зору беттора:
            # - чим вищий коефіцієнт (нижча ймовірність), тим вища потенційна винагорода
            # - але ймовірність має бути достатньо високою для надійності
            
            # For OVER: higher total = higher odds, but lower probability
            if prob_over > 0.55:  # minimum probability
                # Сильний штраф за занадто безпечні варіанти (екстремально низькі тотали)
                if threshold <= min(thresholds):  # найнижчі пороги
                    # Для індивідуальних тоталів менший штраф за 0.5, бо це нормальний варіант
                    if "Individual" in market_name:
                        safety_penalty = max(0, (0.95 - prob_over) * 3)  # менший штраф
                    else:
                        safety_penalty = max(0, (0.90 - prob_over) * 5)  # дуже сильний штраф
                elif threshold <= min(thresholds) + 1.0:  # другі найнижчі пороги
                    safety_penalty = max(0, (0.85 - prob_over) * 2)  # зменшений штраф
                else:
                    safety_penalty = 0
                
                # Бонус за збалансований варіант (оптимальний ризик/винагорода)
                balance_bonus = 0.5 if balance_range[0] <= threshold <= balance_range[1] else 0
                
                # Бонус за "розумний ризик" - якщо ймовірність в діапазоні 0.60-0.75
                smart_risk_bonus = 0.3 if 0.60 <= prob_over <= 0.75 else 0
                
                # Штраф за занадто високу ймовірність (надзвичайно безпечно)
                high_prob_penalty = 0.4 if prob_over > 0.85 else 0
                
                score_over = prob_over - safety_penalty + balance_bonus + smart_risk_bonus - high_prob_penalty
                if score_over > best_score:
                    best_score = score_over
                    best_option = {
                        "selection": f"ТБ {threshold}",
                        "prob": prob_over,
                        "type": "OVER"
                    }
            
            # For UNDER: lower total = higher odds, but lower probability
            if prob_under > 0.55:  # minimum probability
                # Сильний штраф за занадто безпечні варіанти (екстремально високі тотали)
                if threshold >= max(thresholds):  # найвищі пороги
                    safety_penalty = max(0, (0.90 - prob_under) * 5)  # дуже сильний штраф
                elif threshold >= max(thresholds) - 1.0:  # другі найвищі пороги
                    safety_penalty = max(0, (0.85 - prob_under) * 3)
                else:
                    safety_penalty = 0
                
                # Бонус за збалансований варіант
                balance_bonus = 0.5 if balance_range[0] <= threshold <= balance_range[1] else 0
                
                # Бонус за "розумний ризик"
                smart_risk_bonus = 0.3 if 0.60 <= prob_under <= 0.75 else 0
                
                # Штраф за занадто високу ймовірність
                high_prob_penalty = 0.4 if prob_under > 0.85 else 0
                
                score_under = prob_under - safety_penalty + balance_bonus + smart_risk_bonus - high_prob_penalty
                if score_under > best_score:
                    best_score = score_under
                    best_option = {
                        "selection": f"ТМ {threshold}",
                        "prob": prob_under,
                        "type": "UNDER"
                    }
        
        return best_option

    def update_elo(self, elo_a, elo_b, score_a, score_b, k_factor=20):
        expected_a = self.calculate_elo_probability(elo_a, elo_b)
        actual_a = 1.0 if score_a > score_b else (0.5 if score_a == score_b else 0.0)
        new_elo_a = elo_a + k_factor * (actual_a - expected_a)
        new_elo_b = elo_b + k_factor * ((1.0 - actual_a) - (1.0 - expected_a))
        return new_elo_a, new_elo_b

    def calibrate_team_strength_from_user_bets(self):
        """POST-FACTO ANALYSIS (does NOT modify ELO / team ratings).

        Compares the AI model's per-prediction probability vs the market-implied
        probability (1 / user_odd) for every settled user bet. The user bet
        stores a COMBO string ("П1 / ТБ 2.5 / ..."), so it is split into parts
        and each part is matched against that match's predictions.

        Returns dict with overall / by_band / by_market accuracy stats.
        """
        with self.db.get_connection() as conn:
            bets = conn.execute("""
                SELECT ub.match_id, ub.selection, ub.odd, ub.status
                FROM user_bets ub
                WHERE ub.status IN ('WON','LOST')
                  AND ub.odd IS NOT NULL AND ub.odd > 0
            """).fetchall()
            preds = conn.execute("""
                SELECT match_id, selection, market, calculated_prob, is_hit
                FROM predictions
                WHERE calculated_prob IS NOT NULL
            """).fetchall()

        # index predictions per match by normalized selection text
        preds_by_match = {}
        for mid, sel, market, prob, hit in preds:
            key = " ".join((sel or "").upper().split())
            preds_by_match.setdefault(mid, {})[key] = (market or "?", float(prob), 1 if hit else 0)

        def _band(odd: float) -> str:
            if odd <= 1.5:
                return "Fav (<=1.5)"
            if odd <= 2.5:
                return "Even (1.5-2.5)"
            return "Long (>3.0)"

        bands, markets = {}, {}
        totals = {"n": 0, "model": 0, "market": 0, "edge": 0.0}
        unmatched_parts = 0

        for match_id, combo, user_odd, status in bets:
            parts = [p.strip() for p in (combo or "").split("/") if p.strip()]
            lookup = preds_by_match.get(match_id, {})
            matched_any = False
            for part in parts:
                rec = lookup.get(" ".join(part.upper().split()))
                if rec is None:
                    continue
                market, model_prob, hit_val = rec
                matched_any = True

                # Model "call" = probability above coin-flip; Market call = implied prob > 0.5
                model_correct = 1 if ((model_prob > 0.5) == bool(hit_val)) else 0
                market_prob = min(0.99, 1.0 / float(user_odd))
                market_correct = 1 if ((market_prob > 0.5) == bool(hit_val)) else 0
                edge = model_prob - market_prob

                for agg, key in ((bands, _band(user_odd)), (markets, market)):
                    b = agg.setdefault(key, {"n": 0, "model": 0, "market": 0, "edge": 0.0})
                    b["n"] += 1
                    b["model"] += model_correct
                    b["market"] += market_correct
                    b["edge"] += edge

                totals["n"] += 1
                totals["model"] += model_correct
                totals["market"] += market_correct
                totals["edge"] += edge

            if not matched_any:
                unmatched_parts += len(parts)

        def _finalize(d):
            out = {}
            for k, v in d.items():
                n = v["n"]
                out[k] = {
                    "n": n,
                    "model_acc": round(v["model"] / n * 100, 1) if n else 0.0,
                    "market_acc": round(v["market"] / n * 100, 1) if n else 0.0,
                    "avg_edge": round(v["edge"] / n, 4) if n else 0.0,
                }
            return out

        n = totals["n"]
        result = {
            "overall": {
                "n": n,
                "model_acc": round(totals["model"] / n * 100, 1) if n else 0.0,
                "market_acc": round(totals["market"] / n * 100, 1) if n else 0.0,
                "edge": round(totals["edge"] / n, 4) if n else 0.0,
            },
            "by_band": _finalize(bands),
            "by_market": _finalize(markets),
        }
        print("--- CALIBRATION REPORT (model vs market) ---")
        if n == 0:
            print("  No settled bets could be matched to predictions yet.")
        else:
            o = result["overall"]
            print(f"  Matched picks: {n} (unmatched combo parts skipped: {unmatched_parts})")
            print(f"  Overall: model {o['model_acc']}% vs market {o['market_acc']}% (avg edge {o['edge']:+.4f})")
            for band, d in result["by_band"].items():
                print(f"  [{band}] n={d['n']}  model={d['model_acc']}%  market={d['market_acc']}%  edge={d['avg_edge']:+.4f}")
            for mk, d in result["by_market"].items():
                print(f"  <{mk}> n={d['n']}  model={d['model_acc']}%  market={d['market_acc']}%  edge={d['avg_edge']:+.4f}")
        return result

    # ------------------------------------------------------------------
    # v30: Weekend Accumulator — ринкові кефі з `odds` (Bet365 знімки) ---
    _ODDS_CANON = {
        "1X2": ["П1", "X", "П2"],
        "Total Goals": ["ТБ 2.5", "ТМ 2.5", "ТБ 1.5", "ТМ 1.5",
                        "ТБ 3.5", "ТМ 3.5"],
        "BTTS": ["ОЗ - Так", "ОЗ - Ні"],
    }
    _LEAGUE_ALIASES = {
        "EPL": "Premier League", "LALIGA": "La Liga",
        "SERIEA": "Serie A", "BUNDESLIGA": "Bundesliga",
        "LIGUE1": "Ligue 1", "UCL": "UEFA Champions League",
        "UEL": "UEFA Europa League",
    }

    def _odds_snapshot(self, league, market, selection):
        """Найсвіжіший ринковий кеф з `odds` (Weekend Accumulator v30).

        Знімки пишуться в ДАТА-БД (godot_app/logicbet.db — канал CI/синку),
        тому читаємо напряму з data_db_path; у монолітному режимі це та сама
        БД. Шукаємо і за повною назвою ліги, і за кодом (EPL/LALIGA/...).
        Повертає float-кеф або None.
        """
        if not league:
            return None
        aliases = {league}
        for code, full in self._LEAGUE_ALIASES.items():
            if league == full or league == code or full in league:
                aliases.add(code)
                aliases.add(full)
        dpath = getattr(self.db, "data_db_path", None)
        try:
            import sqlite3 as _sq
            if dpath:
                conn = _sq.connect(dpath)
                try:
                    for lg in aliases:
                        r = conn.execute(
                            "SELECT opening_odd FROM odds "
                            "WHERE league = ? AND market = ? AND selection = ? "
                            "ORDER BY fetched_at DESC LIMIT 1",
                            (lg, market, selection)).fetchone()
                        if r and r[0]:
                            return float(r[0])
                finally:
                    conn.close()
            else:
                with self.db.get_connection() as conn:
                    for lg in aliases:
                        r = conn.execute(
                            "SELECT opening_odd FROM odds "
                            "WHERE league = ? AND market = ? AND selection = ? "
                            "ORDER BY fetched_at DESC LIMIT 1",
                            (lg, market, selection)).fetchone()
                        if r and r[0]:
                            return float(r[0])
        except Exception:                        # noqa: BLE001
            return None
        return None

    def _apply_market_odds(self, match_id, results):
        """v30: замінює bookmaker_odd=0 свіжими кефами з `odds`, рахує
        Expected Value і перераховує confidence_score_pct з EV-бустом/
        штрафом — прибирає відбір занижених кефів (типу 1.25 при prob
        0.82: EV всього +2.5%, тоді як альтернатива може дати +8%)."""
        league = None
        try:
            with self.db.get_connection() as conn:
                r = conn.execute("SELECT league FROM matches WHERE id=?",
                                 (match_id,)).fetchone()
                league = r[0] if r else None
        except Exception:                        # noqa: BLE001
            league = None
        if not league:
            return results
        for r in results:
            market = r.get("market")
            sel = (r.get("selection") or "").strip()
            canon = self._ODDS_CANON.get(market, [])
            snap = None
            for cand in canon:
                if sel.upper().startswith(cand.upper()):
                    snap = self._odds_snapshot(league, market, cand)
                    break
            if not snap:
                continue
            prob = float(r.get("calculated_prob") or 0)
            odd = float(snap)
            ev = prob * odd - 1.0
            r["bookmaker_odd"] = round(odd, 3)
            r["value_percentage"] = round(ev * 100, 1)
            r["ev_pct"] = round(ev * 100, 1)
            try:
                kb = self._karma_bonus(self._market_token(sel)) or 0.0
            except Exception:                    # noqa: BLE001
                kb = 0.0
            ev_adj = max(-0.15, min(0.15, ev))
            r["confidence_score_pct"] = min(99.0, round(
                prob * (1 + kb + ev_adj) * 100, 1))
        return results

    def _select_best_market(self, prediction):
        """Гарантований вибір ринку для прогнозу (v30-guard).

        Якщо ``market`` або ``selection`` порожні — замінюємо їх на значення
        за замовчуванням ('1X2' / 'P1'), що робить прогноз показуваним на сайті.
        Якщо ``bookmaker_odd`` порожній або <= 0 (наприклад, коли свіжі кефі з
        `odds` не знайдені ``_apply_market_odds`` нічого не змінив), обчислюємо
        його з розрахованої ймовірності:
            round(1.0 / max(calculated_prob, 0.05), 2)

        Це запобігає NULL-рядкам у `predictions`, через які сайт пише
        "Прогнози генерируются..." і залишає market/selection/odd порожніми.
        """
        market = prediction.get("market") or ""
        selection = prediction.get("selection") or ""
        prob = float(prediction.get("calculated_prob") or 0.0)

        # v31: НЕ перезаписуємо вже розрахований вибір статичним 'P1'.
        # Заповнюємо лише по-справжньому порожні поля; динамічний best-pick
        # (SQL-підзапит у fetch_predictions) обирає ринок для кнопки.
        if not market:
            market = "1X2"
        if not selection:
            selection = "X (Нічия)"

        odd = prediction.get("bookmaker_odd")
        try:
            odd = float(odd)
        except (TypeError, ValueError):
            odd = 0.0
        if odd <= 0:
            odd = round(1.0 / max(prob, 0.05), 2)

        return market, selection, odd

    def determine_predictions(self, match_id, home_id, away_id, bookmaker_odds_data, h_form="", a_form=""):
        match_date = None
        if match_id is not None:
            with self.db.get_connection() as conn:
                row = conn.execute("SELECT date FROM matches WHERE id = ?", (match_id,)).fetchone()
                if row and row[0]: match_date = row[0]
                
        probs = self.calculate_win_probabilities(home_id, away_id, h_form, a_form, match_id=match_id, match_date=match_date)
        h_tr = probs['h_trend']
        a_tr = probs['a_trend']
        
        p_h, p_d, p_a = probs['home'], probs['draw'], probs['away']
        results = []

        # Reward & Penalty engine: market karma from settled user bets.
        rep = self._compute_reputation()
        p1_pen = rep.get("П1", {}).get("penalty_last5", 0.0)
        p2_pen = rep.get("П2", {}).get("penalty_last5", 0.0)
        
        # 1. Main Winner (1X2 / DC)
        # Find the outcome with highest probability
        max_p = max(p_h, p_d, p_a)
        if max_p == p_h: selection, prob, tag = "Home", p_h, "STATISTICS"
        elif max_p == p_a: selection, prob, tag = "Away", p_a, "STATISTICS"
        else: selection, prob, tag = "Draw", p_d, "STATISTICS"
        
        # Override with special conditions if they are strong enough
        if p_h >= 0.60: 
            tag = "VALUE"
            selection, prob = "Home", p_h
        elif p_a >= 0.60: 
            tag = "RISK"
            selection, prob = "Away", p_a
        elif p_d > 0.38: 
            tag = "PARITY"
            selection, prob = "Draw", p_d
        elif abs(p_h - p_a) <= 0.12:
            if p_h >= p_a: selection, prob, tag = "1X", p_h + p_d, "ANALYSIS"
            else: selection, prob, tag = "X2", p_a + p_d, "ANALYSIS"

        # ------------------------------------------------------------------
        # Risk Safety Switch (auto-hedge): if the P1/P2 market has a net-negative
        # penalty balance over its last 5 settled bets, stop issuing that thin pick
        # and hedge it into the double-chance market (Home -> 1X, Away -> X2).
        # ------------------------------------------------------------------
        if selection in ("Home", "П1") and p1_pen < 0:
            selection, prob, tag = "1X", p_h + p_d, "RISK-TO-1X"
        elif selection in ("Away", "П2") and p2_pen < 0:
            selection, prob, tag = "X2", p_a + p_d, "RISK-TO-X2"
        
        # H2H Modifier for Tag
        if probs.get('h2h_count', 0) >= 3:
            tag = "H2H " + tag
            
        meta = self._last_meta
        ui_metadata = f"{tag}|H_ELO:{int(probs['home_elo'])}|A_ELO:{int(probs['away_elo'])}|H_AVG:{meta['h_avg']:.1f}|A_AVG:{meta['a_avg']:.1f}|H_TR:{meta['h_trend']}|A_TR:{meta['a_trend']}|H2H:{probs.get('h2h_count', 0)}"
        
        # --- Equal-rights markets: П1/Х/П2 + подвійні шанси, кожен з Confidence Score ---
        SEL_TXT = {"Home": "П1 (Господарі)", "Draw": "X (Нічия)", "Away": "П2 (Гості)",
                   "1X": "1X (Подвійний шанс)", "X2": "X2 (Подвійний шанс)",
                   "12": "12 (Подвійний шанс)"}
        risk_skip = set()
        if p1_pen < 0: risk_skip.add("Home")   # RISK-TO-1X: хедж явним 1X нижче
        if p2_pen < 0: risk_skip.add("Away")   # RISK-TO-X2: хедж явним X2 нижче
        equal_markets = [("Home", p_h), ("Draw", p_d), ("Away", p_a),
                         ("1X", p_h + p_d), ("X2", p_a + p_d), ("12", p_h + p_a)]
        for label, prob_v in equal_markets:
            if label in risk_skip:
                continue
            sel_txt = SEL_TXT[label]
            kb = self._karma_bonus(label)
            conf_pct = min(99.0, round(float(prob_v) * (1.0 + kb) * 100.0,))
            results.append({
                "match_id": match_id,
                "algorithm": ui_metadata,
                "market": "1X2/DC",
                "selection": sel_txt,
                "calculated_prob": round(float(prob_v), 4),
                "bookmaker_odd": 0.0,
                "value_percentage": 0.0,
                "confidence_level": "HIGH" if prob_v > self._learned_threshold(sel_txt) else "MEDIUM",
                "confidence_score_pct": conf_pct
            })
        
        # 2. Goals Totals (Over/Under) - ONE optimal option
        lmb_goals = h_tr['avg_goals'] + a_tr['avg_goals']
        
        # 2.1 Full Match Totals - choose one best option
        optimal_total = self._calculate_optimal_total(lmb_goals, "Total Goals")
        if optimal_total and optimal_total['prob'] > 0.60:  # minimum probability
            _tk = self._market_token("ТБ" if "Over" in str(optimal_total.get('selection','')) else "ТМ")
            _kb = self._karma_bonus(_tk)
            _conf_pct = min(99.0, round(float(optimal_total['prob']) * (1 + _kb) * 100,))
            results.append({
                "match_id": match_id, "algorithm": "GOALS (AI)", "market": "Total Goals",
                "selection": optimal_total['selection'], "calculated_prob": optimal_total['prob'], "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if optimal_total['prob'] > 0.75 else "MEDIUM",
                "confidence_score_pct": _conf_pct
            })
            
        # 2.3 Individual Team Totals (ITT) - one option per team
        # Use opponent's defense to refine individual expectations
        exp_h_goals = h_tr['avg_goals'] * a_tr['def_power']
        exp_a_goals = a_tr['avg_goals'] * h_tr['def_power']
        
        # Home Team Goals - one optimal option
        optimal_h_total = self._calculate_optimal_total(exp_h_goals, f"Individual Total {h_tr['team_name']}")
        if optimal_h_total and optimal_h_total['prob'] > 0.65:  # slightly higher threshold for individual
            _tk = self._market_token("ТБ" if "Over" in str(optimal_h_total.get('selection','')) else "ТМ")
            _kb = self._karma_bonus(_tk)
            _conf_pct = min(99.0, round(float(optimal_h_total['prob']) * (1 + _kb) * 100,))
            results.append({
                "match_id": match_id, "algorithm": "INDIVIDUAL TOTAL (AI)", "market": "Individual Total",
                "selection": f"{h_tr['team_name']} {optimal_h_total['selection']}",
                "calculated_prob": optimal_h_total['prob'], "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if optimal_h_total['prob'] > 0.80 else "MEDIUM",
                "confidence_score_pct": _conf_pct
            })
        
        # Away Team Goals - one optimal option
        optimal_a_total = self._calculate_optimal_total(exp_a_goals, f"Individual Total {a_tr['team_name']}")
        if optimal_a_total and optimal_a_total['prob'] > 0.65:  # slightly higher threshold for individual
            _tk = self._market_token("ТБ" if "Over" in str(optimal_a_total.get('selection','')) else "ТМ")
            _kb = self._karma_bonus(_tk)
            _conf_pct = min(99.0, round(float(optimal_a_total['prob']) * (1 + _kb) * 100,))
            results.append({
                "match_id": match_id, "algorithm": "INDIVIDUAL TOTAL (AI)", "market": "Individual Total",
                "selection": f"{a_tr['team_name']} {optimal_a_total['selection']}",
                "calculated_prob": optimal_a_total['prob'], "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if optimal_a_total['prob'] > 0.80 else "MEDIUM",
                "confidence_score_pct": _conf_pct
            })

        # 2.5  BTTS (ОЗ) — Both Teams to Score (Обидві заб'ють)
        p_home_scored = 1.0 - self._poisson_pmf(0, exp_h_goals)
        p_away_scored = 1.0 - self._poisson_pmf(0, exp_a_goals)
        prob_btts_yes = p_home_scored * p_away_scored
        prob_btts_no = 1.0 - prob_btts_yes
        if max(prob_btts_yes, prob_btts_no) > 0.60:
            if prob_btts_yes >= prob_btts_no:
                sel_btts = "ОЗ - Так"
                p_btts = prob_btts_yes
            else:
                sel_btts = "ОЗ - Ні"
                p_btts = prob_btts_no
            _kb = self._karma_bonus("ОЗ")
            _conf_pct = min(99.0, round(float(p_btts) * (1 + _kb) * 100,))
            results.append({
                "match_id": match_id, "algorithm": "BTTS (AI)", "market": "BTTS",
                "selection": sel_btts, "calculated_prob": p_btts, "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if p_btts > 0.75 else "MEDIUM",
                "confidence_score_pct": _conf_pct
            })
        # 2.4 1st Half Goals — ВИДАЛЕНО (v29): ринки 1-го тайму зняті з
        # обігу — у безкоштовному Football-Data фіді вони ненадійні.
        # Лишились: 1X2/DC, Загальні тотали (ТБ/ТМ 1.5-3.5), ОЗ (BTTS),
        # Кутові, Картки, Індивідуальні тотали.
            
        # 3. Corners Totals (Improved Model) - ONE optimal option
        # We blend: (Home Corners + Away Conceded) / 2 and (Away Corners + Home Conceded) / 2
        exp_h_corners = (h_tr['avg_corners'] + a_tr['avg_corners_conceded']) / 2.0
        exp_a_corners = (a_tr['avg_corners'] + h_tr['avg_corners_conceded']) / 2.0
        
        # Adjust based on expected dominance (Shots + Elo)
        # If a team is expected to have more shots than their average, boost their corners
        h_shot_mod = max(0.8, min(1.2, h_tr['avg_shots'] / 12.0))
        a_shot_mod = max(0.8, min(1.2, a_tr['avg_shots'] / 12.0))
        
        # Elo/Winner dominance factor
        if p_h > 0.60: exp_h_corners *= 1.1; exp_a_corners *= 0.9
        elif p_a > 0.60: exp_a_corners *= 1.1; exp_h_corners *= 0.9
        
        lmb_corners = (exp_h_corners * h_shot_mod) + (exp_a_corners * a_shot_mod)
        
        # Choose one optimal option for corners
        optimal_corners = self._calculate_optimal_total(lmb_corners, "Corners")
        if optimal_corners and optimal_corners['prob'] > 0.70:  # higher threshold for corners
            _tk = self._market_token("ТБ" if "Over" in str(optimal_corners.get('selection','')) else "ТМ")
            _kb = self._karma_bonus(_tk)
            _conf_pct = min(99.0, round(float(optimal_corners['prob']) * (1 + _kb) * 100,))
            results.append({
                "match_id": match_id, "algorithm": "CORNERS (AI+)", "market": "Corners",
                "selection": f"Corners {optimal_corners['selection']}", "calculated_prob": optimal_corners['prob'], "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if optimal_corners['prob'] > 0.80 else "MEDIUM",
                "confidence_score_pct": _conf_pct
            })


        # 4. Cards Totals - ONE optimal option
        lmb_cards = h_tr['avg_cards'] + a_tr['avg_cards']
        optimal_cards = self._calculate_optimal_total(lmb_cards, "Cards")
        if optimal_cards and optimal_cards['prob'] > 0.65:  # threshold for cards
            _tk = self._market_token("ТБ" if "Over" in str(optimal_cards.get('selection','')) else "ТМ")
            _kb = self._karma_bonus(_tk)
            _conf_pct = min(99.0, round(float(optimal_cards['prob']) * (1 + _kb) * 100,))
            results.append({
                "match_id": match_id, "algorithm": "CARDS (AI)", "market": "Cards",
                "selection": f"Cards {optimal_cards['selection']}", "calculated_prob": optimal_cards['prob'], "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if optimal_cards['prob'] > 0.75 else "MEDIUM",
                "confidence_score_pct": _conf_pct
            })

        # v30: Value із накопичувального календаря Bet365 — свіжі кефі
        # з `odds` (fetched_at) -> EV у value_percentage та EV-зважений
        # confidence (прибирає вибір занижених кефів типу 1.25).
        try:
            results = self._apply_market_odds(match_id, results)
        except Exception:                        # noqa: BLE001
            pass

        # v30-guard: гарантовано непорожній market/selection та додатній
        # bookmaker_odd для КОЖНОГО прогнозу. Якщо свіжі кефі з `odds` не
        # знайдені (_apply_market_odds нічого не змінив), bookmaker_odd
        # залишається 0.0 — це робить прогноз непоказуваним на сайті
        # ("Прогнози генерируются...") та залишає ринок/вибір/odd NULL.
        # Примусово заповнюємо значення, щоб жоден запис не був NULL/0.
        for _p in results:
            _m, _s, _o = self._select_best_market(_p)
            _p["market"] = _m
            _p["selection"] = _s
            _p["bookmaker_odd"] = _o
        return results
