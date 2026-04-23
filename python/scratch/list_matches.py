import sqlite3
import os

db_path = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- ВСІ МАТЧІ ЗА 13 КВІТНЯ В БАЗІ ---")
cursor.execute("""
    SELECT m.id, m.date, t1.name as home, t2.name as away, m.status 
    FROM matches m
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    WHERE m.date LIKE '2026-04-13%'
""")

rows = cursor.fetchall()
if not rows:
    print("В базі взагалі немає ігор за 13 квітня.")
else:
    for row in rows:
        print(f"ID: {row['id']} | {row['home']} vs {row['away']} | Статус: {row['status']}")

conn.close()
