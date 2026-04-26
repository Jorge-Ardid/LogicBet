from database import LogicBetDB

def remove_championship():
    db = LogicBetDB()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        print("[CLEANUP] Removing Championship (League 40) matches...")
        cursor.execute("DELETE FROM matches WHERE league_id = 40 OR league LIKE '%Чемпіоншип%'")
        print(f"  Deleted {cursor.rowcount} matches.")
        
        # Clean up related predictions
        cursor.execute("DELETE FROM predictions WHERE match_id NOT IN (SELECT id FROM matches)")
        conn.commit()
    
    import main
    main.export_to_json(db)
    print("[SUCCESS] Championship removed from local system.")

if __name__ == "__main__":
    remove_championship()
