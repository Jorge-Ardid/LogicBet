import sqlite3
import os

db_path = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"
if not os.path.exists(db_path):
    print(f"Error: DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- RECENT MATCHES IN DB ---")
cursor.execute("SELECT id, date, home_team_id, away_team_id, status FROM matches ORDER BY date DESC LIMIT 10")
for row in cursor.fetchall():
    print(dict(row))

print("\n--- SQLITE TIME CHECK ---")
cursor.execute("SELECT datetime('now', '-4 hours') as filter_time, datetime('now') as now_time")
print(dict(cursor.fetchone()))

conn.close()
