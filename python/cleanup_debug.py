import sqlite3
import os

DB_PATH = r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def cleanup_debug():
    if not os.path.exists(DB_PATH):
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- CLEANING UP DEBUG DATA ---")
    
    # Delete matches with DEBUG in team names (joined)
    cursor.execute("""
        DELETE FROM matches 
        WHERE home_team_id IN (SELECT id FROM teams WHERE name LIKE '%DEBUG%')
        OR away_team_id IN (SELECT id FROM teams WHERE name LIKE '%DEBUG%')
    """)
    
    # Delete teams with DEBUG in name
    cursor.execute("DELETE FROM teams WHERE name LIKE '%DEBUG%'")
    
    # Delete any related predictions
    cursor.execute("DELETE FROM predictions WHERE match_id NOT IN (SELECT id FROM matches)")
    
    conn.commit()
    conn.close()
    print("--- CLEANUP COMPLETE ---")

if __name__ == "__main__":
    cleanup_debug()
