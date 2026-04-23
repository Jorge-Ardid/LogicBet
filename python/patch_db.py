import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def patch_db():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- PATCHING DATABASE SCHEMA ---")
    
    # Check existing columns in 'teams'
    cursor.execute("PRAGMA table_info(teams)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "avg_scored" not in columns:
        print("Adding avg_scored...")
        cursor.execute("ALTER TABLE teams ADD COLUMN avg_scored REAL DEFAULT 0.0")
        
    if "avg_conceded" not in columns:
        print("Adding avg_conceded...")
        cursor.execute("ALTER TABLE teams ADD COLUMN avg_conceded REAL DEFAULT 0.0")
        
    conn.commit()
    conn.close()
    print("--- SCHEMA UPDATED ---")

if __name__ == "__main__":
    patch_db()
