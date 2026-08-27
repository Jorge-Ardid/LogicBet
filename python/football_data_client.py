import os
import requests
import json
from datetime import datetime, timedelta

# --- Shared key loader: env FOOTBALL_DATA_KEY -> data/api_config.json ---
# Watch both legacy 'football_data_org' and new 'football_data_key' keys.
def load_football_data_key():
    """Resolve Football-Data.org token. Priority: env, then api_config.json."""
    candidate = os.environ.get("FOOTBALL_DATA_KEY") or os.environ.get(
        "FOOTBALL_DATA_ORG_KEY")
    if candidate and candidate.strip() and candidate != "PLACEHOLDER_KEY":
        return candidate.strip()
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "api_config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            keys = (json.load(f).get("api_keys") or {})
        for k in ("football_data_key", "football_data_org"):
            if keys.get(k) and keys[k] != "PLACEHOLDER_KEY":
                return str(keys[k]).strip()
    except Exception:                                    # noqa: BLE001
        pass
    return None


class FootballDataClient:
    def __init__(self, api_key=None):
        api_key = api_key or load_football_data_key() or (
            "72cd4a1c41ff402eba0da37f4bbc5ff6")
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
        """Fetch ALL matches across ALL free-tier competitions for the date range.

        Football-Data.org limits the broad /matches endpoint to ~10-day windows,
        so the range is split into <=10-day chunks. Each chunk = 1 API request.

        Returns a single dict in the same {'matches': [...]} format, or None.
        """
        if self.is_mock:
            return self._get_mock_matches()

        if self.requests_remaining <= 0:
            print("[BATCH] No requests remaining, skipping")
            return None

        # Football-Data.org free limit is ~10 days for broad matches endpoint
        d1 = datetime.strptime(date_from, "%Y-%m-%d")
        d2 = datetime.strptime(date_to, "%Y-%m-%d")
        max_range = timedelta(days=10)

        total_days = (d2 - d1).days
        if total_days < 0:
            print(f"[BATCH] Invalid date range: {date_from} -> {date_to}")
            return None

        if total_days > 10:
            print(f"[BATCH] Date range {total_days} days exceeds 10-day limit. Splitting into chunks...")

        all_matches = []
        chunk_start = d1
        while chunk_start <= d2:
            chunk_end = min(chunk_start + max_range, d2)
            cf = chunk_start.strftime("%Y-%m-%d")
            ct = chunk_end.strftime("%Y-%m-%d")

            endpoint = f"matches?dateFrom={cf}&dateTo={ct}"
            result = self._make_request(endpoint)
            if result and 'matches' in result:
                all_matches.extend(result['matches'])
            else:
                print(f"  [BATCH] Chunk {cf} -> {ct} returned no data")

            chunk_start = chunk_end + timedelta(days=1)

        if not all_matches:
            return None
        return {"matches": all_matches}

    def get_finished_matches_scores(self, date_from=None, date_to=None,
                                    full_payload=False):
        """PidsSummer scores of FINISHED matches from Football-Data.

        GET https://api.football-data.org/v4/matches?status=FINISHED
        (optionally narrowed by dateFrom..dateTo), paginated by 100.
        Returns a dict { fd_match_id: {
            "fd_id", "home", "away", "utc_date", "competition_id",
            "home_team", "away_team"} }  or {"matches": [...]} when full.
        """
        if self.is_mock:
            return {}

        collected = []
        limit = 100
        offset = 0
        while True:
            follows = ["status=FINISHED", f"limit={limit}", f"offset={offset}"]
            if date_from:
                follows.append(f"dateFrom={date_from}")
            if date_to:
                follows.append(f"dateTo={date_to}")
            endpoint = "matches?" + "&".join(follows)
            data = self._make_request(endpoint)
            if not data or not data.get("matches"):
                break
            batch = data["matches"]
            collected.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
            if offset > 2000:
                break

        if full_payload:
            return {"matches": collected}

        result = {}
        for m in collected:
            score = (m.get("score") or {}).get("fullTime") or {}
            home = score.get("home")
            away = score.get("away")
            home_team = (m.get("homeTeam") or {}).get("name")
            away_team = (m.get("awayTeam") or {}).get("name")
            comp = (m.get("competition") or {}).get("id")
            result[m.get("id")] = {
                "fd_id": m.get("id"),
                "home": home,
                "away": away,
                "utc_date": m.get("utcDate"),
                "competition_id": comp,
                "home_team": home_team,
                "away_team": away_team,
            }
        return result

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
