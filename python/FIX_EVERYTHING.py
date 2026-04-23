import sqlite3
import os
import sys

# Data exactly as requested: 1500 + Points
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

# Find all DBs to be safe
def find_all_dbs():
    root = r"C:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll"
    found = []
    for r, d, files in os.walk(root):
        if "logicbet.db" in files:
            found.append(os.path.join(r, "logicbet.db"))
    return found

def run_fix():
    dbs = find_all_dbs()
    if not dbs:
        print("!!! Could not find logicbet.db !!!")
        return

    # Add current dir to path for imports
    sys.path.append(os.path.dirname(__file__))
    from analytics import BettingAnalytics

    for path in dbs:
        print(f"\n--- REPAIRING DATABASE: {path} ---")
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        
        # 1. Reset Elo Processed
        try: cursor.execute("UPDATE matches SET elo_processed = 0")
        except: pass
        
        # 2. Set Baseline (Aggressive match)
        cursor.execute("SELECT id, name FROM teams")
        db_teams = cursor.fetchall()
        
        seeded = 0
        for league, teams in STANDINGS_DATA.items():
            for p_name, pts in teams.items():
                target = 1500.0 + pts
                for t_id, t_name in db_teams:
                    if p_name.lower() in t_name.lower():
                        cursor.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (target, t_id))
                        seeded += 1
        print(f"  [OK] Baseline seeded for {seeded} teams.")
        conn.commit()

        # 3. Recalculate History immediately
        class DBStub:
            def get_connection(self): return sqlite3.connect(path)
        
        db_stub = DBStub()
        engine = BettingAnalytics(None)
        
        cursor.execute("""
            SELECT id, home_team_id, away_team_id, home_score, away_score 
            FROM matches 
            WHERE status IN ('FT', 'AET', 'PEN') AND elo_processed = 0
            ORDER BY date ASC
        """)
        matches = cursor.fetchall()
        for m in matches:
            m_id, h_id, a_id, h_s, a_s = m
            # Simple Elo recalc inline to avoid complex imports
            h_elo = conn.execute("SELECT elo_rating FROM teams WHERE id = ?", (h_id,)).fetchone()[0]
            a_elo = conn.execute("SELECT elo_rating FROM teams WHERE id = ?", (a_id,)).fetchone()[0]
            
            # Elo math
            k = 20
            ea = 1 / (1 + 10 ** ((a_elo - h_elo) / 400))
            sa = 1.0 if h_s > a_s else (0.5 if h_s == a_s else 0.0)
            
            nh = h_elo + k * (sa - ea)
            na = a_elo + k * ((1.0 - sa) - (1.0 - ea))
            
            conn.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (nh, h_id))
            conn.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (na, a_id))
            conn.execute("UPDATE matches SET elo_processed = 1 WHERE id = ?", (m_id,))
            print(f"  [ELO] Match {m_id} processed ({h_id} vs {a_id})")
        
        conn.commit()
        conn.close()
        print("--- REPAIR COMPLETE FOR THIS DB ---")

if __name__ == "__main__":
    run_fix()
