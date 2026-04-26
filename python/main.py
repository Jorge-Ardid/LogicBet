from database import LogicBetDB
from api_client import APIFootballClient
from analytics import BettingAnalytics
from multi_source_sync import MultiSourceSyncEngine
from config_manager import ConfigManager
from datetime import datetime, timedelta
import sqlite3
import json
import os
import sys

def export_to_json(db):
    """Exports current predictions, history, bankroll and user bets to a JSON file for mobile sync."""
    print("\n[EXPORT] Generating full logicbet_export.json for cloud sync...")
    
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Fetch Recent & Upcoming Matches (with stats)
            query = """
                SELECT m.*, t1.name as home_name, t2.name as away_name,
                       GROUP_CONCAT(p.selection, ' / ') as ai_prediction,
                       GROUP_CONCAT(p.is_hit, '|') as ai_hit
                FROM matches m
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                LEFT JOIN (
                    SELECT * FROM predictions 
                    ORDER BY (CASE WHEN market = '1X2/DC' THEN 0 ELSE 1 END) ASC, calculated_prob DESC
                    LIMIT -1
                ) p ON m.id = p.match_id
                WHERE DATE(m.date) >= DATE('now', '-7 days')
                GROUP BY m.id
                ORDER BY m.date DESC
            """
            rows = cursor.execute(query).fetchall()
            matches = [dict(row) for row in rows]
            
            # 2. Fetch User Bets (History)
            cursor.execute("""
                SELECT ub.*, t1.name as home_name, t2.name as away_name, m.date, m.home_score, m.away_score
                FROM user_bets ub
                JOIN matches m ON ub.match_id = m.id
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                ORDER BY ub.id DESC
            """)
            user_bets = [dict(row) for row in cursor.fetchall()]
            
            # 3. Fetch Prediction History (for Stats tab)
            cursor.execute("""
                SELECT p.*, m.date 
                FROM predictions p
                JOIN matches m ON p.match_id = m.id
                WHERE p.is_hit IS NOT NULL
                ORDER BY m.date DESC LIMIT 500
            """)
            predictions_history = [dict(row) for row in cursor.fetchall()]

            # 4. Fetch Teams (for Search tab)
            cursor.execute("SELECT id, name, elo_rating, current_form, rank, points FROM teams")
            teams = [dict(row) for row in cursor.fetchall()]
            
            # 5. Fetch Full Config
            cursor.execute("SELECT key, value FROM config")
            config = {row['key']: row['value'] for row in cursor.fetchall()}
            
            # 6. Summary Stats
            cursor.execute("SELECT COUNT(*) FROM predictions WHERE is_hit IS NOT NULL")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM predictions WHERE is_hit = 1")
            hits = cursor.fetchone()[0]
            
            data = {
                "last_updated": datetime.now().isoformat(),
                "config": config,
                "ai_stats": {
                    "total": total,
                    "hits": hits,
                    "acc": (hits / total * 100) if total > 0 else 0
                },
                "matches": matches,
                "user_bets": user_bets,
                "predictions_history": predictions_history,
                "teams": teams
            }
            
            # Save to current directory (in python/ folder)
            export_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "logicbet_export.json"))
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        print(f"  [EXPORT] Success! Full state exported to: {export_path}")
    except Exception as e:
        print(f"  [EXPORT] ❌ Failed to export JSON: {e}")
        import traceback
        traceback.print_exc()


# Statistics are now part of the matches table. No separate fetch needed.



def show_recent_matches_statistics(db):
    """Show statistics for recent matches"""
    print("\n=== RECENT MATCHES STATISTICS ===")
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if columns exist
            cursor.execute("PRAGMA table_info(matches)")
            cols = [c[1] for c in cursor.fetchall()]
            if "shots_on_h" not in cols:
                print("  [INFO] Statistics columns not yet present in database.")
                return

            cursor.execute("""
                SELECT m.id, 
                       t1.name as home_team,
                       t2.name as away_team, 
                       m.home_score, m.away_score, m.date, m.status, m.league,
                       m.shots_on_h, m.shots_on_a, m.corners_h, m.corners_a,
                       m.yellow_cards_h, m.yellow_cards_a, m.possession_h, m.possession_a,
                       m.xg_h, m.xg_a
                FROM matches m
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                WHERE m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
                ORDER BY m.date DESC
                LIMIT 5
            """)
            
            matches = cursor.fetchall()
            if not matches:
                print("No matches with statistics found")
                return
            
            for i, match in enumerate(matches):
                print(f"\n{i+1}. {match[1]} vs {match[2]}")
                print(f"   Score: {match[3]}-{match[4]} ({match[6]})")
                
                if match[8] is not None:
                    print(f"   Shots: {match[8]} - {match[9]} | Corners: {match[10]} - {match[11]}")
                    print(f"   Cards (Y): {match[12]} - {match[13]} | Poss: {match[14]}% - {match[15]}%")
                    print(f"   xG: {match[16]} - {match[17]}")
                else:
                    print("   Statistics: Not available yet")
    except Exception as e:
        print(f"  [DEBUG] Could not show statistics: {e}")

def recalculate_elo_from_history(db, analytics):
    """Processes finished matches and updates team Elo ratings locally."""
    print("--- UPDATING LOCAL ELO RATINGS FROM FINISHED MATCHES ---")
    with db.get_connection() as conn:
        # Find matches that are finished but not yet processed for Elo
        query = """
            SELECT id, home_team_id, away_team_id, home_score, away_score 
            FROM matches 
            WHERE status IN ('FT', 'AET', 'PEN', 'FINISHED') AND elo_processed = 0
            ORDER BY date ASC
        """
        matches = conn.execute(query).fetchall()
        
        for m in matches:
            m_id, h_id, a_id, h_s, a_s = m
            
            # Get current ratings
            h_elo = conn.execute("SELECT elo_rating FROM teams WHERE id = ?", (h_id,)).fetchone()[0]
            a_elo = conn.execute("SELECT elo_rating FROM teams WHERE id = ?", (a_id,)).fetchone()[0]
            
            # Calculate new ratings
            new_h, new_a = analytics.update_elo(h_elo, a_elo, h_s, a_s)
            
            delta_h = new_h - h_elo
            delta_a = new_a - a_elo
            
            # Save back to teams
            conn.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (new_h, h_id))
            conn.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (new_a, a_id))
            
            # Save delta to match
            conn.execute("UPDATE matches SET h_elo_change = ?, a_elo_change = ? WHERE id = ?", (delta_h, delta_a, m_id))
            
            # --- Update Team Form (Last 5) ---
            for t_id in [h_id, a_id]:
                form_query = """
                    SELECT home_score, away_score, home_team_id 
                    FROM matches 
                    WHERE (home_team_id = ? OR away_team_id = ?) AND status IN ('FT', 'FINISHED')
                    ORDER BY date DESC LIMIT 5
                """
                hist = conn.execute(form_query, (t_id, t_id)).fetchall()
                form_str = ""
                for h in reversed(hist): # W: Winner, D: Draw, L: Loser
                    hs, ascores, h_team = h
                    is_h = (h_team == t_id)
                    my_s = hs if is_h else ascores
                    op_s = ascores if is_h else hs
                    if my_s > op_s: form_str += "W"
                    elif my_s < op_s: form_str += "L"
                    else: form_str += "D"
                conn.execute("UPDATE teams SET current_form = ? WHERE id = ?", (form_str, t_id))

            # Mark match as processed
            conn.execute("UPDATE matches SET elo_processed = 1 WHERE id = ?", (m_id,))
            print(f"  [ELO/FORM] Updated {m_id}: New ratings and form string applied.")
        
        conn.commit()

def sync_match_stats(db, api):
    """Fetches statistics for finished matches that don't have them yet."""
    if not api or api.is_mock: return
    print("--- SYNCING MATCH STATISTICS ---")
    
    with db.get_connection() as conn:
        # We only want to fetch stats for matches that are finished and haven't had stats fetched.
        # We limit to 3 matches per run to conserve API quota.
        query = """
            SELECT id, remote_id
            FROM matches 
            WHERE status IN ('FT', 'AET', 'PEN') AND stats_fetched = 0 AND remote_id IS NOT NULL
            ORDER BY date DESC LIMIT 3
        """
        matches = conn.execute(query).fetchall()
        if not matches:
            print("  [STATS] All recent finished matches already have statistics or none available.")
            return

        for m_id, r_id in matches:
            print(f"  > Fetching stats for Match ID: {m_id} (Remote: {r_id})...")
            stats_data = api.fetch_match_statistics(r_id)
            
            stats = {}
            if stats_data and len(stats_data) >= 2:
                # Typically array of 2 elements (home and away team stats)
                # First team in array might be home or away, but usually 0 is home, 1 is away.
                # Let's map it by their structure:
                for team_stats in stats_data:
                    # Depending on api-sports structure: 
                    # {"team": {"id": X}, "statistics": [{"type": "Shots on Goal", "value": 5}, ...]}
                    is_home = (team_stats == stats_data[0]) # naive approach, API usually returns home first
                    
                    for stat in team_stats.get("statistics", []):
                        val = stat.get("value")
                        if val is None:
                            val = 0
                            
                        # Some values might be percentages like "55%" 
                        if isinstance(val, str) and "%" in val:
                            val = val.replace("%", "")
                            
                        try:
                            val = float(val) if '.' in str(val) else int(val)
                        except:
                            val = 0
                            
                        t = stat.get("type", "")
                        suffix = "_h" if is_home else "_a"
                        
                        if t == "Corner Kicks": stats["corners" + suffix] = int(val)
                        elif t == "Yellow Cards": stats["yellow_cards" + suffix] = int(val)
                        elif t == "Red Cards": stats["red_cards" + suffix] = int(val)
                        elif t == "Shots on Goal": stats["shots_on" + suffix] = int(val)
                        elif t == "Shots off Goal": stats["shots_off" + suffix] = int(val)
                        elif t == "expected_goals": stats["xg" + suffix] = float(val)
                        elif t == "Ball Possession": stats["possession" + suffix] = int(val)
                
                db.update_match_stats(m_id, stats)
                print(f"  [STATS] Saved stats for Match ID {m_id} (Corners: {stats.get('corners_h',0)}-{stats.get('corners_a',0)})")
            else:
                # Mark as fetched anyway so we don't retry forever on matches with no stats
                db.update_match_stats(m_id, {"stats_fetched": 1})
                print(f"  [STATS] No statistics available for Match ID {m_id}. Marked as fetched.")

def evaluate_virtual_bets(db):
    """Evaluates all pending predictions against finished match results."""
    print("--- EVALUATING VIRTUAL BETS ---")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Include 'FINISHED' and 'FT' statuses
        query = """
            SELECT p.id, p.selection, m.home_score, m.away_score, 
                   t1.name as h_name, t2.name as a_name,
                   m.ht_score_h, m.ht_score_a
            FROM predictions p
            JOIN matches m ON p.match_id = m.id
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE p.is_hit IS NULL AND m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
        """
        preds = cursor.execute(query).fetchall()
        
        evaluated = 0
        hits = 0
        for p_id, sel, hs, as_t, h_name, a_name, hth, hta in preds:
            if hs is None or as_t is None: continue
            
            is_hit = 0
            # Normalize selection string for matching
            s = sel.upper()
            h_n = h_name.upper()
            a_n = a_name.upper()
            
            if "1-Й ТАЙМ" in s:
                if hth is None or hta is None: continue # Skip if no HT data
                total_ht = hth + hta
                if "ТБ 0.5" in s: is_hit = 1 if total_ht > 0.5 else 0
                elif "ТМ 0.5" in s: is_hit = 1 if total_ht < 0.5 else 0
                # Add more HT markets if needed
            elif h_n in s and ("ТБ" in s or "ТМ" in s):
                threshold = 0.5
                if "1.5" in s: threshold = 1.5
                if "ТБ" in s: is_hit = 1 if hs > threshold else 0
                else: is_hit = 1 if hs < threshold else 0
            elif a_n in s and ("ТБ" in s or "ТМ" in s):
                threshold = 0.5
                if "1.5" in s: threshold = 1.5
                if "ТБ" in s: is_hit = 1 if as_t > threshold else 0
                else: is_hit = 1 if as_t < threshold else 0
            elif "П1" in s or "HOME" in s:
                is_hit = 1 if hs > as_t else 0
            elif "П2" in s or "AWAY" in s:
                is_hit = 1 if as_t > hs else 0
            elif "X (" in s or "НІЧИЯ" in s or s == "DRAW" or " X" in s:
                is_hit = 1 if hs == as_t else 0
            elif "1X" in s or "1 X" in s:
                is_hit = 1 if hs >= as_t else 0
            elif "X2" in s or "X 2" in s:
                is_hit = 1 if as_t >= hs else 0
            elif "БІЛЬШЕ" in s or "OVER" in s or "ТБ" in s:
                # Extract number if possible, or default to 2.5
                threshold = 2.5
                if "1.5" in s: threshold = 1.5
                elif "3.5" in s: threshold = 3.5
                elif "8.5" in s: threshold = 8.5
                is_hit = 1 if (hs + as_t) > threshold else 0
            elif "МЕНШЕ" in s or "UNDER" in s or "ТМ" in s:
                threshold = 2.5
                if "1.5" in s: threshold = 1.5
                is_hit = 1 if (hs + as_t) < threshold else 0
                
            cursor.execute("UPDATE predictions SET is_hit = ? WHERE id = ?", (is_hit, p_id))
            evaluated += 1
            if is_hit: hits += 1
            
        conn.commit()
        if evaluated > 0:
            print(f"  [EVAL] Evaluated {evaluated} AI predictions. Accuracy: {(hits/evaluated)*100:.1f}%")
        else:
            print("  [EVAL] No pending AI predictions to evaluate.")

def heal_database(db, conn):

    """Fixes incorrect league names and IDs for existing matches in the DB."""
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET value = '' WHERE key = 'sync_error'")
    # Correct mapping for IDs
    mapping = {
        39: "Прем'єр-ліга (Англія)",
        140: "Ла Ліга (Іспанія)",
        78: "Бундесліга (Німеччина)",
        61: "Ліга 1 (Франція)",
        135: "Серія А (Італія)",
        88: "Ередивізі (Нідерланди)",
        94: "Прімейра-ліга (Португалія)",
        40: "Чемпіоншип (Англія)"
    }
    for l_id, name in mapping.items():
        cursor.execute("UPDATE matches SET league = ? WHERE league_id = ?", (name, l_id))
    
    # Fix league names according to current ID mapping
    for l_id, name in mapping.items():
        cursor.execute("UPDATE matches SET league = ? WHERE league_id = ? AND league != ?", (name, l_id, name))
    
    # Merge Duplicate Teams (normalized names collision)

    cursor.execute("SELECT id, name FROM teams")
    all_teams = cursor.fetchall()
    canonical_teams = {} # normalized_name -> id
    
    for t_id, t_name in all_teams:
        norm_name = db._normalize_name(t_name)
        if norm_name in canonical_teams:

            old_id = t_id
            new_id = canonical_teams[norm_name]
            # Merge: update all matches to use the new_id
            cursor.execute("UPDATE matches SET home_team_id = ? WHERE home_team_id = ?", (new_id, old_id))
            cursor.execute("UPDATE matches SET away_team_id = ? WHERE away_team_id = ?", (new_id, old_id))
            # Also merge synonyms to point to the new_id
            cursor.execute("UPDATE team_synonyms SET team_id = ? WHERE team_id = ?", (new_id, old_id))
            cursor.execute("DELETE FROM teams WHERE id = ?", (old_id,))
            print(f"  [HEAL] Merged team ID {old_id} into {new_id} ({t_name})")
        else:
            canonical_teams[t_name] = t_id

    # --- NEW: Delete Duplicate Matches ---
    # Find matches with same teams and same date
    cursor.execute("""
        DELETE FROM matches 
        WHERE id IN (
            SELECT m1.id 
            FROM matches m1
            JOIN matches m2 ON m1.home_team_id = m2.home_team_id 
                            AND m1.away_team_id = m2.away_team_id
                            AND DATE(m1.date) = DATE(m2.date)
                            AND m1.id > m2.id
        )
    """)
    if cursor.rowcount > 0:
        print(f"  [HEAL] Deleted {cursor.rowcount} duplicate matches.")
    
    conn.commit()

def evaluate_user_bets(db):
    """Evaluates user's personal bets and updates bankroll with winnings."""
    print("--- EVALUATING USER BETS & BANKROLL ---")
    with db.get_connection() as conn:
        heal_database(db, conn) # Fix league names and merge teams
        cursor = conn.cursor()


        
        # Get pending user bets for finished matches
        query = """
            SELECT ub.id, ub.selection, ub.stake, ub.odd, m.home_score, m.away_score, 
                   t1.name as h_name, t2.name as a_name,
                   m.ht_score_h, m.ht_score_a, ub.match_id
            FROM user_bets ub
            JOIN matches m ON ub.match_id = m.id
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE ub.status = 'PENDING' AND m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
        """
        user_bets = cursor.execute(query).fetchall()
        
        if not user_bets:
            print("  [USER] No pending user bets to evaluate.")
            return

        # Get current bankroll
        cursor.execute("SELECT value FROM config WHERE key = 'bankroll'")
        res = cursor.fetchone()
        current_bankroll = float(res[0]) if res else 1000.0
        
        initial_bankroll = current_bankroll
        processed = 0
        wins = 0
        
        for b_id, sel, stake, odd, hs, as_t, h_name, a_name, hth, hta, m_id in user_bets:
            if hs is None or as_t is None: continue
            
            is_hit = False
            s = sel.upper()
            h_n = h_name.upper()
            a_n = a_name.upper()
            
            # Reusing the hit detection logic from evaluate_virtual_bets
            if "1-Й ТАЙМ" in s:
                if hth is not None and hta is not None:
                    total_ht = hth + hta
                    if "ТБ 0.5" in s: is_hit = total_ht > 0.5
                    elif "ТМ 0.5" in s: is_hit = total_ht < 0.5
            elif h_n in s and ("ТБ" in s or "ТМ" in s):
                threshold = 1.5 if "1.5" in s else 0.5
                if "ТБ" in s: is_hit = hs > threshold
                else: is_hit = hs < threshold
            elif a_n in s and ("ТБ" in s or "ТМ" in s):
                threshold = 1.5 if "1.5" in s else 0.5
                if "ТБ" in s: is_hit = as_t > threshold
                else: is_hit = as_t < threshold
            elif "П1" in s or "HOME" in s:
                is_hit = hs > as_t
            elif "П2" in s or "AWAY" in s:
                is_hit = as_t > hs
            elif "X (" in s or "НІЧИЯ" in s or s == "DRAW" or " X" in s:
                is_hit = hs == as_t
            elif "1X" in s or "1 X" in s:
                is_hit = hs >= as_t
            elif "X2" in s or "X 2" in s:
                is_hit = as_t >= hs
            elif "БІЛЬШЕ" in s or "OVER" in s or "ТБ" in s:
                threshold = 2.5
                if "1.5" in s: threshold = 1.5
                elif "3.5" in s: threshold = 3.5
                elif "8.5" in s: threshold = 8.5
                is_hit = (hs + as_t) > threshold
            elif "МЕНШЕ" in s or "UNDER" in s or "ТМ" in s:
                threshold = 2.5
                if "1.5" in s: threshold = 1.5
                is_hit = (hs + as_t) < threshold
                
            if is_hit:
                win_amount = stake * odd
                profit = win_amount - stake
                cursor.execute("UPDATE user_bets SET status = 'WON', profit = ? WHERE id = ?", (profit, b_id))
                current_bankroll += win_amount
                wins += 1
                print(f"  [USER] Bet {b_id} WON! +{win_amount:.2f} to bankroll.")
            else:
                cursor.execute("UPDATE user_bets SET status = 'LOST', profit = ? WHERE id = ?", (-stake, b_id))
                print(f"  [USER] Bet {b_id} LOST.")
            
            processed += 1
            
        # Update bankroll in config if changed
        if current_bankroll != initial_bankroll:
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('bankroll', ?)", (str(current_bankroll),))
            print(f"  [USER] Bankroll updated: {initial_bankroll:.2f} -> {current_bankroll:.2f}")
            
        conn.commit()
        print(f"  [USER] Processed {processed} bets. Wins: {wins}")


def sync_live_data(db, api, engine, target_ids):
    """Fetches matches and populates with deep statistical form."""
    
    # Free plan only allows Yesterday, Today, Tomorrow (3 days)
    dates = []
    for i in [-1, 0, 1]: 
        dates.append((datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"))
    
    print("\n--- STARTING OPTIMIZED SYNC (FREE PLAN LIMITS) ---")
    all_fixtures = []
    for d in dates:
        print(f"  > Fetching fixtures for {d}...")
        fixtures = api.fetch_fixtures(date=d)
        if fixtures:
            all_fixtures.append((d, fixtures))
        else:
            # Check if this was an API error (limit, etc)
            pass
    
    if not all_fixtures:
        print("!!! WARNING: No fixtures returned from API. !!!")
        db.set_config("sync_error", "Помилка API (перевірте ліміт або інтернет)")
        return

    # WE NO LONGER DELETE DATA. Matches are updated via ON CONFLICT (remote_id).
    
    for d, fixtures in all_fixtures:
        print(f"[{d}] Processing Matches...")
        
        for obj in fixtures:
            l_id = obj['league']['id']
            if l_id not in target_ids: continue
            
            fixture, teams, goals = obj['fixture'], obj['teams'], obj['goals']
            h_id = db.add_team_if_not_exists(teams['home']['name'])
            a_id = db.add_team_if_not_exists(teams['away']['name'])
            
            status = fixture['status']['short']
            h_score = goals['home']
            a_score = goals['away']
            
            print(f"  > [{status}] {teams['home']['name']} {h_score or ''} : {a_score or ''} {teams['away']['name']}")
            
            # Update match record with scores and status
            # We skip stats fetching because Free Plan blocks current season stats
            m_id = db.insert_match(fixture['id'], fixture['date'], engine.translate(obj['league']['name']), h_id, a_id, h_score, a_score, status, "", "", l_id)
            
            # Use ELO-only prediction (Zero extra API calls)
            preds = engine.determine_predictions(m_id, h_id, a_id, None, "", "")
            
            # Update predictions
            with db.get_connection() as conn:
                conn.execute("DELETE FROM predictions WHERE match_id = ?", (m_id,))
            for p in preds:
                db.insert_prediction(p['match_id'], p['algorithm'], p['market'], p['selection'], p['calculated_prob'], p['bookmaker_odd'], p['value_percentage'], p['confidence_level'])

def initialize_elo_from_standings(db, api, league_id):
    """Uses the current league table to give teams a realistic starting Elo."""
    print(f"--- INITIALIZING ELO FROM STANDINGS (LEAGUE {league_id}) ---")
    standings = api.fetch_standings(league_id)
    if not standings: 
        print(f"    ! No standings found for league {league_id}")
        return
    
    for team_obj in standings:
        team_name = team_obj['team']['name']
        points = team_obj['points']
        rank = team_obj['rank']
        team_id = db.add_team_if_not_exists(team_name)
        
        # Season Stats
        played = team_obj['all']['played']
        goals_for = team_obj['all']['goals']['for']
        goals_against = team_obj['all']['goals']['against']
        
        avg_scored = goals_for / played if played > 0 else 1.2
        avg_conceded = goals_against / played if played > 0 else 1.2
        
        # Elo Logic
        baseline = 1500.0
        rank_bonus = (20 - rank) * 5 
        point_bonus = points * 2
        new_elo = baseline + rank_bonus + point_bonus
        
        # Update Database (Elo and attack/defense ratings)
        db.update_team_elo(team_id, new_elo)
        db.update_team_stats(team_id, avg_scored, avg_conceded)
        
        print(f"    - {team_name}: Elo {int(new_elo)} | Avg Goals: {avg_scored:.1f}")

if __name__ == "__main__":
    import sys
    import time
    force_sync = "--force" in sys.argv
    use_legacy = "--legacy" in sys.argv
    setup_mode = "--setup" in sys.argv
    
    if setup_mode:
        # Run setup mode
        print("=== SETUP MODE ===")
        config = ConfigManager()
        config.print_status()
        
        print("\nTo set API keys, use:")
        print("  config.set_api_key('football_data_org', 'your_key_here')")
        print("  config.set_api_key('api_football', 'your_key_here')")
        print("  config.store_to_db()")
        sys.exit(0)
    
    if use_legacy:
        # Use legacy sync engine
        print("=== LEGACY SYNC MODE ===")
        
        # ===== COOLDOWN CONFIGURATION =====
        SYNC_COOLDOWN_SECONDS = 12 * 60 * 60  # 12 годин = 43200 секунд
        # ==================================
        
        db = LogicBetDB()
        api = APIFootballClient(api_key="72afa426ab5fb0a7c964261b8b25f977") 
        engine = BettingAnalytics(db)
        
        # --- Cooldown Check ---
        last_sync = float(db.get_config("last_sync_time") or 0)
        current_time = time.time()
        elapsed = current_time - last_sync
        cooldown_remaining = SYNC_COOLDOWN_SECONDS - elapsed
        
        print(f"=== LOGICBET LEGACY SYNC ENGINE ===")
        print(f"  Час (Local):     {time.ctime(current_time)}")
        print(f"  Дата поточна:    {datetime.now().strftime('%Y-%m-%d')}")
        
        if last_sync > 0:
            print(f"  Останній синк:   {time.ctime(last_sync)}")
            hours_ago = elapsed / 3600
            print(f"  Пройшло:         {hours_ago:.1f} год")
        else:
            print(f"  Останній синк:   НІКОЛИ (перший запуск)")
        
        target_leagues = [39, 140, 78, 61, 135, 2, 3, 848, 88, 94]
        
        # Determine if API sync is allowed
        api_sync_allowed = force_sync or (cooldown_remaining <= 0)
        
        if force_sync:
            print(f"\n  ⚡ ПРИМУСОВИЙ СИНК (--force)")
        elif cooldown_remaining > 0:
            hours_left = cooldown_remaining / 3600
            mins_left = (cooldown_remaining % 3600) / 60
            print(f"\n  ⏳ КУЛДАУН АКТИВНИЙ: до наступного синку {int(hours_left)} год {int(mins_left)} хв")
            print(f"     API запити НЕ виконуються. Працюємо лише з локальними даними.")
        else:
            print(f"\n  ✅ КУЛДАУН ЗАВЕРШЕНО — дозволено оновити дані з API")
        
        print(f"{'='*40}")
        
        
        # --- SHOW MATCH STATISTICS ---
        show_recent_matches_statistics(db)
        
        try:
            # --- API SYNC (only if cooldown passed or --force) ---
            if api_sync_allowed:
                print("\n--- ЗАПУСК СИНХРОНІЗАЦІЇ З API ---")
                sync_live_data(db, api, engine, target_leagues)
                
                # Save sync timestamp ONLY after successful API sync
                db.set_config("last_sync_time", current_time)
                
                # Save real API limits to DB for UI
                if api.requests_remaining is not None:
                    db.set_config("api_requests_left", api.requests_remaining)
                else:
                    db.set_config("api_requests_left", api.get_limit_left())
                
                print("  [OK] Дані з API оновлено. Наступний синк через 12 годин.")
            else:
                print("\n--- ПРОПУСК API (кулдаун) ---")
            
            # --- LOCAL OPERATIONS (always run) ---
            recalculate_elo_from_history(db, engine)
            evaluate_virtual_bets(db)
            evaluate_user_bets(db)
            sync_match_stats(db, api)
            
            # --- SHOW MATCH STATISTICS ---
            show_recent_matches_statistics(db)
            
            # --- SHOW MATCH STATISTICS ---
            show_recent_matches_statistics(db)
            
            # --- EXPORT STATISTICS FOR GODOT ---
            try:
                from godot_data_exporter import export_match_statistics_to_godot
                export_match_statistics_to_godot()
            except Exception as e:
                print(f"Could not export statistics for Godot: {e}")
            
            db.set_config("sync_error", "")
            
            print("\n=== СИНХРОНІЗАЦІЯ ЗАВЕРШЕНА ===")
            if not api_sync_allowed:
                hours_left = cooldown_remaining / 3600
                print(f"    Наступне оновлення з API можливе через {int(hours_left)} год {int((cooldown_remaining % 3600) / 60)} хв")
                print(f"    Або запустіть з прапором: python main.py --force")
            
        except Exception as e:
            import traceback
            error_msg = f"Помилка: {str(e)}"
            db.set_config("sync_error", error_msg)
            print(f"\n!!! SYNC FAILED: {traceback.format_exc()} !!!")
    
    else:
        # Use new multi-source sync engine
        print("=== MULTI-SOURCE SYNC ENGINE ===")
        
        # Initialize multi-source engine
        multi_engine = MultiSourceSyncEngine()
        db = LogicBetDB()
        analytics = BettingAnalytics(db)
        
        # Print status
        multi_engine.print_status()
        
        
        try:
            # Run multi-source sync (may be skipped by cooldown)
            success = multi_engine.run_full_sync(force_sync=force_sync)
            
            if force_sync:
                print("[DATABASE] Resetting predictions for re-evaluation...")
                db.get_connection().execute("UPDATE predictions SET is_hit = NULL")
            
            if success:
                print("\n[SYNC] ✅ API sync completed successfully")
            else:
                print("\n[SYNC] ⏳ API sync skipped (cooldown or limit)")
            
            # --- LOCAL OPERATIONS (ALWAYS run, even if API sync was skipped) ---
            recalculate_elo_from_history(db, analytics)
            evaluate_virtual_bets(db)
            evaluate_user_bets(db)
            sync_match_stats(db, multi_engine.api_football)
            
            # --- SHOW MATCH STATISTICS ---
            show_recent_matches_statistics(db)
            
            # --- EXPORT DATA FOR MOBILE ---
            export_to_json(db)
            
            print("\n=== MULTI-SOURCE SYNC COMPLETED SUCCESSFULLY ===")
                
        except Exception as e:
            import traceback
            error_msg = f"Multi-source sync error: {str(e)}"
            db.set_config("sync_error", error_msg)
            print(f"\n!!! MULTI-SOURCE SYNC FAILED: {traceback.format_exc()} !!!")
            
            # Fallback to legacy mode if multi-source fails
            print("\n!!! FALLING BACK TO LEGACY MODE !!!")
            # Note: We don't use exec() anymore to avoid infinite loops
            print("Please check the error log above.")


# Function moved to top
