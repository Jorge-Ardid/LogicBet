import sqlite3
import os

# Let's try to find the DB in the same directory as the script first, then elsewhere
possible_paths = [
    r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "godot_app", "logicbet.db")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "logicbet.db"))
]

def debug_db():
    print("--- LOGICBET DEEP DEBUG ---")
    found_path = None
    for p in possible_paths:
        if os.path.exists(p):
            print(f"[FOUND] Database exists at: {p}")
            found_path = p
            break
        else:
            print(f"[MISSING] No file at: {p}")

    if not found_path:
        print("!!! ERROR: Could not find logicbet.db anywhere !!!")
        return

    try:
        conn = sqlite3.connect(found_path)
        cursor = conn.cursor()
        
        # Check teams
        cursor.execute("SELECT name, elo_rating, current_form FROM teams WHERE name LIKE '%Arsenal%'")
        result = cursor.fetchone()
        if result:
            print(f"\n[DATA] Team: {result[0]}")
            print(f"[DATA] Elo: {result[1]}")
            print(f"[DATA] Form: {result[2]}")
        else:
            print("\n[DATA] Could not find any team named Arsenal.")
            
        cursor.execute("SELECT COUNT(*) FROM matches WHERE elo_processed = 1")
        processed = cursor.fetchone()[0]
        print(f"[DATA] Processed matches: {processed}")
        
        conn.close()
    except Exception as e:
        print(f"!!! SQL ERROR: {e}")

if __name__ == "__main__":
    debug_db()
