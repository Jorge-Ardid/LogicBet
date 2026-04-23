import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def check_teams():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Search for anything containing "Koln" or "oln" or "nited"
    cursor.execute("SELECT id, name FROM teams WHERE name LIKE '%oln%' OR name LIKE '%rem%' OR name LIKE '%nited%'")
    teams = cursor.fetchall()
    
    print(f"--- MATCHING TEAMS: {len(teams)} ---")
    for t_id, t_name in teams:
        print(f"ID: {t_id} | Name: '{t_name}'")
            
    conn.close()

if __name__ == "__main__":
    check_teams()
