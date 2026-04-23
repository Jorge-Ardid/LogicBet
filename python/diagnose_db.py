import sqlite3
import os

DB_PATH = r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def diagnose():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- TOP 20 TEAMS BY ELO ---")
    cursor.execute("SELECT id, name, elo_rating, current_form FROM teams ORDER BY elo_rating DESC LIMIT 20")
    for row in cursor.fetchall():
        print(f"ID: {row[0]} | Team: {row[1]:<20} | Elo: {row[2]:.1f} | Form: {row[3]}")
    
    print("\n--- LAST 10 PROCESSED MATCHES ---")
    cursor.execute("""
        SELECT m.id, t1.name, t2.name, m.home_score, m.away_score, m.elo_processed 
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.status = 'FT'
        ORDER BY m.date DESC LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"Match: {row[1]} {row[3]}:{row[4]} {row[2]} | Processed: {row[5]}")

    conn.close()

if __name__ == "__main__":
    diagnose()
