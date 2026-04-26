from database import LogicBetDB
from multi_source_sync import MultiSourceSyncEngine
import main

def nuclear_reset():
    db = LogicBetDB()
    with db.get_connection() as conn:
        print("[RESET] Clearing current matches and predictions to fix name mismatch...")
        # We delete only future and very recent matches to preserve long history
        conn.execute("DELETE FROM predictions WHERE match_id IN (SELECT id FROM matches WHERE DATE(date) >= DATE('now', '-1 day'))")
        conn.execute("DELETE FROM matches WHERE DATE(date) >= DATE('now', '-1 day')")
        
        # Also let's fix the teams table if there's a mess
        # If 'Itesalat' is posing as a top team, we need to find it
        conn.execute("DELETE FROM teams WHERE name LIKE '%Itesalat%' OR name LIKE '%Maleyet%'")
        conn.commit()
        print("[RESET] Tables cleared. Starting FRESH sync...")

    # Run fresh sync
    engine = MultiSourceSyncEngine()
    success = engine.run_full_sync(force_sync=True)
    
    if success:
        print("[SUCCESS] Data reloaded correctly.")
        main.export_to_json(db)
    else:
        print("[ERROR] Sync failed.")

if __name__ == "__main__":
    nuclear_reset()
