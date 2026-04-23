import sqlite3

db_path='c:/Users/jvjor/OneDrive/Рабочий стол/Yuri/Footboll/godot_app/logicbet.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
for row in c.fetchall():
    print(f"Table: {row[0]}")
    print(f"Schema: {row[1]}")
    print("-" * 50)
