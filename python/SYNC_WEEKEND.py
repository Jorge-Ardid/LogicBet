from database import LogicBetDB
from multi_source_sync import MultiSourceSyncEngine
from analytics import BettingAnalytics
from datetime import datetime, timedelta

def sync_weekend():
    print("=== WEEKEND PREDICTION SYNC ===")
    db = LogicBetDB()
    engine = MultiSourceSyncEngine()
    
    # Force sync for the next 3 days to get all weekend matches
    # We'll modify the engine's date range temporarily or just run it
    success = engine.run_full_sync(force_sync=True)
    
    if success:
        print("\n[SUCCESS] Weekend matches loaded. Exporting...")
        import main
        main.export_to_json(db)
        print("=== DONE! REFRESH GODOT ===")
    else:
        print("\n[FAILED] Could not sync weekend matches.")

if __name__ == "__main__":
    sync_weekend()
