import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- MIGRATING DATABASE: ADDING HT SCORES ---")
    
    try:
        cursor.execute("ALTER TABLE matches ADD COLUMN ht_score_h INTEGER DEFAULT NULL")
        cursor.execute("ALTER TABLE matches ADD COLUMN ht_score_a INTEGER DEFAULT NULL")
        conn.commit()
        print("Columns added successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Columns already exist.")
        else:
            print(f"Error: {e}")
            
    conn.close()

if __name__ == "__main__":
    migrate()
