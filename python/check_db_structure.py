#!/usr/bin/env python3
"""
Check database structure and create match_statistics table
"""

import sqlite3
import os

def check_and_create_table():
    """Check database and create match_statistics table"""
    db_path = "../godot_app/logicbet.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Existing tables: {tables}")
        
        # Check if match_statistics exists
        if 'match_statistics' in tables:
            print("match_statistics table already exists")
            
            # Show structure
            cursor.execute("PRAGMA table_info(match_statistics)")
            columns = cursor.fetchall()
            print("match_statistics table structure:")
            for col in columns:
                print(f"  {col[1]}: {col[2]}")
        else:
            print("Creating match_statistics table...")
            
            # Create the table
            cursor.execute("""
                CREATE TABLE match_statistics (
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
            
            print("match_statistics table created successfully")
            
            # Add sample data
            cursor.execute("SELECT id FROM matches LIMIT 3")
            matches = cursor.fetchall()
            
            for match in matches:
                match_id = match[0]
                
                # Sample statistics
                cursor.execute("""
                    INSERT OR REPLACE INTO match_statistics 
                    (match_id, shots_home, shots_away, corners_home, corners_away,
                     cards_yellow_home, cards_yellow_away, possession_home, possession_away,
                     xg_home, xg_away)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, 15, 12, 8, 6, 2, 3, 58, 42, 2.3, 1.8
                ))
            
            conn.commit()
            print(f"Added sample statistics for {len(matches)} matches")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        conn.close()
        return False

if __name__ == "__main__":
    print("CHECKING DATABASE STRUCTURE")
    print("=" * 40)
    
    if check_and_create_table():
        print("\nSUCCESS: Database structure is ready!")
        print("Your main.py will now show statistics")
    else:
        print("\nFAILED: Could not setup database structure")
