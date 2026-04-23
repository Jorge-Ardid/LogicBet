#!/usr/bin/env python3
"""
Check and fix match_statistics table structure
"""

import sqlite3
import os

def check_and_fix_stats():
    """Check match_statistics table structure and fix if needed"""
    db_path = "../godot_app/logicbet.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check match_statistics table structure
        cursor.execute("PRAGMA table_info(match_statistics)")
        columns = cursor.fetchall()
        print("match_statistics table columns:")
        for col in columns:
            print(f"  {col[1]}: {col[2]}")
        
        # Check if we have the right columns
        column_names = [col[1] for col in columns]
        print(f"\nColumn names: {column_names}")
        
        # Test query with correct column names
        cursor.execute("""
            SELECT m.id, 
                   (SELECT name FROM teams WHERE id = m.home_team_id) as home_team,
                   (SELECT name FROM teams WHERE id = m.away_team_id) as away_team, 
                   m.home_score, m.away_score, m.date, m.status, m.league,
                   s.shots_home, s.shots_away, s.corners_home, s.corners_away,
                   s.cards_home_yellow, s.cards_away_yellow, s.possession_home, s.possession_away,
                   s.xg_home, s.xg_away
            FROM matches m
            LEFT JOIN match_statistics s ON m.id = s.match_id
            ORDER BY m.date DESC
            LIMIT 3
        """)
        
        matches = cursor.fetchall()
        print(f"\nFound {len(matches)} matches with statistics")
        
        for i, match in enumerate(matches):
            print(f"\n{i+1}. {match[1]} vs {match[2]}")
            print(f"   Score: {match[3]}-{match[4]}")
            print(f"   Date: {match[5]}")
            print(f"   Status: {match[6]}")
            
            if match[8]:  # If statistics exist
                print(f"   Shots: {match[8]} - {match[9]}")
                print(f"   Corners: {match[10]} - {match[11]}")
                print(f"   Cards: {match[12]} - {match[13]}")
                print(f"   Possession: {match[14]}% - {match[15]}%")
                print(f"   xG: {match[16]} - {match[17]}")
            else:
                print("   Statistics: Not available")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        conn.close()
        return False

if __name__ == "__main__":
    print("CHECKING AND FIXING MATCH STATISTICS")
    print("=" * 50)
    
    if check_and_fix_stats():
        print("\nSUCCESS: Match statistics working!")
        print("Now your main.py will show statistics correctly")
    else:
        print("\nFAILED: Could not fix match statistics")
