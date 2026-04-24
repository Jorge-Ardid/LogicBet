import requests
import json
from datetime import datetime, timedelta

class FootballDataClient:
    def __init__(self, api_key="72cd4a1c41ff402eba0da37f4bbc5ff6"):
        self.api_key = api_key
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {
            "X-Auth-Token": self.api_key
        }
        self.is_mock = (api_key == "PLACEHOLDER_KEY")
        self.requests_remaining = 10  # Free tier: 10 requests per minute
        
        # League mappings for Football-Data.org
        self.league_mappings = {
            39: "PL",      # Premier League
            140: "PD",     # La Liga
            78: "BL1",     # Bundesliga
            61: "FL1",     # Ligue 1
            135: "SA",     # Serie A
            2: "CL",       # Champions League
            3: "EL",       # Europa League
            88: "DED",     # Eredivisie
            94: "PPL"      # Primeira Liga
        }
        
        # Reverse mapping for normalization (FD Code/ID -> API-Football ID)
        self.reverse_mappings = {
            "PL": 39, "PD": 140, "BL1": 78, "SA": 135, "FL1": 61,
            "CL": 2, "EL": 3, "DED": 88, "PPL": 94
        }
        
        # Mapping by FD Competition ID (as returned in match object)
        self.id_mappings = {
            2021: 39,   # PL (England)
            2014: 140,  # PD (Spain)
            2002: 78,   # BL1 (Germany)
            2019: 135,  # SA (Italy)
            2015: 61,   # FL1 (France)
            2001: 2,    # CL (Champions League)
            2146: 3,    # EL (Europa League)
            2003: 88,   # DED (Netherlands) - FIXED (was 78)
            2017: 94    # PPL (Portugal)
        }

        
        # Available competitions in free tier
        self.free_competitions = ["PL", "PD", "BL1", "SA", "FL1", "CL", "DED", "PPL", "FLC"]

    def _make_request(self, endpoint):
        """Make API request with rate limiting"""
        if self.is_mock:
            return None
            
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers)
            
            # Rate limit handling
            remaining = response.headers.get("X-Requests-Available-Minute")
            if remaining:
                self.requests_remaining = int(remaining)
                if self.requests_remaining <= 2:
                    print(f"!!! Football-Data.org Rate Limit Warning (Remaining: {remaining}) !!!")
                    if self.requests_remaining <= 0:
                        print("!!! Rate limit reached, pausing requests !!!")
                        # Don't return None here - the current request already succeeded
                        # Just prevent FUTURE requests
            
            if response.status_code == 429:
                print(f"!!! Error 429: Too Many Requests. Waiting... !!!")
                return None
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Football-Data.org API Error ({endpoint}): {e}")
            return None

    def get_limit_left(self):
        return self.requests_remaining

    def fetch_competitions(self):
        """Get all available competitions"""
        if self.is_mock:
            return self._get_mock_competitions()
        return self._make_request("competitions")

    def fetch_matches(self, competition_id=None, date_from=None, date_to=None):
        """Fetch matches for specific competition or date range"""
        if self.is_mock:
            return self._get_mock_matches()
            
        params = []
        endpoint = "matches"
        
        if competition_id:
            endpoint = f"competitions/{competition_id}/matches"
        
        if date_from:
            params.append(f"dateFrom={date_from}")
        if date_to:
            params.append(f"dateTo={date_to}")
            
        if params:
            endpoint += "?" + "&".join(params)
            
        return self._make_request(endpoint)

    def fetch_all_matches_batch(self, date_from, date_to):
        """Fetch ALL matches across ALL free-tier competitions in a SINGLE request.
        This is the most efficient way to use the Football-Data.org free tier.
        Instead of 7 requests (one per league), this uses just 1."""
        if self.is_mock:
            return self._get_mock_matches()
        
        if self.requests_remaining <= 0:
            print("[BATCH] No requests remaining, skipping")
            return None
            
        # Football-Data.org Free tier limit is often 10 days for broad matches endpoint
        d1 = datetime.strptime(date_from, "%Y-%m-%d")
        d2 = datetime.strptime(date_to, "%Y-%m-%d")
        if (d2 - d1).days > 10:
            print(f"!!! Warning: Date range {(d2 - d1).days} days is too large for Football-Data.org. Reducing to 10 days. !!!")
            date_to = (d1 + timedelta(days=10)).strftime("%Y-%m-%d")
            
        endpoint = f"matches?dateFrom={date_from}&dateTo={date_to}"
        return self._make_request(endpoint)

    def fetch_standings(self, competition_id):
        """Get current standings for a competition"""
        if self.is_mock:
            return self._get_mock_standings()
        return self._make_request(f"competitions/{competition_id}/standings")

    def fetch_team_matches(self, team_id, date_from=None, date_to=None):
        """Get matches for a specific team"""
        if self.is_mock:
            return []
            
        endpoint = f"teams/{team_id}/matches"
        params = []
        
        if date_from:
            params.append(f"dateFrom={date_from}")
        if date_to:
            params.append(f"dateTo={date_to}")
            
        if params:
            endpoint += "?" + "&".join(params)
            
        return self._make_request(endpoint)

    def fetch_teams(self, competition_id):
        """Get all teams in a competition"""
        if self.is_mock:
            return []
        return self._make_request(f"competitions/{competition_id}/teams")

    def translate_league_id(self, api_football_id):
        """Convert API-Football league ID to Football-Data.org format"""
        return self.league_mappings.get(api_football_id)
        
    def resolve_api_league_id(self, fd_id=None, fd_code=None):
        """Translate Football-Data ID or Code back to API-Football ID"""
        if fd_id and fd_id in self.id_mappings:
            return self.id_mappings[fd_id]
        if fd_code and fd_code in self.reverse_mappings:
            return self.reverse_mappings[fd_code]
        return fd_id # Return original if no mapping found

    # --- MOCK DATA ---
    def _get_mock_competitions(self):
        return {
            "competitions": [
                {"id": 39, "name": "Premier League", "code": "PL"},
                {"id": 140, "name": "La Liga", "code": "PD"},
                {"id": 78, "name": "Bundesliga", "code": "BL1"},
                {"id": 135, "name": "Serie A", "code": "SA"},
                {"id": 61, "name": "Ligue 1", "code": "FL1"}
            ]

        }

    def _get_mock_matches(self):
        return {
            "matches": [
                {
                    "id": 123456,
                    "utcDate": datetime.now().isoformat(),
                    "status": "SCHEDULED",
                    "matchday": 30,
                    "stage": "REGULAR_SEASON",
                    "group": None,
                    "lastUpdated": datetime.now().isoformat(),
                    "homeTeam": {"id": 57, "name": "Arsenal"},
                    "awayTeam": {"id": 58, "name": "Chelsea"},
                    "score": {"fullTime": {"home": None, "away": None}, "halfTime": {"home": None, "away": None}},
                    "competition": {"id": 39, "name": "Premier League", "code": "PL"}
                }
            ]
        }

    def _get_mock_standings(self):
        return {
            "standings": [
                {
                    "stage": "REGULAR_SEASON",
                    "type": "TOTAL",
                    "group": None,
                    "table": [
                        {
                            "position": 1,
                            "team": {"id": 57, "name": "Arsenal"},
                            "playedGames": 25,
                            "won": 18,
                            "draw": 4,
                            "lost": 3,
                            "goalsFor": 45,
                            "goalsAgainst": 20,
                            "goalDifference": 25,
                            "points": 58
                        }
                    ]
                }
            ]
        }

if __name__ == "__main__":
    client = FootballDataClient()
    print("Football-Data.org Client Ready.")
    print("Available competitions:", client.free_competitions)
