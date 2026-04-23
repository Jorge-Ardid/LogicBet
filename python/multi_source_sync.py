import time
import os
from datetime import datetime, timedelta
from database import LogicBetDB
from api_client import APIFootballClient
from football_data_client import FootballDataClient
from open_goal_loader import OpenGoalDBLoader
from config_manager import ConfigManager
from analytics import BettingAnalytics
from rapidapi_client import RapidAPIClient, create_rapidapi_client

class MultiSourceSyncEngine:
    def __init__(self):
        self.db = LogicBetDB()
        self.config = ConfigManager()
        self.analytics = BettingAnalytics(self.db)
        
        # Load configuration from database first
        self.config.load_from_db()
        
        # Initialize API clients
        self.api_football = None
        self.football_data_org = None
        self.open_goal_loader = OpenGoalDBLoader(self.db)
        
        # Internal state for error tracking
        self.api_football_disabled = False
        
        self._init_clients()

    def _init_clients(self):
        """Initialize API clients with available keys"""
        # API-Football (RapidAPI)
        if self.config.is_api_key_valid("api_football"):
            self.api_football = APIFootballClient(
                api_key=self.config.get_api_key("api_football")
            )
            print("[SYNC] API-Football client initialized")
        
        # Football-Data.org
        if self.config.is_api_key_valid("football_data_org"):
            self.football_data_org = FootballDataClient(
                api_key=self.config.get_api_key("football_data_org")
            )
            print("[SYNC] Football-Data.org client initialized")
        
        # RapidAPI Generic
        if self.config.is_api_key_valid("rapidapi_generic"):
            self.rapidapi_generic = create_rapidapi_client("generic_football", 
                api_key=self.config.get_api_key("rapidapi_generic"))
            print("[SYNC] RapidAPI Generic client initialized")
        
        # Network-as-Code
        if self.config.is_api_key_valid("network_as_code"):
            self.network_as_code = create_rapidapi_client("network_as_code",
                api_key=self.config.get_api_key("network_as_code"))
            print("[SYNC] Network-as-Code client initialized")

    def get_primary_client(self):
        """Get the primary API client based on configuration"""
        primary = self.config.get_primary_source()
        if primary == "football_data_org" and self.football_data_org:
            return self.football_data_org, "football_data_org"
        elif primary == "api_football" and self.api_football:
            return self.api_football, "api_football"
        
        # Fallback to available client
        if self.football_data_org:
            return self.football_data_org, "football_data_org"
        elif self.api_football:
            return self.api_football, "api_football"
        
        return None, None

    def get_fallback_client(self):
        """Get the fallback API client"""
        fallback = self.config.get_fallback_source()
        if fallback == "football_data_org" and self.football_data_org:
            return self.football_data_org, "football_data_org"
        elif fallback == "api_football" and self.api_football:
            return self.api_football, "api_football"
        
        return None, None

    def sync_with_fallback(self, operation_name, primary_func, fallback_func=None):
        """Execute operation with primary client, fallback to secondary if needed"""
        client, source_name = self.get_primary_client()
        
        if not client:
            print(f"[SYNC] No API clients available for {operation_name}")
            return None
        
        try:
            print(f"[SYNC] Trying {operation_name} with {source_name}")
            result = primary_func(client)
            
            if result:
                print(f"[SYNC] ✅ {operation_name} successful with {source_name}")
                return result
            else:
                print(f"[SYNC] ❌ {operation_name} failed with {source_name}")
                
        except Exception as e:
            print(f"[SYNC] ❌ {operation_name} error with {source_name}: {e}")
        
        # Try fallback
        if fallback_func:
            fallback_client, fallback_name = self.get_fallback_client()
            if fallback_client and fallback_name != source_name:
                try:
                    print(f"[SYNC] Trying {operation_name} with fallback {fallback_name}")
                    result = fallback_func(fallback_client)
                    
                    if result:
                        print(f"[SYNC] ✅ {operation_name} successful with fallback {fallback_name}")
                        return result
                    else:
                        print(f"[SYNC] ❌ {operation_name} failed with fallback {fallback_name}")
                        
                except Exception as e:
                    print(f"[SYNC] ❌ {operation_name} error with fallback {fallback_name}: {e}")
        
        return None

    def fetch_fixtures_multi_source(self, date=None, league_ids=None):
        """Fetch fixtures using multiple data sources"""
        def fetch_from_football_data(client):
            if not league_ids:
                return client.fetch_matches(date_from=date, date_to=date)
            
            all_matches = []
            for league_id in league_ids:
                fd_league_id = client.translate_league_id(league_id)
                if fd_league_id:
                    matches = client.fetch_matches(fd_league_id, date, date)
                    if matches and 'matches' in matches:
                        all_matches.extend(matches['matches'])
            
            return {"matches": all_matches} if all_matches else None

        def fetch_from_api_football(client):
            all_fixtures = []
            for league_id in (league_ids or self.config.get_enabled_leagues()):
                fixtures = client.fetch_fixtures(date=date, league_id=league_id)
                if fixtures:
                    all_fixtures.extend(fixtures)
            return all_fixtures

        # Try primary source first
        result = self.sync_with_fallback(
            "fetch_fixtures",
            fetch_from_football_data if self.football_data_org else fetch_from_api_football,
            fetch_from_api_football if self.football_data_org else None
        )
        
        return result

    def fetch_standings_multi_source(self, league_id):
        """Fetch standings using multiple data sources"""
        def fetch_from_football_data(client):
            fd_league_id = client.translate_league_id(league_id)
            if fd_league_id:
                return client.fetch_standings(fd_league_id)
            return None

        def fetch_from_api_football(client):
            return client.fetch_standings(league_id)

        return self.sync_with_fallback(
            "fetch_standings",
            fetch_from_football_data if self.football_data_org else fetch_from_api_football,
            fetch_from_api_football if self.football_data_org else None
        )

    def fetch_odds_multi_source(self, league_id):
        """Fetch odds for all matches in a league (single request efficiency)"""
        if self.api_football and not self.api_football_disabled:
            print(f"  [ODDS] Fetching odds for league {league_id}...")
            return self.api_football.fetch_odds_by_league(league_id)
        return []


    def sync_live_data(self, target_leagues=None, max_requests=None):
        """Enhanced sync with BATCH request strategy — uses 1 API call instead of 21."""
        self._cleanup_stale_matches() # Move old NS matches to history
        target_leagues = target_leagues or self.config.get_enabled_leagues()
        
        print("\n=== MULTI-SOURCE SYNC ENGINE ===")
        print(f"Target leagues: {target_leagues}")
        
        # Determine date range - Reduce to 7 days to avoid 400 errors with Football-Data.org
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # === STRATEGY: Single batch request for all dates ===
        if self.football_data_org:
            available_requests = self.football_data_org.get_limit_left()
            print(f"Available requests: {available_requests}")
            
            if available_requests <= 0:
                print("[SYNC] No requests available. Skipping API sync.")
                return False
            
            if available_requests <= 2:
                print("[SYNC] Low requests. Fetching today only...")
                date_from = datetime.now().strftime("%Y-%m-%d")
                date_to = date_from
            elif available_requests <= 5:
                print("[SYNC] Limited requests. Fetching today + tomorrow...")
                date_from = datetime.now().strftime("%Y-%m-%d")
                date_to = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                print("[SYNC] Good request availability. Full 3-day sync...")
        
        # --- BATCH FETCH: ONE request for the entire date range ---
        print(f"\n> Fetching ALL fixtures for {date_from} to {date_to} (single request)...")
        all_fixtures = []
        requests_used = 0
        
        if self.football_data_org:
            result = self.football_data_org.fetch_all_matches_batch(date_from, date_to)
            if result and 'matches' in result:
                raw_matches = result['matches']
                requests_used += 1
                
                # Build league ID whitelist for Football-Data.org competition IDs
                fd_league_ids = set()
                found_fd_codes = set()
                
                for league_id in target_leagues:
                    fd_code = self.football_data_org.translate_league_id(league_id)
                    if fd_code:
                        fd_league_ids.add(fd_code)
                
                # Filter by target leagues CLIENT-SIDE
                for match in raw_matches:
                    comp_code = match.get('competition', {}).get('code', '')
                    if comp_code in fd_league_ids or not fd_league_ids:
                        all_fixtures.append(match)
                        found_fd_codes.add(comp_code)
                
                print(f"  [BATCH] Football-Data.org: Got {len(raw_matches)} matches total, {len(all_fixtures)} in target leagues")
                
                # --- PARTIAL FALLBACK: Check for missing leagues ---
                if self.api_football and not self.api_football_disabled:
                    gap_leagues = []
                    for lid in target_leagues:
                        fd_code = self.football_data_org.translate_league_id(lid)
                        # Fallback ONLY if the league isn't supported by Football-Data.org mapping
                        if not fd_code:
                            gap_leagues.append(lid)
                    
                    if gap_leagues:
                        print(f"  [FALLBACK] Fetching {len(gap_leagues)} explicitly unsupported leagues from API-Football...")
                        for lid in gap_leagues:
                            if self.api_football_disabled: break
                            
                            for d_offset in range((datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")).days + 1):
                                if self.api_football_disabled: break
                                
                                d = (datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=d_offset)).strftime("%Y-%m-%d")
                                fixtures = self.api_football.fetch_fixtures(date=d, league_id=lid)
                                
                                if not fixtures and getattr(self.api_football, 'last_error_code', None) == "PLAN_RESTRICTION":
                                    print("  [FALLBACK] Detected Free Plan restriction for this season. Skipping further fallback attempts.")
                                    self.api_football_disabled = True
                                    break
                                    
                                if fixtures:
                                    all_fixtures.extend(fixtures)
                                requests_used += 1

            else:
                print("  [BATCH] No data from Football-Data.org")
                # Full fallback to API-Football
                if self.api_football:
                    print(f"  [BATCH] Trying full API-Football fallback ({date_from} to {date_to})...")
                    for league_id in target_leagues:
                        # Iterate through ALL dates in range for fallback
                        delta = datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")
                        for i in range(delta.days + 1):
                            d = (datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
                            fixtures = self.api_football.fetch_fixtures(date=d, league_id=league_id)
                            if fixtures:
                                all_fixtures.extend(fixtures)
                            requests_used += 1
        
        elif self.api_football:
            # No Football-Data.org configured, use API-Football directly
            for d_offset in range((datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")).days + 1):
                d = (datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=d_offset)).strftime("%Y-%m-%d")
                for league_id in target_leagues:
                    fixtures = self.api_football.fetch_fixtures(date=d, league_id=league_id)
                    if fixtures:
                        all_fixtures.extend(fixtures)
                    requests_used += 1

        
        if not all_fixtures:
            print("!!! WARNING: No fixtures from any source !!!")
            self.db.set_config("sync_error", "No data available from any source")
            return False
        
        print(f"[SYNC] Used {requests_used} request(s) this sync")
        
        # Process fixtures
        processed = 0
        for fixture in all_fixtures:
            try:
                # Normalize fixture data based on source
                normalized = self._normalize_fixture_data(fixture)
                if not normalized:
                    continue
                
                # Add teams
                home_id = self.db.add_team_if_not_exists(normalized['home_team'])
                away_id = self.db.add_team_if_not_exists(normalized['away_team'])
                
                # Insert match
                match_id = self.db.insert_match(
                    remote_id=normalized['remote_id'],
                    date=normalized['date'],
                    league=normalized['league'],
                    home_id=home_id,
                    away_id=away_id,
                    h_score=normalized['home_score'],
                    a_score=normalized['away_score'],
                    status=normalized['status'],
                    league_id=normalized.get('league_id'),
                    ht_h=normalized.get('ht_score_h'),
                    ht_a=normalized.get('ht_score_a')
                )
                
                # Generate predictions
                preds = self.analytics.determine_predictions(match_id, home_id, away_id, None, "", "")
                
                # Update predictions
                with self.db.get_connection() as conn:
                    conn.execute("DELETE FROM predictions WHERE match_id = ?", (match_id,))
                for p in preds:
                    self.db.insert_prediction(
                        p['match_id'], p['algorithm'], p['market'], 
                        p['selection'], p['calculated_prob'], p['bookmaker_odd'], 
                        p['value_percentage'], p['confidence_level']
                    )
                
                processed += 1
                print(f"  ✅ Processed: {normalized['home_team']} vs {normalized['away_team']}")
                
            except Exception as e:
                print(f"  ❌ Error processing fixture: {e}")
                continue
        
        # --- NEW: Sync Odds for all processed matches in batch ---
        print("\n> Synchronizing Odds (Value Detection)...")
        for lid in target_leagues:
            try:
                odds_data = self.fetch_odds_multi_source(lid)
                if odds_data:
                    self._process_odds_data(odds_data)
            except Exception as e:
                print(f"  [ODDS] Error for league {lid}: {e}")
        
        print(f"\n[SYNC] Processed {processed} fixtures successfully")
        self.db.set_config("sync_error", "") # Clear old errors on success
        return True

    def _process_odds_data(self, odds_list):
        """Processes and stores bookmaker odds in the database"""
        count = 0
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for odd_obj in odds_list:
                f_id = odd_obj.get('fixture', {}).get('id')
                if not f_id: continue
                
                # We typically look for Bet365 (8) or the first available bookmaker
                bookmakers = odd_obj.get('bookmakers', [])
                if not bookmakers: continue
                
                # Try to find a major bookie or just use first
                bookie = next((b for b in bookmakers if b['id'] == 8), bookmakers[0])
                
                # Find Match Winner (1) odds
                match_winner = next((b for b in bookie.get('bets', []) if b['id'] == 1), None)
                if not match_winner: continue
                
                # Extract Home/Draw/Away odds
                h_odd = d_odd = a_odd = 0.0
                for val in match_winner.get('values', []):
                    if val['value'] == 'Home': h_odd = float(val['odd'])
                    elif val['value'] == 'Draw': d_odd = float(val['odd'])
                    elif val['value'] == 'Away': a_odd = float(val['odd'])
                
                if h_odd > 0:
                    # Update predictions table with these real odds for 1X2 market
                    # We also find the match internal ID first
                    cursor.execute("SELECT id FROM matches WHERE remote_id = ?", (f_id,))
                    match_row = cursor.fetchone()
                    if match_row:
                        m_id = match_row[0]
                        # Update Match Winner prediction and calculate Value
                        # Value = (Probability * Odd) - 1.0
                        cursor.execute("""
                            UPDATE predictions 
                            SET bookmaker_odd = (CASE WHEN selection LIKE '%П1%' THEN ? WHEN selection LIKE '%П2%' THEN ? ELSE ? END),
                                value_percentage = (calculated_prob * (CASE WHEN selection LIKE '%П1%' THEN ? WHEN selection LIKE '%П2%' THEN ? ELSE ? END)) - 1.0
                            WHERE match_id = ? AND market = '1X2/DC'
                        """, (h_odd, a_odd, d_odd, h_odd, a_odd, d_odd, m_id))
                        count += 1

            conn.commit()
        if count > 0:
            print(f"  [ODDS] Updated {count} matches with real bookmaker odds")


    def _cleanup_stale_matches(self):
        """Finds old NS/TIMED matches and marks them as FINISHED to clean up UI"""
        print("[DATABASE] Cleaning up stale matches...")
        cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE matches 
                SET status = 'FINISHED' 
                WHERE status IN ('NS', 'TIMED', 'SCHEDULED', 'TBD') 
                AND date < ?
            """, (cutoff,))
            # --- Remove ghost/duplicate matches ---
            # Find matches where same home+away teams play on the same date
            # but one is NS (no score) and another is FINISHED (has score)
            cursor.execute("""
                DELETE FROM matches 
                WHERE id IN (
                    SELECT m1.id 
                    FROM matches m1
                    JOIN matches m2 ON m1.home_team_id = m2.home_team_id 
                                    AND m1.away_team_id = m2.away_team_id
                                    AND DATE(m1.date) = DATE(m2.date)
                                    AND m1.id != m2.id
                    WHERE m1.status IN ('NS', 'NOT_STARTED', 'UNKNOWN')
                      AND m2.status IN ('FT', 'FINISHED', 'AET', 'PEN')
                )
            """)
            ghost_deleted = cursor.rowcount
            if ghost_deleted > 0:
                print(f"  [OK] Removed {ghost_deleted} duplicate ghost matches")
                
            conn.commit()

    def _get_localized_league_name(self, league_id):
        """Map API league IDs to localized names to avoid confusion (like multiple Premier Leagues)"""
        mapping = {
            39: "Прем'єр-ліга (Англія)",
            140: "Ла Ліга (Іспанія)",
            78: "Бундесліга (Німеччина)",
            61: "Ліга 1 (Франція)",
            135: "Серія А (Італія)",
            2: "Ліга Чемпіонів",
            3: "Ліга Європи",
            848: "Ліга Конференцій",
            88: "Ередивізі (Нідерланди)",
            94: "Прімейра-ліга (Португалія)",
            40: "Чемпіоншип (Англія)"
        }
        return mapping.get(league_id)

    def _normalize_fixture_data(self, fixture):
        """Normalize fixture data from different API sources"""
        # Football-Data.org format
        if 'homeTeam' in fixture and 'awayTeam' in fixture and 'competition' in fixture:
            status_raw = fixture.get('status', 'UNKNOWN')
            # Map Football-Data status to our internal short format
            status_map = {
                'FINISHED': 'FT',
                'SCHEDULED': 'NS',
                'TIMED': 'NS',
                'POSTPONED': 'PST',
                'CANCELLED': 'CANC',
                'IN_PLAY': 'LIVE',
                'PAUSED': 'LIVE'
            }
            status = status_map.get(status_raw, status_raw)
            
            # Resolve API-Football league ID for consistency
            fd_code = fixture.get('competition', {}).get('code')
            fd_id = fixture.get('competition', {}).get('id')
            league_id = self.football_data_org.resolve_api_league_id(fd_id=fd_id, fd_code=fd_code)
            
            # Translate league name
            league_name = fixture.get('competition', {}).get('name', '')
            local_league_name = self._get_localized_league_name(league_id) or league_name
            
            return {
                'remote_id': fixture.get('id'),
                'date': fixture.get('utcDate', ''),
                'league': local_league_name,
                'league_id': league_id,
                'home_team': fixture.get('homeTeam', {}).get('name', ''),
                'away_team': fixture.get('awayTeam', {}).get('name', ''),
                'home_score': fixture.get('score', {}).get('fullTime', {}).get('home'),
                'away_score': fixture.get('score', {}).get('fullTime', {}).get('away'),
                'ht_score_h': fixture.get('score', {}).get('halfTime', {}).get('home'),
                'ht_score_a': fixture.get('score', {}).get('halfTime', {}).get('away'),
                'status': status
            }
        
        # API-Football format
        elif 'fixture' in fixture and 'teams' in fixture and 'league' in fixture:
            status_raw = fixture.get('fixture', {}).get('status', {}).get('short', 'UNKNOWN')
            # Normalize common statuses
            status_map = {
                'FINISHED': 'FT',
                'IN_PLAY': 'LIVE',
                'SCHEDULED': 'NS',
                'TIMED': 'NS',
                'POSTPONED': 'PST',
                'CANCELLED': 'CANC'
            }
            status = status_map.get(status_raw, status_raw)
            
            league_id = fixture.get('league', {}).get('id')
            
            # Translate league name
            league_name = fixture.get('league', {}).get('name', '')
            local_league_name = self._get_localized_league_name(league_id) or league_name
            
            return {
                'remote_id': fixture.get('fixture', {}).get('id'),
                'date': fixture.get('fixture', {}).get('date', ''),
                'league': local_league_name,
                'league_id': league_id,
                'home_team': fixture.get('teams', {}).get('home', {}).get('name', ''),
                'away_team': fixture.get('teams', {}).get('away', {}).get('name', ''),
                'home_score': fixture.get('goals', {}).get('home'),
                'away_score': fixture.get('goals', {}).get('away'),
                'ht_score_h': fixture.get('score', {}).get('halftime', {}).get('home'),
                'ht_score_a': fixture.get('score', {}).get('halftime', {}).get('away'),
                'status': status
            }
        
        return None

    def sync_historical_data(self):
        """Sync historical data from Open Goal DB"""
        if not self.config.get_sync_settings().get('use_historical_data', True):
            print("[SYNC] Historical data sync disabled")
            return False
        
        print("\n=== HISTORICAL DATA SYNC ===")
        
        # Check if database already has teams
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM teams")
            team_count = cursor.fetchone()[0]
            
            if team_count > 0:
                print(f"[HISTORICAL] Database already has {team_count} teams. Skipping sample data creation.")
            else:
                # Try to create sample data only if DB is empty
                matches, teams = self.open_goal_loader.create_sample_historical_data()
                print(f"[HISTORICAL] Created sample data: {matches} matches, {teams} teams")
        
        # Try to download real data if available (Optional)
        try:
            # Only try to bulk import if there are files in ../data
            data_dir = "../data"
            if os.path.exists(data_dir) and any(f.endswith('.json') for f in os.listdir(data_dir)):
                self.open_goal_loader.bulk_import_from_directory()
            else:
                print("[HISTORICAL] No external data files found in ../data. Skipping bulk import.")
        except Exception as e:
            print(f"[HISTORICAL] Bulk import skipped: {e}")
        
        return True

    def _refresh_clients(self):
        """Re-initialize API clients with current config keys"""
        fd_key = self.config.get_api_key("football_data_org")
        af_key = self.config.get_api_key("api_football")
        
        self.api_football = APIFootballClient(af_key)
        self.football_data_org = FootballDataClient(fd_key)
        
        if not self.api_football or not self.api_football.api_key:
            self.api_football = None
        if not self.football_data_org or not self.football_data_org.api_key:
            self.football_data_org = None

    def run_full_sync(self, force_sync=False):
        """Run complete sync with all data sources"""
        # Reload config from DB and re-initialize clients to ensure latest keys
        self.config.load_from_db()
        self._init_clients()
        
        sync_settings = self.config.get_sync_settings()
        cooldown = sync_settings.get('cooldown_seconds', 43200)
        
        # Check cooldown
        if not force_sync:
            last_sync = float(self.db.get_config("last_sync_time") or 0)
            current_time = time.time()
            elapsed = current_time - last_sync
            
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                hours_left = remaining // 3600
                mins_left = (remaining % 3600) // 60
                print(f"[SYNC] Cooldown active: {int(hours_left)}h {int(mins_left)}m remaining")
                return False
        
        # Check API limits before attempting sync
        if self.football_data_org and self.football_data_org.get_limit_left() <= 1:
            print("[SYNC] Football-Data.org limit reached. Checking reset time...")
            
            # Store last limit check time
            last_limit_check = float(self.db.get_config("last_limit_check") or 0)
            current_time = time.time()
            
            # If it's been more than 1 hour since last check, try again
            if current_time - last_limit_check > 3600:  # 1 hour
                print("[SYNC] Testing if limits have reset...")
                # Test with a small request
                test_result = self.football_data_org.fetch_competitions()
                if test_result and self.football_data_org.get_limit_left() > 1:
                    print("[SYNC] ✅ Limits have reset! Proceeding with sync...")
                    self.db.set_config("last_limit_check", current_time)
                else:
                    print(f"[SYNC] Limits still low ({self.football_data_org.get_limit_left()}). Waiting...")
                    self.db.set_config("last_limit_check", current_time)
                    return False
            else:
                time_until_reset = 3600 - (current_time - last_limit_check)
                minutes_left = int(time_until_reset / 60)
                print(f"[SYNC] Checking again in {minutes_left} minutes...")
                return False
        
        print(f"\n{'='*50}")
        print("STARTING MULTI-SOURCE SYNC")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Primary source: {self.config.get_primary_source()}")
        print(f"Fallback source: {self.config.get_fallback_source()}")
        print(f"{'='*50}")
        
        try:
            # 1. Sync historical data (if enabled)
            if sync_settings.get('use_historical_data', True):
                self.sync_historical_data()
            
            # 2. Sync live data
            success = self.sync_live_data()
            
            if success:
                # Update sync timestamp
                self.db.set_config("last_sync_time", time.time())
                self.db.set_config("sync_error", "")
                
                # Store current API limits
                if self.football_data_org:
                    self.db.set_config("football_data_requests_left", self.football_data_org.get_limit_left())
                if self.api_football:
                    self.db.set_config("api_football_requests_left", self.api_football.get_limit_left())
                
                print(f"\n[SYNC] ✅ Full sync completed successfully")
                return True
            else:
                print(f"\n[SYNC] ❌ Sync failed")
                return False
                
        except Exception as e:
            error_msg = f"Sync error: {str(e)}"
            self.db.set_config("sync_error", error_msg)
            print(f"\n[SYNC] ❌ {error_msg}")
            return False

    def print_status(self):
        """Print sync engine status"""
        print("\n=== MULTI-SOURCE SYNC STATUS ===")
        
        # API clients status
        print("API Clients:")
        print(f"  API-Football: {'✅ Active' if self.api_football else '❌ Inactive'}")
        print(f"  Football-Data.org: {'✅ Active' if self.football_data_org else '❌ Inactive'}")
        
        # Last sync info
        last_sync = self.db.get_config("last_sync_time")
        if last_sync:
            sync_time = datetime.fromtimestamp(float(last_sync))
            print(f"  Last sync: {sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("  Last sync: Never")
        
        # API limits
        fd_requests = self.db.get_config("football_data_requests_left")
        af_requests = self.db.get_config("api_football_requests_left")
        print(f"  Requests left - Football-Data.org: {fd_requests or 'Unknown'}")
        print(f"  Requests left - API-Football: {af_requests or 'Unknown'}")
        
        # Errors
        error = self.db.get_config("sync_error")
        if error:
            print(f"  Last error: {error}")
        
        print("=" * 35)

if __name__ == "__main__":
    engine = MultiSourceSyncEngine()
    engine.print_status()
    
    # Example usage:
    # engine.run_full_sync(force_sync=True)
