import sqlite3
import os
import sys

# Add parent dir to path to import database and merge logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from merge_teams import merge_teams

db_path = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find IDs
cursor.execute("SELECT id, name FROM teams WHERE name = 'Leeds'")
h1 = cursor.fetchone()
cursor.execute("SELECT id, name FROM teams WHERE name = 'Leeds United'")
h2 = cursor.fetchone()

conn.close()

if h1 and h2:
    print(f"Found Leeds (ID:{h1[0]}) and Leeds United (ID:{h2[0]})")
    # Merge Leeds United (1194?) into Leeds (1166?)
    merge_teams(h2[0], h1[0])
else:
    print("Could not find both Leeds variants to merge.")
