import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def merge_matches():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Find matches with same date, home_id, away_id
    cursor.execute("""
        SELECT DATE(date) as d, home_team_id, away_team_id, COUNT(*) as c
        FROM matches
        GROUP BY d, home_team_id, away_team_id
        HAVING c > 1
    """)
    dupes = cursor.fetchall()
    
    print(f"Found {len(dupes)} groups of duplicate matches.")
    
    merged_count = 0
    for d, h_id, a_id, count in dupes:
        cursor.execute("""
            SELECT id, remote_id FROM matches 
            WHERE DATE(date) = ? AND home_team_id = ? AND away_team_id = ?
            ORDER BY id ASC
        """, (d, h_id, a_id))
        ids = cursor.fetchall()
        
        keep_id = ids[0][0]
        to_remove = ids[1:]
        
        print(f"Merging matches into ID {keep_id} (Date: {d})")
        
        for rem_id, rem_remote in to_remove:
            # 2. Move predictions to the kept match
            cursor.execute("UPDATE predictions SET match_id = ? WHERE match_id = ?", (keep_id, rem_id))
            # 3. Delete the duplicate match
            cursor.execute("DELETE FROM matches WHERE id = ?", (rem_id,))
            merged_count += 1
            
    conn.commit()
    print(f"Finished. Merged {merged_count} matches.")
    conn.close()

if __name__ == "__main__":
    merge_matches()
