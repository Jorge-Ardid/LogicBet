#!/usr/bin/env python3
"""
Fix the statistics query to match actual database schema
"""

import sqlite3
import os

def fix_statistics_query():
    """Fix the statistics query to use correct column names"""
    db_path = "../godot_app/logicbet.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check matches table structure
        cursor.execute("PRAGMA table_info(matches)")
        columns = cursor.fetchall()
        print("matches table columns:")
        for col in columns:
            print(f"  {col[1]}: {col[2]}")
        
        # Test the corrected query
        cursor.execute("""
            SELECT m.id, m.home_team, m.away_team, m.home_score, m.away_score, 
                   m.date, m.status, m.competition,
                   s.shots_home, s.shots_away, s.corners_home, s.corners_away,
                   s.cards_yellow_home, s.cards_yellow_away, s.possession_home, s.possession_away,
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
    print("FIXING STATISTICS QUERY")
    print("=" * 40)
    
    if fix_statistics_query():
        print("\nSUCCESS: Statistics query fixed!")
        print("Now update show_recent_matches_statistics in main.py")
    else:
        print("\nFAILED: Could not fix statistics query")
