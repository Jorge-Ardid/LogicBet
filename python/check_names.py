import sqlite3
import os

DB_PATH = r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def check_names():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- REAL NAMES IN YOUR DATABASE (FROM API) ---")
    cursor.execute("SELECT id, name, elo_rating FROM teams ORDER BY name ASC")
    for row in cursor.fetchall():
        print(f"ID: {row[0]} | '{row[1]}' | Elo: {row[2]}")
    
    print("\n--- TEAMS IN RECENT MATCHES ---")
    cursor.execute("""
        SELECT DISTINCT t.name 
        FROM matches m 
        JOIN teams t ON m.home_team_id = t.id OR m.away_team_id = t.id
        LIMIT 20
    """)
    for row in cursor.fetchall():
        print(f"Match Participant: '{row[0]}'")

    conn.close()

if __name__ == "__main__":
    check_names()
