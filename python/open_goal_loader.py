import json
import csv
import os
import requests
from datetime import datetime
from database import LogicBetDB

class OpenGoalDBLoader:
    def __init__(self, db=None):
        self.db = db or LogicBetDB()
        # NOTE: openfootball GitHub URLs are dead (404).
        # Historical data comes from local sample files + API imports.
        self.data_sources = {}
        
    def download_historical_data(self, save_path="../data"):
        """Download historical data from Open Goal DB repositories"""
        os.makedirs(save_path, exist_ok=True)
        
        print("--- DOWNLOADING HISTORICAL DATA FROM OPEN GOAL DB ---")
        
        for name, url in self.data_sources.items():
            try:
                print(f"  > Downloading {name}...")
                response = requests.get(url)
                response.raise_for_status()
                
                filename = os.path.join(save_path, f"{name}.json")
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(response.json(), f, indent=2, ensure_ascii=False)
                
                print(f"    [OK] Saved to {filename}")
                
            except Exception as e:
                print(f"    [ERROR] Failed to download {name}: {e}")
    
    def load_json_data(self, file_path):
        """Load JSON data from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None
    
    def import_historical_matches(self, matches_file):
        """Import historical matches from JSON file"""
        print("--- IMPORTING HISTORICAL MATCHES ---")
        
        data = self.load_json_data(matches_file)
        if not data:
            return 0
            
        imported = 0
        with self.db.get_connection() as conn:
            for match in data.get('matches', []):
                try:
                    # Extract match data
                    home_team = match.get('homeTeam', {}).get('name', '')
                    away_team = match.get('awayTeam', {}).get('name', '')
                    competition = match.get('competition', {}).get('name', '')
                    
                    if not home_team or not away_team:
                        continue
                    
                    # Add teams if they don't exist
                    home_id = self.db.add_team_if_not_exists(home_team)
                    away_id = self.db.add_team_if_not_exists(away_team)
                    
                    # Extract score and date
                    score = match.get('score', {})
                    home_score = score.get('fullTime', {}).get('home')
                    away_score = score.get('fullTime', {}).get('away')
                    
                    date_str = match.get('utcDate', '')
                    status = 'FT' if home_score is not None else 'NOT_STARTED'
                    
                    # Insert match
                    match_id = self.db.insert_match(
                        remote_id=match.get('id'),
                        date=date_str,
                        league=competition,
                        home_id=home_id,
                        away_id=away_id,
                        h_score=home_score,
                        a_score=away_score,
                        status=status
                    )
                    
                    imported += 1
                    
                except Exception as e:
                    print(f"Error importing match {match.get('id')}: {e}")
                    continue
        
        print(f"  [OK] Imported {imported} historical matches")
        return imported
    
    def import_teams_data(self, teams_file):
        """Import teams data from JSON file"""
        print("--- IMPORTING TEAMS DATA ---")
        
        data = self.load_json_data(teams_file)
        if not data:
            return 0
            
        imported = 0
        with self.db.get_connection() as conn:
            for team in data.get('teams', []):
                try:
                    team_name = team.get('name', '')
                    if not team_name:
                        continue
                    
                    team_id = self.db.add_team_if_not_exists(team_name)
                    imported += 1
                    
                except Exception as e:
                    print(f"Error importing team {team.get('name')}: {e}")
                    continue
        
        print(f"  [OK] Imported {imported} teams")
        return imported
    
    def create_sample_historical_data(self):
        """Create sample historical data for testing"""
        print("--- CREATING SAMPLE HISTORICAL DATA ---")
        
        sample_matches = {
            "matches": [
                {
                    "id": 100001,
                    "utcDate": "2024-01-15T15:00:00Z",
                    "status": "FINISHED",
                    "matchday": 20,
                    "stage": "REGULAR_SEASON",
                    "group": None,
                    "lastUpdated": "2024-01-15T17:00:00Z",
                    "homeTeam": {"id": 57, "name": "Arsenal"},
                    "awayTeam": {"id": 58, "name": "Chelsea"},
                    "score": {
                        "fullTime": {"home": 2, "away": 1},
                        "halfTime": {"home": 1, "away": 0},
                        "extraTime": {"home": None, "away": None},
                        "penalties": {"home": None, "away": None}
                    },
                    "competition": {"id": 39, "name": "Premier League"}
                },
                {
                    "id": 100002,
                    "utcDate": "2024-01-16T20:00:00Z",
                    "status": "FINISHED",
                    "matchday": 20,
                    "stage": "REGULAR_SEASON",
                    "group": None,
                    "lastUpdated": "2024-01-16T22:00:00Z",
                    "homeTeam": {"id": 61, "name": "Liverpool"},
                    "awayTeam": {"id": 62, "name": "Manchester City"},
                    "score": {
                        "fullTime": {"home": 1, "away": 1},
                        "halfTime": {"home": 0, "away": 1},
                        "extraTime": {"home": None, "away": None},
                        "penalties": {"home": None, "away": None}
                    },
                    "competition": {"id": 39, "name": "Premier League"}
                },
                {
                    "id": 100003,
                    "utcDate": "2024-01-17T19:45:00Z",
                    "status": "FINISHED",
                    "matchday": 20,
                    "stage": "REGULAR_SEASON",
                    "group": None,
                    "lastUpdated": "2024-01-17T21:45:00Z",
                    "homeTeam": {"id": 63, "name": "Barcelona"},
                    "awayTeam": {"id": 64, "name": "Real Madrid"},
                    "score": {
                        "fullTime": {"home": 3, "away": 2},
                        "halfTime": {"home": 2, "away": 1},
                        "extraTime": {"home": None, "away": None},
                        "penalties": {"home": None, "away": None}
                    },
                    "competition": {"id": 140, "name": "La Liga"}
                }
            ]
        }
        
        sample_teams = {
            "teams": [
                {"id": 57, "name": "Arsenal", "shortName": "Arsenal", "tla": "ARS"},
                {"id": 58, "name": "Chelsea", "shortName": "Chelsea", "tla": "CHE"},
                {"id": 61, "name": "Liverpool", "shortName": "Liverpool", "tla": "LIV"},
                {"id": 62, "name": "Manchester City", "shortName": "Man City", "tla": "MCI"},
                {"id": 63, "name": "Barcelona", "shortName": "Barcelona", "tla": "BAR"},
                {"id": 64, "name": "Real Madrid", "shortName": "Real Madrid", "tla": "RMA"}
            ]
        }
        
        # Save sample data
        os.makedirs("../data", exist_ok=True)
        
        with open("../data/sample_matches.json", 'w', encoding='utf-8') as f:
            json.dump(sample_matches, f, indent=2, ensure_ascii=False)
        
        with open("../data/sample_teams.json", 'w', encoding='utf-8') as f:
            json.dump(sample_teams, f, indent=2, ensure_ascii=False)
        
        print("  [OK] Sample data created in ../data/")
        
        # Import sample data
        matches_imported = self.import_historical_matches("../data/sample_matches.json")
        teams_imported = self.import_teams_data("../data/sample_teams.json")
        
        return matches_imported, teams_imported
    
    def bulk_import_from_directory(self, data_dir="../data"):
        """Import all JSON files from a directory"""
        print(f"--- BULK IMPORT FROM {data_dir} ---")
        
        total_matches = 0
        total_teams = 0
        
        for file in os.listdir(data_dir):
            if file.endswith('.json'):
                file_path = os.path.join(data_dir, file)
                
                if 'matches' in file.lower():
                    imported = self.import_historical_matches(file_path)
                    total_matches += imported
                elif 'teams' in file.lower():
                    imported = self.import_teams_data(file_path)
                    total_teams += imported
        
        print(f"  [SUMMARY] Imported {total_matches} matches and {total_teams} teams")
        return total_matches, total_teams

if __name__ == "__main__":
    loader = OpenGoalDBLoader()
    
    # Create sample data for testing
    matches, teams = loader.create_sample_historical_data()
    print(f"Sample data created: {matches} matches, {teams} teams")
    
    # Uncomment to download real data
    # loader.download_historical_data()
    # loader.bulk_import_from_directory()
