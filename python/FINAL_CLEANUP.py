from database import LogicBetDB
import sqlite3

def final_cleanup():
    db = LogicBetDB()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        print("[CLEANUP] Removing Egyptian matches from Portugal league...")
        # Targeting specific team names from the screenshot
        cursor.execute("""
            DELETE FROM matches 
            WHERE home_team_id IN (SELECT id FROM teams WHERE name LIKE '%Itesalat%' OR name LIKE '%Maleyet%')
               OR away_team_id IN (SELECT id FROM teams WHERE name LIKE '%Itesalat%' OR name LIKE '%Maleyet%')
        """)
        print(f"  Deleted {cursor.rowcount} ghost matches.")
        
        # Also let's make sure Real Madrid and Napoli have the right status to be seen
        # Sometimes APIs send 'IN_PLAY' which we need to map to 'LIVE'
        cursor.execute("UPDATE matches SET status = 'LIVE' WHERE status = 'IN_PLAY'")
        conn.commit()
    
    # Export to JSON so Godot sees it
    import main
    main.export_to_json(db)
    print("[SUCCESS] DB Cleaned. Real Madrid and Napoli should now be visible in Godot.")

if __name__ == "__main__":
    final_cleanup()
