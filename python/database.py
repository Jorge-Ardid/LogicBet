import sqlite3
import os

class LogicBetDB:
    def __init__(self, db_path='../godot_app/logicbet.db'):
        # We now place the DB directly inside the Godot project folder
        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_path))
        print(f"--- LOGICBET DATABASE INITIALIZED ---")
        
        # Team Name Mapping Dictionary
        self.TEAM_MAP = {
            # English teams
            "Manchester City": "Man City",
            "Manchester City FC": "Man City",
            "Man City": "Man City",
            "Manchester United": "Man United",
            "Manchester United FC": "Man United",
            "Man United": "Man United",
            "Man Utd": "Man United",
            "MU": "Man United",
            "Tottenham Hotspur": "Tottenham",
            "Tottenham Hotspur FC": "Tottenham",
            "Arsenal FC": "Arsenal",
            "Chelsea FC": "Chelsea",
            "Liverpool FC": "Liverpool",
            "Newcastle United FC": "Newcastle",
            "West Ham United FC": "West Ham",
            "Aston Villa FC": "Aston Villa",
            "AFC Bournemouth": "Bournemouth",
            "Wolverhampton Wanderers FC": "Wolves",
            "Brighton & Hove Albion FC": "Brighton",
            "Crystal Palace FC": "Crystal Palace",
            "Nottingham Forest FC": "Forest",
            "Fulham FC": "Fulham",
            "Brentford FC": "Brentford",
            "Everton FC": "Everton",
            "Burnley FC": "Burnley",
            "Leeds United FC": "Leeds",
            "Sunderland AFC": "Sunderland",
            
            # Spanish teams
            "Club Atlético de Madrid": "Atletico Madrid",
            "Atletico de Madrid": "Atletico Madrid",
            "Club Atl. Madrid": "Atletico Madrid",
            "FC Barcelona": "Barcelona",
            "Barca": "Barcelona",
            "Real Madrid CF": "Real Madrid",
            "Real Madrid": "Real Madrid",
            "Real Sociedad de Fútbol": "Real Sociedad",
            "Real Sociedad de Futbol": "Real Sociedad",
            "Real Betis Balompié": "Betis",
            "Real Betis Balompie": "Betis",
            "RCD Espanyol de Barcelona": "Espanyol",
            "Villarreal CF": "Villarreal",
            "CA Osasuna": "Osasuna",
            "Rayo Vallecano de Madrid": "Rayo Vallecano",
            "Getafe CF": "Getafe",
            "RC Celta de Vigo": "Celta",
            "Celta Vigo": "Celta",
            "Celta de Vigo": "Celta",
            "Girona FC": "Girona",
            "Athletic Club": "Athletic Club",
            "Deportivo Alavés": "Alaves",
            "Deportivo Alaves": "Alaves",
            "UD Almería": "Almeria",
            "RCD Mallorca": "Mallorca",
            "Sevilla FC": "Sevilla",
            "Valencia CF": "Valencia",
            "UD Las Palmas": "Las Palmas",
            "Elche CF": "Elche",
            "Levante UD": "Levante",
            "Real Oviedo": "Oviedo",
            "Oviedo CF": "Oviedo",
            "Real Oviedo CF": "Oviedo",
            
            # German teams
            "FC Bayern München": "Bayern Munich",
            "FC Bayern Munchen": "Bayern Munich",
            "Bayern Munchen": "Bayern Munich",
            "Bayern Munich": "Bayern Munich",
            "Borussia Dortmund": "Dortmund",
            "Bayer 04 Leverkusen": "Leverkusen",
            "Bayer Leverkusen": "Leverkusen",
            "RB Leipzig": "Leipzig",
            "VfB Stuttgart": "Stuttgart",
            "TSG 1899 Hoffenheim": "Hoffenheim",
            "Eintracht Frankfurt": "Frankfurt",
            "SC Freiburg": "Freiburg",
            "1. FSV Mainz 05": "Mainz",
            "FC Augsburg": "Augsburg",
            "1. FC Union Berlin": "Union",
            "Hamburger SV": "Hamburg",
            "Borussia Mönchengladbach": "Gladbach",
            "Borussia Monchengladbach": "Gladbach",
            "Werder Bremen": "Bremen",
            "SV Werder Bremen": "Bremen",
            "1. FC Köln": "Koln",
            "1. FC Koln": "Koln",
            "1. Koln": "Koln",
            "1. Köln": "Koln",
            "FC St. Pauli 1910": "Pauli",
            "VfL Wolfsburg": "Wolfsburg",
            "1. FC Heidenheim 1846": "Heidenheim",
            
            # French teams
            "Paris Saint-Germain FC": "PSG",
            "Paris Saint-Germain": "PSG",
            "Paris Saint Germain": "PSG",
            "Paris SG": "PSG",
            "RC Lens": "Lens",
            "Olympique de Marseille": "Marseille",
            "Olympique Lyonnais": "Lyon",
            "LOSC Lille": "Lille",
            "AS Monaco FC": "Monaco",
            "AS Monaco": "Monaco",
            "Stade Rennais FC 1901": "Rennes",
            "Stade Rennais": "Rennes",
            "RC Strasbourg Alsace": "Strasbourg",
            "FC Lorient": "Lorient",
            "Toulouse FC": "Toulouse",
            "Stade Brestois 29": "Brest",
            "Paris FC": "Paris FC",
            "Angers SCO": "Angers",
            "Le Havre AC": "Le Havre",
            "OGC Nice": "Nice",
            "AJ Auxerre": "Auxerre",
            "FC Nantes": "Nantes",
            "FC Metz": "Metz",
            
            # Italian teams
            "FC Internazionale Milano": "Inter",
            "Internazionale": "Inter",
            "Inter Milan": "Inter",
            "AC Milan": "AC Milan",
            "Milan": "AC Milan",
            "SSC Napoli": "Napoli",
            "AS Roma": "Roma",
            "Juventus FC": "Juventus",
            "Atalanta BC": "Atalanta",
            "SS Lazio": "Lazio",
            "Bologna FC 1909": "Bologna",
            "Udinese Calcio": "Udinese",
            "US Sassuolo Calcio": "Sassuolo",
            "Torino FC": "Torino",
            "Parma Calcio 1913": "Parma",
            "Genoa CFC": "Genoa",
            "Cagliari Calcio": "Cagliari",
            "ACF Fiorentina": "Fiorentina",
            "US Cremonese": "Cremonese",
            "US Lecce": "Lecce",
            "Hellas Verona FC": "Verona",
            "Hellas Verona": "Verona",
            "Como 1907": "Como",
            "AC Pisa 1909": "Pisa",
            
            # European competitions
            "Sporting Clube de Portugal": "Sporting CP",
            "Sporting CP": "Sporting CP",
            "SL Benfica": "Benfica",
            "FC Porto": "Porto",
            "AFC Ajax": "Ajax",
            "PSV": "PSV",
            "Club Brugge KV": "Club Brugge",
        }
        
        print(f"TARGET PATH: {self.db_path}")
        self._init_db()
        self._sync_map_to_synonyms()

    def _sync_map_to_synonyms(self):
        """One-time migration: fills team_synonyms table from TEAM_MAP if it's empty."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM team_synonyms")
            if cursor.fetchone()[0] == 0:
                print("[MIGRATION] Populating team_synonyms from code map...")
                for full_name, short_name in self.TEAM_MAP.items():
                    # 1. Ensure the canonical team exists
                    cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (short_name,))
                    cursor.execute("SELECT id FROM teams WHERE name = ?", (short_name,))
                    team_id = cursor.fetchone()[0]
                    # 2. Add the full name as a synonym
                    cursor.execute("INSERT OR IGNORE INTO team_synonyms (team_id, synonym) VALUES (?, ?)", (team_id, full_name))
                conn.commit()

    def _normalize_name(self, name):
        """Standardizes team names. Checks DB synonyms first, then local map, then cleans strings."""
        if not name: return ""
        n_strip = name.strip()
        
        # 1. Check DB synonyms table first
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT team_id FROM team_synonyms WHERE synonym = ?", (n_strip,))
            res = cursor.fetchone()
            if res:
                cursor.execute("SELECT name FROM teams WHERE id = ?", (res[0],))
                name_res = cursor.fetchone()
                if name_res: return name_res[0]

        # 2. Check the manual map
        if n_strip in self.TEAM_MAP:
            return self.TEAM_MAP[n_strip]
            
        # 3. Aggressive cleanup
        clean = n_strip
        # Normalize special characters and remove dots
        clean = clean.replace(".", "").replace("ö", "o").replace("ü", "u").replace("ä", "a").replace("á", "a").replace("é", "e")
        
        # Remove common prefixes (order matters)
        prefixes = ["1 ", "AFC ", "FC ", "AC ", "SC ", "RC ", "SS ", "SSC ", "US ", "AS ", "LOSC ", "VfL ", "VfB ", "RCD ", "UD "]
        for p in prefixes:
            if clean.upper().startswith(p.upper()):
                clean = clean[len(p):].strip()
        
        # Remove common suffixes
        suffixes = [" FC", " CF", " AFC", " SC", " AC", " BC", " FK", " SK", " 04", " 05", " 1909", " 1910", " 1846"]
        for s in suffixes:
            if clean.upper().endswith(s.upper()):
                clean = clean[:-len(s)].strip()
        
        # Check map again for cleaned version
        return self.TEAM_MAP.get(clean, clean)

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Teams table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE,
                    elo_rating REAL DEFAULT 1500.0,
                    attack_rating REAL DEFAULT 50.0,
                    defense_rating REAL DEFAULT 50.0,
                    discipline_rating REAL DEFAULT 50.0,
                    corners_rating REAL DEFAULT 50.0,
                    current_form TEXT DEFAULT '',
                    rank INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0
                )
            ''')

            # Team Synonyms table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS team_synonyms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER,
                    synonym TEXT UNIQUE,
                    FOREIGN KEY(team_id) REFERENCES teams(id)
                )
            ''')
            
            # Migration check for new column
            cursor.execute("PRAGMA table_info(teams)")
            cols = [c[1] for c in cursor.fetchall()]
            if "current_form" not in cols:
                cursor.execute("ALTER TABLE teams ADD COLUMN current_form TEXT DEFAULT ''")
            if "rank" not in cols:
                cursor.execute("ALTER TABLE teams ADD COLUMN rank INTEGER DEFAULT 0")
            if "points" not in cols:
                cursor.execute("ALTER TABLE teams ADD COLUMN points INTEGER DEFAULT 0")
            
            # Matches table (Historical Data & Fixtures)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY,
                    remote_id INTEGER UNIQUE, -- ID from API
                    date TEXT,
                    league TEXT,
                    league_id INTEGER,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    home_score INTEGER,
                    away_score INTEGER,
                    ht_score_h INTEGER,
                    ht_score_a INTEGER,
                    form_home TEXT, -- WDLWW
                    form_away TEXT,
                    status TEXT,
                    corners_h INTEGER DEFAULT 0,
                    corners_a INTEGER DEFAULT 0,
                    yellow_cards_h INTEGER DEFAULT 0,
                    yellow_cards_a INTEGER DEFAULT 0,
                    red_cards_h INTEGER DEFAULT 0,
                    red_cards_a INTEGER DEFAULT 0,
                    shots_on_h INTEGER DEFAULT 0,
                    shots_on_a INTEGER DEFAULT 0,
                    shots_off_h INTEGER DEFAULT 0,
                    shots_off_a INTEGER DEFAULT 0,
                    xg_h REAL DEFAULT 0.0,
                    xg_a REAL DEFAULT 0.0,
                    possession_h INTEGER DEFAULT 50,
                    possession_a INTEGER DEFAULT 50,
                    stats_fetched INTEGER DEFAULT 0,
                    FOREIGN KEY(home_team_id) REFERENCES teams(id),
                    FOREIGN KEY(away_team_id) REFERENCES teams(id)
                )
            ''')

            # Odds table
            # --- AUTO-MIGRATION: Add HT columns if missing ---
            try:
                cursor.execute("SELECT ht_score_h FROM matches LIMIT 1")
            except sqlite3.OperationalError:
                print("[DATABASE] Migrating: Adding HT columns to existing table...")
                cursor.execute("ALTER TABLE matches ADD COLUMN ht_score_h INTEGER DEFAULT NULL")
                cursor.execute("ALTER TABLE matches ADD COLUMN ht_score_a INTEGER DEFAULT NULL")
                conn.commit()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS odds (
                    match_id INTEGER,
                    market TEXT, -- '1X2', 'TOTAL_GOALS', 'CORNERS', 'CARDS', 'BTTS'
                    selection TEXT, -- 'Home', 'Away', 'Draw', 'Over 2.5', 'Under 2.5', etc.
                    opening_odd REAL,
                    closing_odd REAL,
                    FOREIGN KEY(match_id) REFERENCES matches(id),
                    PRIMARY KEY (match_id, market, selection)
                )
            ''')

            # Predictions / Value Bets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    algorithm TEXT,
                    market TEXT,
                    selection TEXT,
                    calculated_prob REAL,
                    bookmaker_odd REAL,
                    value_percentage REAL,
                    confidence_level TEXT, -- 'HIGH', 'MEDIUM', 'LOW'
                    is_hit INTEGER, -- 1 if won, 0 if lost, NULL if pending
                    FOREIGN KEY(match_id) REFERENCES matches(id)
                )
            ''')

            # User Config table (Bankroll, Settings, etc)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # User Bets table (Tracking real/tracked bets)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    selection TEXT,
                    stake REAL,
                    odd REAL,
                    status TEXT DEFAULT 'PENDING', -- 'PENDING', 'WON', 'LOST'
                    profit REAL DEFAULT 0.0,
                    FOREIGN KEY(match_id) REFERENCES matches(id)
                )
            ''')

            # --- MIGRATION: Auto-add columns ---
            cursor.execute("PRAGMA table_info(matches)")
            columns = [col[1] for col in cursor.fetchall()]
            if "home_score" not in columns:
                cursor.execute("ALTER TABLE matches ADD COLUMN home_score INTEGER")
            if "away_score" not in columns:
                cursor.execute("ALTER TABLE matches ADD COLUMN away_score INTEGER")
            if "league_id" not in columns:
                cursor.execute("ALTER TABLE matches ADD COLUMN league_id INTEGER")
            if "elo_processed" not in columns:
                cursor.execute("ALTER TABLE matches ADD COLUMN elo_processed INTEGER DEFAULT 0")
            if "h_elo_change" not in columns:
                cursor.execute("ALTER TABLE matches ADD COLUMN h_elo_change REAL DEFAULT 0.0")
            if "a_elo_change" not in columns:
                cursor.execute("ALTER TABLE matches ADD COLUMN a_elo_change REAL DEFAULT 0.0")
                
            # Migration for match stats
            if "corners_h" not in columns:
                new_cols = [
                    "corners_h INTEGER DEFAULT 0", "corners_a INTEGER DEFAULT 0",
                    "yellow_cards_h INTEGER DEFAULT 0", "yellow_cards_a INTEGER DEFAULT 0",
                    "red_cards_h INTEGER DEFAULT 0", "red_cards_a INTEGER DEFAULT 0",
                    "shots_on_h INTEGER DEFAULT 0", "shots_on_a INTEGER DEFAULT 0",
                    "shots_off_h INTEGER DEFAULT 0", "shots_off_a INTEGER DEFAULT 0",
                    "xg_h REAL DEFAULT 0.0", "xg_a REAL DEFAULT 0.0",
                    "possession_h INTEGER DEFAULT 50", "possession_a INTEGER DEFAULT 50",
                    "stats_fetched INTEGER DEFAULT 0"
                ]
                for col in new_cols:
                    try:
                        cursor.execute(f"ALTER TABLE matches ADD COLUMN {col}")
                    except sqlite3.OperationalError:
                        pass # Column might already exist
                        
            # Initialize sync status if not exists
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('last_sync_time', '0')")
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('sync_error', '')")
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('api_requests_left', '100')")
            
            conn.commit()

    def get_config(self, key):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            res = cursor.fetchone()
            return res[0] if res else None

    def set_config(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def add_team_if_not_exists(self, team_name):
        norm_name = self._normalize_name(team_name)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Double check if this normalized name is a synonym for something else
            cursor.execute("SELECT team_id FROM team_synonyms WHERE synonym = ?", (norm_name,))
            syn = cursor.fetchone()
            if syn:
                return syn[0]
                
            # 2. Otherwise insert or get
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (norm_name,))
            conn.commit()
            cursor.execute("SELECT id FROM teams WHERE name = ?", (norm_name,))
            return cursor.fetchone()[0]
            
    def update_team_elo(self, team_id, new_elo):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE teams SET elo_rating = ? WHERE id = ?", (new_elo, team_id))
            conn.commit()

    def update_team_stats(self, team_id, attack, defense):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE teams SET attack_rating = ?, defense_rating = ? WHERE id = ?", (attack, defense, team_id))
            conn.commit()

    def insert_match(self, remote_id, date, league, home_id, away_id, h_score=None, a_score=None, status='NOT_STARTED', form_h="", form_a="", league_id=None, ht_h=None, ht_a=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check if match already exists by remote_id
            cursor.execute("SELECT id FROM matches WHERE remote_id = ?", (remote_id,))
            res = cursor.fetchone()
            
            # 2. If not found by remote_id, check by Date + Teams (for multi-source consistency)
            if not res:
                # Use DATE(date) to allow for small time differences between APIs
                match_date = date.split('T')[0] if 'T' in date else date
                cursor.execute("""
                    SELECT id FROM matches 
                    WHERE DATE(date) = ? AND home_team_id = ? AND away_team_id = ?
                """, (match_date, home_id, away_id))
                res = cursor.fetchone()
            
            if res:
                # Update existing match
                match_id = res[0]
                cursor.execute("""
                    UPDATE matches SET 
                        home_score = COALESCE(?, home_score),
                        away_score = COALESCE(?, away_score),
                        ht_score_h = COALESCE(?, ht_score_h),
                        ht_score_a = COALESCE(?, ht_score_a),
                        status = ?,
                        form_home = ?,
                        form_away = ?,
                        league_id = COALESCE(?, league_id),
                        remote_id = COALESCE(remote_id, ?)
                    WHERE id = ?
                """, (h_score, a_score, ht_h, ht_a, status, form_h, form_a, league_id, remote_id, match_id))
            else:
                # Insert new match
                cursor.execute("""
                    INSERT INTO matches (remote_id, date, league, league_id, home_team_id, away_team_id, home_score, away_score, ht_score_h, ht_score_a, status, form_home, form_away)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (remote_id, date, league, league_id, home_id, away_id, h_score, a_score, ht_h, ht_a, status, form_h, form_a))
                match_id = cursor.lastrowid
                
            conn.commit()
            return match_id

    def fetch_h2h_matches(self, home_id, away_id, limit=5):
        """Fetches last N matches between these two specific teams."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT home_score, away_score, home_team_id, away_team_id, date
                FROM matches
                WHERE ((home_team_id = ? AND away_team_id = ?) OR (home_team_id = ? AND away_team_id = ?))
                AND status IN ('FT', 'AET', 'PEN', 'FINISHED')
                ORDER BY date DESC LIMIT ?
            """
            cursor.execute(query, (home_id, away_id, away_id, home_id, limit))
            return cursor.fetchall()
            
    def insert_prediction(self, match_id, algorithm, market, selection, prob, odds, value, confidence='MEDIUM'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions (match_id, algorithm, market, selection, calculated_prob, bookmaker_odd, value_percentage, confidence_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, algorithm, market, selection, prob, odds, value, confidence))
            conn.commit()

    def update_match_stats(self, match_id, stats):
        """Update match statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE matches SET 
                    corners_h=?, corners_a=?, 
                    yellow_cards_h=?, yellow_cards_a=?, 
                    red_cards_h=?, red_cards_a=?,
                    shots_on_h=?, shots_on_a=?, 
                    shots_off_h=?, shots_off_a=?, 
                    xg_h=?, xg_a=?, 
                    possession_h=?, possession_a=?,
                    stats_fetched=1
                WHERE id=?
            """, (
                stats.get('corners_h', 0), stats.get('corners_a', 0),
                stats.get('yellow_cards_h', 0), stats.get('yellow_cards_a', 0),
                stats.get('red_cards_h', 0), stats.get('red_cards_a', 0),
                stats.get('shots_on_h', 0), stats.get('shots_on_a', 0),
                stats.get('shots_off_h', 0), stats.get('shots_off_a', 0),
                stats.get('xg_h', 0.0), stats.get('xg_a', 0.0),
                stats.get('possession_h', 50), stats.get('possession_a', 50),
                match_id
            ))
            conn.commit()

if __name__ == "__main__":
    # Test DB creation
    db = LogicBetDB()
    print(f"DB initialized at {db.db_path}")
