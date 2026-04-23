import sqlite3
import os

# Starting Point: 1500 (Base) + Points from your screenshots
STANDINGS_DATA = {
    "Premier League": {
        "Arsenal": 70, "City": 61, "United": 55, "Villa": 54, "Liverpool": 52,
        "Chelsea": 48, "Brentford": 47, "Everton": 47, "Brighton": 46, "Bournemouth": 45,
        "Fulham": 44, "Sunderland": 43, "Newcastle": 42, "Palace": 39, "Leeds": 33,
        "Forest": 32, "West Ham": 32, "Tottenham": 30, "Burnley": 20, "Wolves": 17
    },
    "Bundesliga": {
        "Bayern": 76, "Dortmund": 64, "Leipzig": 56, "Stuttgart": 53, "Leverkusen": 52,
        "Hoffenheim": 51, "Frankfurt": 42, "Freiburg": 37, "Mainz": 33, "Augsburg": 33,
        "Union": 32, "Hamburg": 31, "Gladbach": 30, "Bremen": 28, "Koln": 27,
        "Pauli": 25, "Wolfsburg": 21, "Heidenheim": 19
    },
    "La Liga": {
        "Barcelona": 79, "Real Madrid": 70, "Villarreal": 58, "Atletico": 57, "Betis": 45,
        "Celta": 44, "Sociedad": 42, "Getafe": 41, "Osasuna": 38, "Espanyol": 38,
        "Athletic": 38, "Girona": 38, "Vallecano": 35, "Valencia": 35, "Alaves": 33,
        "Elche": 32, "Mallorca": 31, "Sevilla": 31, "Levante": 26, "Oviedo": 24
    },
    "Ligue 1": {
        "Paris": 63, "Lens": 59, "Marseille": 52, "Lille": 50, "Monaco": 49,
        "Lyon": 48, "Rennes": 47, "Strasbourg": 43, "Lorient": 38, "Toulouse": 37,
        "Brest": 36, "Paris FC": 35, "Angers": 33, "Le Havre": 28, "Nice": 27,
        "Auxerre": 24, "Nantes": 19, "Metz": 15
    },
    "Serie A": {
        "Inter": 72, "Napoli": 65, "Milan": 63, "Como": 58, "Juventus": 57, "Roma": 57,
        "Atalanta": 53, "Bologna": 45, "Lazio": 44, "Udinese": 43, "Sassuolo": 42, "Torino": 39,
        "Parma": 35, "Genoa": 33, "Cagliari": 33, "Fiorentina": 32, "Cremonese": 27, "Lecce": 27,
        "Verona": 18, "Pisa": 18
    }
}

def find_all_db_files(root_dir):
    db_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file == "logicbet.db":
                db_files.append(os.path.join(root, file))
    return db_files

def seed_everything():
    root_path = r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll"
    db_files = find_all_db_files(root_path)
    
    if not db_files:
        print("!!! No logicbet.db found anywhere in the project folder !!!")
        return

    print(f"--- FOUND {len(db_files)} DATABASE COPIES ---")
    
    for db_path in db_files:
        print(f"\n[SYNC] Updating database at: {db_path}")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Reset processing history in every DB
            try: cursor.execute("UPDATE matches SET elo_processed = 0")
            except: pass

            for league, teams in STANDINGS_DATA.items():
                for partial_name, points in teams.items():
                    target_elo = 1500.0 + points
                    
                    # Update all matching team names (partial match)
                    cursor.execute("SELECT id, name FROM teams")
                    teams_in_db = cursor.fetchall()
                    for t_id, t_name in teams_in_db:
                        if partial_name.lower() in t_name.lower():
                            cursor.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (target_elo, t_id))
            
            conn.commit()
            conn.close()
            print(f"[OK] Database updated successfully.")
        except Exception as e:
            print(f"[ERROR] Could not update {db_path}: {e}")

    print("\n--- ALL DATABASES SYNCHRONIZED WITH STARTING POINTS! ---")

if __name__ == "__main__":
    seed_everything()
