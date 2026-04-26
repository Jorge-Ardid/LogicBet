import os
import sqlite3
import shutil

def total_wipe():
    print("=== TOTAL SYSTEM RESET (REPAIRED PATHS) ===")
    
    # Use absolute paths to be 100% sure
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db_path = os.path.join(base_dir, "godot_app", "logicbet.db")
    json_path = os.path.join(base_dir, "python", "logicbet_export.json")
    data_dir = os.path.join(base_dir, "data")
    
    print(f"Target DB: {db_path}")
    
    # 1. Delete the DB file
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print("  [OK] Deleted local database.")
        except Exception as e:
            print(f"  [!] ERROR: Could not delete DB: {e}. CLOSE GODOT APP!")
            return
    else:
        print("  [?] DB file not found at this path. Checking root...")
        root_db = os.path.join(base_dir, "logicbet.db")
        if os.path.exists(root_db):
            os.remove(root_db)
            print("  [OK] Deleted DB from root.")

    # 2. Clean DATA folder (but keep config)
    if os.path.exists(data_dir):
        print("  [CLEANUP] Cleaning data folder from old samples...")
        for f in os.listdir(data_dir):
            if f.endswith(".json") and "config" not in f:
                os.remove(os.path.join(data_dir, f))
                print(f"    - Removed {f}")

    # 3. Delete the JSON export
    if os.path.exists(json_path):
        os.remove(json_path)
        print("  [OK] Deleted local JSON.")

    # 4. Run a fresh sync
    print("\n[STEP 2] Creating a fresh, clean database from scratch...")
    from multi_source_sync import MultiSourceSyncEngine
    import main
    
    engine = MultiSourceSyncEngine()
    success = engine.run_full_sync(force_sync=True)
    
    if success:
        db = engine.db
        print("[STEP 3] Exporting clean data...")
        main.export_to_json(db)
        print("\n=== SYSTEM IS NOW 100% CLEAN ===")
    else:
        print("\n[!] Sync failed. Check internet.")

if __name__ == "__main__":
    total_wipe()
