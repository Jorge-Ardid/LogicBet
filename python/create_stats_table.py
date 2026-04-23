#!/usr/bin/env python3
"""
Create match_statistics table in the database
"""

import sqlite3
import os

def create_match_statistics_table():
    """Create match_statistics table if it doesn't exist"""
    db_path = "../godot_app/logicbet.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create match_statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER UNIQUE,
                shots_home INTEGER DEFAULT 0,
                shots_away INTEGER DEFAULT 0,
                shots_on_target_home INTEGER DEFAULT 0,
                shots_on_target_away INTEGER DEFAULT 0,
                corners_home INTEGER DEFAULT 0,
                corners_away INTEGER DEFAULT 0,
                cards_yellow_home INTEGER DEFAULT 0,
                cards_red_home INTEGER DEFAULT 0,
                cards_yellow_away INTEGER DEFAULT 0,
                cards_red_away INTEGER DEFAULT 0,
                possession_home INTEGER DEFAULT 50,
                possession_away INTEGER DEFAULT 50,
                fouls_home INTEGER DEFAULT 0,
                fouls_away INTEGER DEFAULT 0,
                offsides_home INTEGER DEFAULT 0,
                offsides_away INTEGER DEFAULT 0,
                xg_home REAL DEFAULT 0.0,
                xg_away REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches (id)
            )
        """)
        
        print("Created match_statistics table")
        
        # Add sample statistics for existing matches
        cursor.execute("SELECT id, home_team, away_team FROM matches LIMIT 5")
        matches = cursor.fetchall()
        
        for match in matches:
            match_id = match[0]
            home_team = match[1]
            away_team = match[2]
            
            # Generate realistic statistics
            import random
            
            shots_home = random.randint(8, 20)
            shots_away = random.randint(6, 18)
            shots_on_target_home = random.randint(3, 8)
            shots_on_target_away = random.randint(2, 7)
            corners_home = random.randint(3, 12)
            corners_away = random.randint(2, 10)
            cards_yellow_home = random.randint(0, 4)
            cards_red_home = random.randint(0, 1)
            cards_yellow_away = random.randint(0, 4)
            cards_red_away = random.randint(0, 1)
            possession_home = random.randint(40, 70)
            possession_away = 100 - possession_home
            fouls_home = random.randint(5, 15)
            fouls_away = random.randint(5, 15)
            offsides_home = random.randint(1, 5)
            offsides_away = random.randint(1, 5)
            xg_home = round(random.uniform(0.5, 3.5), 1)
            xg_away = round(random.uniform(0.5, 3.5), 1)
            
            cursor.execute("""
                INSERT OR IGNORE INTO match_statistics 
                (match_id, shots_home, shots_away, shots_on_target_home, shots_on_target_away,
                 corners_home, corners_away, cards_yellow_home, cards_red_home,
                 cards_yellow_away, cards_red_away, possession_home, possession_away,
                 fouls_home, fouls_away, offsides_home, offsides_away, xg_home, xg_away)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, shots_home, shots_away, shots_on_target_home, shots_on_target_away,
                corners_home, corners_away, cards_yellow_home, cards_red_home,
                cards_yellow_away, cards_red_away, possession_home, possession_away,
                fouls_home, fouls_away, offsides_home, offsides_away, xg_home, xg_away
            ))
        
        conn.commit()
        print(f"Added statistics for {len(matches)} matches")
        
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
    print("CREATING MATCH STATISTICS TABLE")
    print("=" * 40)
    
    if create_match_statistics_table():
        print("\nSUCCESS: Match statistics table created!")
        print("Now your main.py will show statistics")
    else:
        print("\nFAILED: Could not create statistics table")
