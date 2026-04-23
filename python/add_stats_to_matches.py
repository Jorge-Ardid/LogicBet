#!/usr/bin/env python3
"""
Add statistics to existing matches
"""

import sqlite3
import os
import random

def add_statistics_to_matches():
    """Add statistics to existing matches"""
    db_path = "../godot_app/logicbet.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get matches without statistics
        cursor.execute("""
            SELECT id, home_team_id, away_team_id, home_score, away_score
            FROM matches 
            WHERE id NOT IN (SELECT DISTINCT match_id FROM match_statistics)
            LIMIT 10
        """)
        
        matches = cursor.fetchall()
        print(f"Found {len(matches)} matches without statistics")
        
        for match in matches:
            match_id = match[0]
            home_team_id = match[1]
            away_team_id = match[2]
            home_score = match[3] or 0
            away_score = match[4] or 0
            
            # Generate realistic statistics based on score
            if home_score > away_score:
                # Home team won - more shots, corners for home
                shots_home = random.randint(12, 20)
                shots_away = random.randint(6, 14)
                corners_home = random.randint(6, 12)
                corners_away = random.randint(2, 8)
                possession_home = random.randint(55, 70)
                possession_away = 100 - possession_home
            elif away_score > home_score:
                # Away team won - more shots, corners for away
                shots_home = random.randint(6, 14)
                shots_away = random.randint(12, 20)
                corners_home = random.randint(2, 8)
                corners_away = random.randint(6, 12)
                possession_home = random.randint(30, 45)
                possession_away = 100 - possession_home
            else:
                # Draw - balanced statistics
                shots_home = random.randint(8, 15)
                shots_away = random.randint(8, 15)
                corners_home = random.randint(4, 8)
                corners_away = random.randint(4, 8)
                possession_home = random.randint(45, 55)
                possession_away = 100 - possession_home
            
            # Cards based on match intensity
            cards_yellow_home = random.randint(1, 4)
            cards_yellow_away = random.randint(1, 4)
            cards_red_home = random.randint(0, 1)
            cards_red_away = random.randint(0, 1)
            
            # xG based on goals
            xg_home = round(random.uniform(0.8, 2.5), 1)
            xg_away = round(random.uniform(0.8, 2.5), 1)
            
            # Insert statistics
            cursor.execute("""
                INSERT OR REPLACE INTO match_statistics 
                (match_id, shots_home, shots_away, corners_home, corners_away,
                 cards_yellow_home, cards_red_home, cards_yellow_away, cards_red_away,
                 possession_home, possession_away, xg_home, xg_away)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, shots_home, shots_away, corners_home, corners_away,
                cards_yellow_home, cards_red_home, cards_yellow_away, cards_red_away,
                possession_home, possession_away, xg_home, xg_away
            ))
            
            print(f"  Added stats for match {match_id}: {shots_home}-{shots_away} shots, {corners_home}-{corners_away} corners")
        
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM match_statistics")
        stats_count = cursor.fetchone()[0]
        print(f"Total statistics records: {stats_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        conn.close()
        return False

if __name__ == "__main__":
    print("ADDING STATISTICS TO MATCHES")
    print("=" * 40)
    
    if add_statistics_to_matches():
        print("\nSUCCESS: Statistics added to matches!")
        print("Now run your main.py to see statistics")
    else:
        print("\nFAILED: Could not add statistics")
