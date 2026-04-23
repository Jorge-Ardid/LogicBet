import requests
import json
import random
from datetime import datetime, timedelta

class APIFootballClient:
    def __init__(self, api_key="PLACEHOLDER_KEY"):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": self.api_key
        }
        self.is_mock = (api_key == "PLACEHOLDER_KEY")
        self.requests_remaining = 100  # Free plan: 100 requests per day
        self.last_error_code = None

    def _make_request(self, endpoint, params):
        url = f"{self.base_url}/{endpoint}"
        self.last_error_code = None
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            # Rate limit handling
            remaining = response.headers.get("x-ratelimit-requests-remaining")
            if remaining and remaining.isdigit():
                self.requests_remaining = int(remaining)
                if self.requests_remaining <= 1:
                    print(f"!!! CRITICAL: API Rate Limit Reached (Remaining: {remaining}) !!!")
            
            if response.status_code == 429:
                print(f"!!! Error 429: Too Many Requests. Try again later. !!!")
                self.last_error_code = "RATE_LIMIT"
                return []
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('errors'):
                errors = data['errors']
                print(f"API Business Error ({endpoint}): {errors}")
                
                # Check for plan restrictions
                if isinstance(errors, dict) and 'plan' in errors:
                    self.last_error_code = "PLAN_RESTRICTION"
                elif isinstance(errors, list) and any('plan' in str(e).lower() for e in errors):
                    self.last_error_code = "PLAN_RESTRICTION"
                else:
                    self.last_error_code = "BUSINESS_ERROR"
                    
                return []
                
            return data.get('response', [])
        except Exception as e:
            print(f"Network/API Error ({endpoint}): {e}")
            self.last_error_code = "NETWORK_ERROR"
            return []

    def get_limit_left(self):
        return self.requests_remaining

    def fetch_fixtures(self, date=None, league_id=None):
        if self.is_mock: return self._get_mock_fixtures(date)
        params = {"date": date or datetime.now().strftime("%Y-%m-%d")}
        if league_id:
            params["league"] = league_id
            params["season"] = 2025
        return self._make_request('fixtures', params)

    def fetch_league_results(self, league_id, season=2025):
        if self.is_mock: return []
        params = {"league": league_id, "season": season}
        return self._make_request('fixtures', params)

    def fetch_fixtures_range(self, league_id, date_from, date_to, season=2025):
        if self.is_mock: return []
        params = {"league": league_id, "season": season, "from": date_from, "to": date_to}
        return self._make_request('fixtures', params)

    def fetch_odds(self, fixture_id):
        if self.is_mock: return self._get_mock_odds(fixture_id)
        return self._make_request('odds', {"fixture": fixture_id})

    def fetch_odds_by_league(self, league_id, season=2025):
        """Fetch all available odds for a league in a single request."""
        if self.is_mock: return []
        params = {"league": league_id, "season": season}
        return self._make_request('odds', params)

    def fetch_team_stats(self, league_id, team_id, season=2025):
        if self.is_mock: return None
        params = {"league": league_id, "team": team_id, "season": season}
        data = self._make_request('teams/statistics', params)
        return data[0] if data else None

    def fetch_standings(self, league_id, season=2025):
        if self.is_mock: return []
        params = {"league": league_id, "season": season}
        data = self._make_request('standings', params)
        return data[0]['league']['standings'][0] if data else []

    def fetch_leagues(self):
        """Get all available leagues"""
        if self.is_mock: return []
        return self._make_request('leagues', {})

    def fetch_teams(self, league_id, season=2025):
        """Get all teams in a league"""
        if self.is_mock: return []
        params = {"league": league_id, "season": season}
        return self._make_request('teams', params)

    def fetch_head_to_head(self, h2h, league_id=None, season=2025):
        """Get head-to-head matches between two teams"""
        if self.is_mock: return []
        params = {"h2h": h2h}
        if league_id:
            params["league"] = league_id
            params["season"] = season
        return self._make_request('fixtures/headtohead', params)

    def fetch_predictions(self, fixture_id):
        """Get predictions for a specific fixture"""
        if self.is_mock: return None
        params = {"fixture": fixture_id}
        data = self._make_request('predictions', params)
        return data[0] if data else None

    def fetch_lineups(self, fixture_id):
        """Get lineups for a specific fixture"""
        if self.is_mock: return []
        params = {"fixture": fixture_id}
        return self._make_request('fixtures/lineups', params)

    def fetch_events(self, fixture_id):
        """Get events (goals, cards, substitutions) for a fixture"""
        if self.is_mock: return []
        params = {"fixture": fixture_id}
        return self._make_request('fixtures/events', params)

    def fetch_match_statistics(self, fixture_id):
        """Get detailed statistics (xG, corners, cards, shots) for a fixture"""
        if self.is_mock: return self._get_mock_statistics()
        params = {"fixture": fixture_id}
        return self._make_request('fixtures/statistics', params)

    # --- MOCK DATA ---
    def _get_mock_fixtures(self, date=None):
        teams = ["Arsenal", "Chelsea", "Liverpool", "Man City", "Man United"]
        fixtures = []
        for i in range(3):
            home = random.choice(teams); away = random.choice([t for t in teams if t != home])
            fixtures.append({
                "fixture": {"id": random.randint(1000, 9999), "date": f"{date or '2026-04-10'}T15:00:00+00:00", "status": {"short": "NS"}},
                "league": {"name": "Premier League", "id": 39},
                "teams": {"home": {"id": 1, "name": home}, "away": {"id": 2, "name": away}},
                "goals": {"home": None, "away": None}
            })
        return fixtures

    def _get_mock_odds(self, fixture_id):
        return [{"fixture": {"id": fixture_id}, "bookmakers": [{"name": "Bet365", "bets": [{"name": "Match Winner", "values": [{"value": "Home", "odd": 1.9}, {"value": "Draw", "odd": 3.4}, {"value": "Away", "odd": 4.1}]}]}]}]
        
    def _get_mock_statistics(self):
        return []

if __name__ == "__main__":
    client = APIFootballClient()
    print("API Client Ready.")
