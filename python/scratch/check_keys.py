import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def check_keys():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- API KEY DIAGNOSTICS ---")
    cursor.execute("SELECT key, value FROM config WHERE key LIKE 'api_key_%'")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1][:8]}...")
        
    # Force set api_football key if it looks missing or placeholder
    cursor.execute("SELECT value FROM config WHERE key = 'api_key_api_football'")
    val = cursor.fetchone()
    if not val or val[0] == "PLACEHOLDER_KEY":
        print("Fixing api_football key...")
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('api_key_api_football', '72afa426ab5fb0a7c964261b8b25f977')")
        conn.commit()
        print("Fixed.")
        
    conn.close()

if __name__ == "__main__":
    check_keys()
