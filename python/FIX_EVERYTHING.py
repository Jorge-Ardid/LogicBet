from database import LogicBetDB
from multi_source_sync import MultiSourceSyncEngine
from analytics import BettingAnalytics
import os

def fix():
    print("=== FINAL REPAIR & SYNC ===")
    db = LogicBetDB()
    analytics = BettingAnalytics(db)
    engine = MultiSourceSyncEngine()
    
    # 1. Clean up potential bad data
    with db.get_connection() as conn:
        print("[1] Cleaning up matches with missing or wrong data...")
        # Delete matches that are clearly mapped wrong (like the one in the screenshot)
        conn.execute("DELETE FROM matches WHERE league = 'Прімейра-ліга (Португалія)' AND (SELECT name FROM teams WHERE id = home_team_id) NOT LIKE '%Porto%' AND (SELECT name FROM teams WHERE id = home_team_id) NOT LIKE '%Sporting%' AND (SELECT name FROM teams WHERE id = home_team_id) NOT LIKE '%Benfica%'")
        # Also clean empty predictions
        conn.execute("DELETE FROM predictions WHERE match_id NOT IN (SELECT id FROM matches)")
        conn.commit()

    # 2. Force a full sync of ALL target leagues
    print("[2] Running FORCE SYNC for all TOP leagues...")
    # Target IDs: 39 (EPL), 140 (La Liga), 78 (Bundesliga), 135 (Serie A), 61 (Ligue 1), 94 (Portugal), 88 (Eredivisie)
    success = engine.run_full_sync(force_sync=True)
    
    if success:
        print("[3] Sync successful! Recalculating ELO and exporting...")
        # Need to import these functions from main or just run them here
        import main
        main.recalculate_elo_from_history(db, analytics)
        main.evaluate_virtual_bets(db)
        main.export_to_json(db)
        print("\n=== SUCCESS! PLEASE REFRESH GODOT APP ===")
    else:
        print("\n!!! SYNC FAILED. Check API limits or internet. !!!")

if __name__ == "__main__":
    fix()
