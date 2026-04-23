import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def cleanup_duplicates():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- STARTING ADVANCED DUPLICATE CLEANUP ---")
    
    # 1. Identify duplicates based on Date, Home Team and Away Team
    # We use DATE(date) to ignore time differences
    cursor.execute("""
        SELECT DATE(date) as d, home_team_id, away_team_id, COUNT(*) as c
        FROM matches
        GROUP BY d, home_team_id, away_team_id
        HAVING c > 1
    """)
    
    duplicates = cursor.fetchall()
    print(f"Found {len(duplicates)} groups of duplicate matches.")
    
    deleted_count = 0
    
    for d, home_id, away_id, count in duplicates:
        # Get all matches in this group
        cursor.execute("""
            SELECT id, status, remote_id 
            FROM matches 
            WHERE DATE(date) = ? AND home_team_id = ? AND away_team_id = ?
            ORDER BY 
                CASE WHEN status IN ('FT', 'FINISHED', 'AET', 'PEN') THEN 0 ELSE 1 END,
                id ASC
        """, (d, home_id, away_id))
        
        matches = cursor.fetchall()
        # Keep the first one (preferred based on ORDER BY)
        keep_id = matches[0][0]
        delete_ids = [m[0] for m in matches[1:]]
        
        for mid in delete_ids:
            # Delete predictions associated with this match
            cursor.execute("DELETE FROM predictions WHERE match_id = ?", (mid,))
            # Delete the match itself
            cursor.execute("DELETE FROM matches WHERE id = ?", (mid,))
            deleted_count += 1
            
    conn.commit()
    print(f"Successfully deleted {deleted_count} duplicate records and their predictions.")
    
    # 2. Cleanup orphaned predictions (just in case)
    cursor.execute("DELETE FROM predictions WHERE match_id NOT IN (SELECT id FROM matches)")
    conn.commit()
    
    conn.close()

if __name__ == "__main__":
    cleanup_duplicates()
