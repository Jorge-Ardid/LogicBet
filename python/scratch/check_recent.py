import sqlite3
import os

DB_PATH = r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def check_history():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- RECENT MATCHES IN DB ---")
    cursor.execute("""
        SELECT m.date, t1.name, t2.name, m.home_score, m.away_score, m.status, m.league
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        ORDER BY m.date DESC LIMIT 30
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"{row[0]} | {row[1]} {row[3]}:{row[4]} {row[2]} | Status: {row[5]} | League: {row[6]}")
    
    print("\n--- CONFIG VALUES ---")
    cursor.execute("SELECT key, value FROM config")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}")

    conn.close()

if __name__ == "__main__":
    check_history()
