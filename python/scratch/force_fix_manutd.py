import sqlite3
import os

db_path = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Виправляємо обидва виявлені ID матчу
cursor.execute("""
    UPDATE matches 
    SET home_score = 1, away_score = 2, status = 'FINISHED', 
        red_cards_h = 1, corners_h = 5, corners_a = 6, 
        shots_on_h = 4, shots_on_a = 5, possession_h = 48, possession_a = 52
    WHERE id IN (52, 77)
""")

if cursor.rowcount > 0:
    print(f"✅ УСПІХ: Обидва записи (ID 52 та 77) оновлено: 1-2 та червона картка.")
else:
    print("❌ Не вдалося знайти записи з такими ID.")

conn.commit()
conn.close()
