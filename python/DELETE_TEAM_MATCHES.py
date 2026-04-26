from database import LogicBetDB

def delete_specific_teams():
    db = LogicBetDB()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        print("[CLEANUP] Removing specific unwanted team matches...")
        # Delete by team names that shouldn't be in your top list
        teams_to_remove = ['Sunderland', 'Forest', 'Itesalat', 'Maleyet']
        
        for team in teams_to_remove:
            cursor.execute("""
                DELETE FROM matches 
                WHERE home_team_id IN (SELECT id FROM teams WHERE name LIKE ?)
                   OR away_team_id IN (SELECT id FROM teams WHERE name LIKE ?)
            """, (f'%{team}%', f'%{team}%'))
            print(f"  Removed {cursor.rowcount} matches for {team}.")
            
        conn.commit()
    
    import main
    main.export_to_json(db)
    print("[SUCCESS] Unwanted matches removed.")

if __name__ == "__main__":
    delete_specific_teams()
