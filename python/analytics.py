import random
import math

class BettingAnalytics:
    def __init__(self, db):
        self.db = db
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
            "Ligue 1": "Ліга 1 (Франція)"
        }

    def translate(self, text):
        return self.uk_dict.get(text, text)

    def calculate_elo_probability(self, elo_a, elo_b):
        exponent = (elo_b - elo_a) / 400.0
        expected_a = 1.0 / (1.0 + 10 ** exponent)
        return expected_a

    def calculate_local_trends(self, team_id):
        """Calculates form using a blend of Season Averages and Recent Matches."""
        with self.db.get_connection() as conn:
            # 1. Get Season Averages (Baseline from Standings)
            team_data = conn.execute("SELECT name, attack_rating, defense_rating, elo_rating FROM teams WHERE id = ?", (team_id,)).fetchone()
            t_name = team_data[0] if team_data else "Unknown"
            season_atk = team_data[1] if team_data and team_data[1] else 1.2
            season_def = team_data[2] if team_data and team_data[2] else 1.2
            my_elo = team_data[3] if team_data and team_data[3] else 1500.0
            
            # 2. Get Recent Match Form (Last 5 played matches in local DB)
            query = """
                SELECT m.home_score, m.away_score, m.home_team_id, 
                       (CASE WHEN m.home_team_id = ? THEN t2.elo_rating ELSE t1.elo_rating END) as opp_elo,
                       m.xg_h, m.xg_a, m.corners_h, m.corners_a, m.yellow_cards_h, m.yellow_cards_a, m.shots_on_h, m.shots_on_a,
                       m.ht_score_h, m.ht_score_a
                FROM matches m
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                WHERE (m.home_team_id = ? OR m.away_team_id = ?) 
                AND m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
                ORDER BY m.date DESC LIMIT 5
            """
            matches = conn.execute(query, (team_id, team_id, team_id)).fetchall()
        
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
        
        for m in matches:
            # Result from query has 12 columns, we unpack the first 4 for basic logic
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
            weighted_points += pts * weight_step
            total_weight += 3.0 * weight_step
            
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
            
        avg_recent = sum(recent_goals) / len(recent_goals)
        points_pct = weighted_points / total_weight if total_weight > 0 else 0
        
        # Extended Stats (Averages over last matches)
        # Results from query: 0:h_s, 1:a_s, 2:h_id, 3:opp_elo, 4:xg_h, 5:xg_a, 6:cor_h, 7:cor_a, 8:y_h, 9:y_a, 10:sh_h, 11:sh_a
        def _get_stat(m, home_idx, away_idx, team_id):
            return m[home_idx] if m[2] == team_id else m[away_idx]

        # Filter matches that actually have stats (if corners + shots > 0, we assume stats exist)
        stats_matches = [m for m in matches if (m[6] or 0) + (m[7] or 0) + (m[10] or 0) + (m[11] or 0) > 0]

        avg_xg = sum([_get_stat(m, 4, 5, team_id) or 0 for m in stats_matches]) / len(stats_matches) if stats_matches else season_atk
        
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
                
        avg_corners = sum([_get_stat(m, 6, 7, team_id) or 0 for m in stats_matches]) / len(stats_matches) if stats_matches else 4.8
        avg_corners_conceded = sum([_get_stat(m, 7, 6, team_id) or 0 for m in stats_matches]) / len(stats_matches) if stats_matches else 4.8
        avg_y_cards = sum([_get_stat(m, 8, 9, team_id) or 0 for m in stats_matches]) / len(stats_matches) if stats_matches else 1.8
        avg_shots = sum([_get_stat(m, 10, 11, team_id) or 0 for m in stats_matches]) / len(stats_matches) if stats_matches else 11.0

        
        # Filter matches that actually have Half-Time score data
        ht_matches = [m for m in matches if m[12] is not None and m[13] is not None]
        avg_goals_ht = sum([_get_stat(m, 12, 13, team_id) or 0 for m in ht_matches]) / len(ht_matches) if ht_matches else (season_atk * 0.45)

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


    def _calculate_home_away_factor(self, home_id, away_id):
        base_bonus = 50.0
        
        with self.db.get_connection() as conn:
            # Get last 10 HOME matches for home team
            h_matches = conn.execute("""
                SELECT home_score, away_score 
                FROM matches 
                WHERE home_team_id = ? AND status IN ('FT', 'AET', 'PEN', 'FINISHED')
                ORDER BY date DESC LIMIT 10
            """, (home_id,)).fetchall()
            
            # Get last 10 AWAY matches for away team
            a_matches = conn.execute("""
                SELECT home_score, away_score 
                FROM matches 
                WHERE away_team_id = ? AND status IN ('FT', 'AET', 'PEN', 'FINISHED')
                ORDER BY date DESC LIMIT 10
            """, (away_id,)).fetchall()
            
        h_pts = 0.0
        if h_matches:
            for m in h_matches:
                if m[0] is not None and m[1] is not None:
                    if m[0] > m[1]: h_pts += 1.0
                    elif m[0] == m[1]: h_pts += 0.5
            h_winrate = h_pts / len(h_matches) if len(h_matches) > 0 else 0.5
        else:
            h_winrate = 0.5
            
        a_pts = 0.0
        if a_matches:
            for m in a_matches:
                if m[0] is not None and m[1] is not None:
                    if m[1] > m[0]: a_pts += 1.0
                    elif m[1] == m[0]: a_pts += 0.5
            a_winrate = a_pts / len(a_matches) if len(a_matches) > 0 else 0.3
        else:
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

    def calculate_win_probabilities(self, home_id, away_id, home_form="", away_form=""):
        with self.db.get_connection() as conn:
            h_data = conn.execute("SELECT elo_rating, name FROM teams WHERE id = ?", (home_id,)).fetchone()
            a_data = conn.execute("SELECT elo_rating, name FROM teams WHERE id = ?", (away_id,)).fetchone()

        if not h_data or not a_data:
            return {
                "home": 0.4, "draw": 0.3, "away": 0.3,
                "home_elo": 1500, "away_elo": 1500,
                "h_trend": {"avg_goals": 1.2, "label": "Unknown"},
                "a_trend": {"avg_goals": 1.2, "label": "Unknown"},
                "h2h_count": 0
            }

        home_elo = h_data[0]
        away_elo = a_data[0]

        # Dynamic Home Advantage
        home_bonus = self._calculate_home_away_factor(home_id, away_id)
        win_prob = self.calculate_elo_probability(home_elo + home_bonus, away_elo)
        
        # Hybrid Trends
        h_trend = self.calculate_local_trends(home_id)
        a_trend = self.calculate_local_trends(away_id)
        
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
        h2h = self.db.fetch_h2h_matches(home_id, away_id)
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

    def update_elo(self, elo_a, elo_b, score_a, score_b, k_factor=20):
        expected_a = self.calculate_elo_probability(elo_a, elo_b)
        actual_a = 1.0 if score_a > score_b else (0.5 if score_a == score_b else 0.0)
        new_elo_a = elo_a + k_factor * (actual_a - expected_a)
        new_elo_b = elo_b + k_factor * ((1.0 - actual_a) - (1.0 - expected_a))
        return new_elo_a, new_elo_b

    def determine_predictions(self, match_id, home_id, away_id, bookmaker_odds_data, h_form="", a_form=""):
        probs = self.calculate_win_probabilities(home_id, away_id, h_form, a_form)
        h_tr = probs['h_trend']
        a_tr = probs['a_trend']
        
        p_h, p_d, p_a = probs['home'], probs['draw'], probs['away']
        results = []
        
        # 1. Main Winner (1X2 / DC)
        # Refined Tag Logic
        selection, prob, tag = "Home", p_h, "СТАТИСТИКА"
        
        if p_h >= 0.55: 
            tag = "💎 ЦІННІСТЬ"
            selection = "Home"
            prob = p_h
        elif p_a >= 0.55: 
            tag = "🔥 РИЗИК"
            selection = "Away"
            prob = p_a
        elif p_d > 0.35: 
            tag = "⚖️ ПАРИТЕТ"
            selection = "Draw"
            prob = p_d
        elif abs(p_h - p_a) <= 0.15:
            if p_h >= p_a: selection, prob, tag = "1X", p_h + p_d, "АНАЛІЗ"
            else: selection, prob, tag = "X2", p_a + p_d, "АНАЛІЗ"
        
        # H2H Modifier for Tag
        if probs.get('h2h_count', 0) >= 3:
            tag = "📊 H2H " + tag
            
        meta = self._last_meta
        ui_metadata = f"{tag}|H_ELO:{int(probs['home_elo'])}|A_ELO:{int(probs['away_elo'])}|H_AVG:{meta['h_avg']:.1f}|A_AVG:{meta['a_avg']:.1f}|H_TR:{meta['h_trend']}|A_TR:{meta['a_trend']}|H2H:{probs.get('h2h_count', 0)}"
        
        results.append({
            "match_id": match_id,
            "algorithm": ui_metadata,
            "market": "1X2/DC",
            "selection": self.translate(selection),
            "calculated_prob": prob,
            "bookmaker_odd": 0.0,
            "value_percentage": 0.0,
            "confidence_level": "HIGH" if prob > 0.65 else "MEDIUM"
        })
        
        # 2. Goals Totals (Over/Under)
        lmb_goals = h_tr['avg_goals'] + a_tr['avg_goals']
        
        # 2.1 Full Match Totals
        for threshold in [2.5, 3.5]:
            prob_over = self._poisson_over(lmb_goals, threshold)
            prob_under = 1.0 - prob_over
            if prob_over > 0.65:
                results.append({
                    "match_id": match_id, "algorithm": "ГОЛИ", "market": "Total Goals",
                    "selection": f"ТБ {threshold}", "calculated_prob": prob_over, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if prob_over > 0.75 else "MEDIUM"
                })
            elif prob_under > 0.65:
                results.append({
                    "match_id": match_id, "algorithm": "ГОЛИ", "market": "Total Goals",
                    "selection": f"ТМ {threshold}", "calculated_prob": prob_under, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if prob_under > 0.75 else "MEDIUM"
                })
            
        # 2.3 Individual Team Totals (ITT)
        # Use opponent's defense to refine individual expectations
        exp_h_goals = h_tr['avg_goals'] * a_tr['def_power']
        exp_a_goals = a_tr['avg_goals'] * h_tr['def_power']
        
        # Home Team Goals
        for threshold in [0.5, 1.5]:
            p_h_over = self._poisson_over(exp_h_goals, threshold)
            if p_h_over > 0.70:
                results.append({
                    "match_id": match_id, "algorithm": "ІНД. ТОТАЛ", "market": "Individual Total",
                    "selection": f"{h_tr['team_name']} ТБ {threshold}", "calculated_prob": p_h_over, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if p_h_over > 0.80 else "MEDIUM"
                })
        
        # Away Team Goals
        for threshold in [0.5, 1.5]:
            p_a_over = self._poisson_over(exp_a_goals, threshold)
            if p_a_over > 0.70:
                results.append({
                    "match_id": match_id, "algorithm": "ІНД. ТОТАЛ", "market": "Individual Total",
                    "selection": f"{a_tr['team_name']} ТБ {threshold}", "calculated_prob": p_a_over, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if p_a_over > 0.80 else "MEDIUM"
                })

        # 2.4 1st Half Goals
        lmb_ht = h_tr['avg_goals_ht'] + a_tr['avg_goals_ht']
        prob_ht05 = self._poisson_over(lmb_ht, 0.5)
        prob_ht_u05 = 1.0 - prob_ht05
        
        if prob_ht05 > 0.70:
            results.append({
                "match_id": match_id, "algorithm": "ГОЛИ (1-й ТАЙМ)", "market": "1st Half Goals",
                "selection": "ТБ 0.5 (1-й тайм)", "calculated_prob": prob_ht05, "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if prob_ht05 > 0.80 else "MEDIUM"
            })
        elif prob_ht_u05 > 0.70:
            results.append({
                "match_id": match_id, "algorithm": "ГОЛИ (1-й ТАЙМ)", "market": "1st Half Goals",
                "selection": "ТМ 0.5 (1-й тайм)", "calculated_prob": prob_ht_u05, "bookmaker_odd": 0.0,
                "value_percentage": 0.0, "confidence_level": "HIGH" if prob_ht_u05 > 0.80 else "MEDIUM"
            })
            
        # 3. Corners Totals (Improved Model)
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
        
        # Use more conservative thresholds for corners to improve accuracy
        for threshold in [8.5, 9.5, 10.5]:
            prob_c_over = self._poisson_over(lmb_corners, threshold)
            prob_c_under = 1.0 - prob_c_over
            
            # Require higher probability (75%+) for corner predictions
            if prob_c_over > 0.75:
                results.append({
                    "match_id": match_id, "algorithm": "КУТОВІ (AI+)", "market": "Corners",
                    "selection": f"Кутові ТБ {threshold}", "calculated_prob": prob_c_over, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if prob_c_over > 0.85 else "MEDIUM"
                })
                break # Only suggest one total per match (the most confident one)
            elif prob_c_under > 0.75:
                results.append({
                    "match_id": match_id, "algorithm": "КУТОВІ (AI+)", "market": "Corners",
                    "selection": f"Кутові ТМ {threshold}", "calculated_prob": prob_c_under, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if prob_c_under > 0.85 else "MEDIUM"
                })
                break


        # 4. Cards Totals
        lmb_cards = h_tr['avg_cards'] + a_tr['avg_cards']
        for threshold in [3.5, 4.5]:
            prob_card_over = self._poisson_over(lmb_cards, threshold)
            prob_card_under = 1.0 - prob_card_over
            if prob_card_over > 0.65:
                results.append({
                    "match_id": match_id, "algorithm": "КАРТКИ", "market": "Cards",
                    "selection": f"Картки ТБ {threshold}", "calculated_prob": prob_card_over, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if prob_card_over > 0.75 else "MEDIUM"
                })
            elif prob_card_under > 0.65:
                results.append({
                    "match_id": match_id, "algorithm": "КАРТКИ", "market": "Cards",
                    "selection": f"Картки ТМ {threshold}", "calculated_prob": prob_card_under, "bookmaker_odd": 0.0,
                    "value_percentage": 0.0, "confidence_level": "HIGH" if prob_card_under > 0.75 else "MEDIUM"
                })

        return results
