import json
import os
from database import LogicBetDB

class ConfigManager:
    def __init__(self, config_file=None):
        if config_file is None:
            # Use absolute path relative to this file
            self.config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/api_config.json"))
        else:
            self.config_file = config_file
        self.db = LogicBetDB()
        self.default_config = {
            "api_keys": {
                "football_data_org": "PLACEHOLDER_KEY",
                "api_football": "PLACEHOLDER_KEY",
                "rapidapi_generic": "PLACEHOLDER_KEY",
                "network_as_code": "3725c32b04mshb942c2df0e3ab79p18f60djsn14472b9a742"
            },
            "data_sources": {
                "primary": "football_data_org",  # Primary data source
                "fallback": "api_football",      # Fallback if primary fails
                "historical": "open_goal_db"      # For historical data
            },
            "rate_limits": {
                "football_data_org": {
                    "requests_per_minute": 10,
                    "daily_limit": None
                },
                "api_football": {
                    "requests_per_minute": None,
                    "daily_limit": 100
                }
            },
            "sync_settings": {
                "cooldown_seconds": 12 * 60 * 60,  # 12 hours
                "auto_retry": True,
                "max_retries": 3,
                "use_historical_data": True
            },
            "leagues": {
                "enabled": [39, 140, 78, 61, 135, 2, 3],  # League IDs
                "priority": {
                    "football_data_org": ["PL", "PD", "BL1", "SA", "FL1", "CL", "EL"],
                    "api_football": [39, 140, 78, 61, 135, 2, 3]
                }
            }
        }
        self.load_config()

    def load_config(self):
        """Load configuration from file or create default"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print(f"[CONFIG] Loaded from {self.config_file}")
            else:
                self.config = self.default_config.copy()
                self.save_config()
                print(f"[CONFIG] Created default config at {self.config_file}")
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to load config: {e}")
            self.config = self.default_config.copy()

    def save_config(self):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            print(f"[CONFIG] Saved to {self.config_file}")
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save config: {e}")

    def get_api_key(self, service):
        """Get API key for a specific service"""
        return self.config.get("api_keys", {}).get(service, "PLACEHOLDER_KEY")

    def set_api_key(self, service, key):
        """Set API key for a specific service"""
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        self.config["api_keys"][service] = key
        self.save_config()
        print(f"[CONFIG] API key set for {service}")

    def get_primary_source(self):
        """Get primary data source"""
        return self.config.get("data_sources", {}).get("primary", "football_data_org")

    def get_fallback_source(self):
        """Get fallback data source"""
        return self.config.get("data_sources", {}).get("fallback", "api_football")

    def set_data_sources(self, primary=None, fallback=None):
        """Set data source priorities"""
        if "data_sources" not in self.config:
            self.config["data_sources"] = {}
        
        if primary:
            self.config["data_sources"]["primary"] = primary
        if fallback:
            self.config["data_sources"]["fallback"] = fallback
            
        self.save_config()

    def get_rate_limit(self, service):
        """Get rate limit settings for a service"""
        return self.config.get("rate_limits", {}).get(service, {})

    def get_sync_settings(self):
        """Get sync settings"""
        return self.config.get("sync_settings", {})

    def get_enabled_leagues(self):
        """Get list of enabled leagues"""
        return self.config.get("leagues", {}).get("enabled", [])

    def set_enabled_leagues(self, leagues):
        """Set enabled leagues"""
        if "leagues" not in self.config:
            self.config["leagues"] = {}
        self.config["leagues"]["enabled"] = leagues
        self.save_config()

    def is_api_key_valid(self, service):
        """Check if API key is set and not placeholder"""
        key = self.get_api_key(service)
        return key and key != "PLACEHOLDER_KEY"

    def get_available_sources(self):
        """Get list of available data sources with valid API keys"""
        available = []
        for service in ["football_data_org", "api_football"]:
            if self.is_api_key_valid(service):
                available.append(service)
        return available

    def store_to_db(self):
        """Store important config values to database"""
        try:
            # Store API keys in database (encrypted or as config)
            for service, key in self.config.get("api_keys", {}).items():
                if key != "PLACEHOLDER_KEY":
                    self.db.set_config(f"api_key_{service}", key)
            
            # Store data source preferences
            self.db.set_config("primary_data_source", self.get_primary_source())
            self.db.set_config("fallback_data_source", self.get_fallback_source())
            
            # Store sync settings
            sync_settings = self.get_sync_settings()
            self.db.set_config("sync_cooldown", sync_settings.get("cooldown_seconds", 43200))
            self.db.set_config("use_historical_data", sync_settings.get("use_historical_data", True))
            
            print("[CONFIG] Settings stored to database")
            
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to store to DB: {e}")

    def load_from_db(self):
        """Load config values from database"""
        try:
            # Load API keys from database
            for service in ["football_data_org", "api_football", "rapidapi_generic", "network_as_code"]:
                db_key = self.db.get_config(f"api_key_{service}")
                if db_key and db_key != "PLACEHOLDER_KEY":
                    self.set_api_key(service, db_key)
                    print(f"[CONFIG] Loaded {service} key from database")
            
            # Load data source preferences
            primary = self.db.get_config("primary_data_source")
            fallback = self.db.get_config("fallback_data_source")
            if primary or fallback:
                self.set_data_sources(primary, fallback)
                print(f"[CONFIG] Loaded data sources: {primary} -> {fallback}")
            
            # Load sync settings
            cooldown = self.db.get_config("sync_cooldown")
            if cooldown:
                self.config["sync_settings"]["cooldown_seconds"] = int(cooldown)
            
            use_historical = self.db.get_config("use_historical_data")
            if use_historical is not None:
                self.config["sync_settings"]["use_historical_data"] = use_historical.lower() == "true"
            
            print("[CONFIG] Settings loaded from database")
            
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to load from DB: {e}")

    def print_status(self):
        """Print current configuration status"""
        print("\n=== CONFIGURATION STATUS ===")
        
        # API Keys
        print("API Keys:")
        for service in ["football_data_org", "api_football"]:
            key = self.get_api_key(service)
            status = "✅ SET" if self.is_api_key_valid(service) else "❌ NOT SET"
            masked = key[:8] + "..." if key and key != "PLACEHOLDER_KEY" else "PLACEHOLDER"
            print(f"  {service}: {status} ({masked})")
        
        # Data Sources
        print(f"\nData Sources:")
        print(f"  Primary: {self.get_primary_source()}")
        print(f"  Fallback: {self.get_fallback_source()}")
        print(f"  Available: {self.get_available_sources()}")
        
        # Sync Settings
        sync = self.get_sync_settings()
        print(f"\nSync Settings:")
        print(f"  Cooldown: {sync.get('cooldown_seconds', 43200)} seconds ({sync.get('cooldown_seconds', 43200)//3600} hours)")
        print(f"  Use Historical Data: {sync.get('use_historical_data', True)}")
        print(f"  Auto Retry: {sync.get('auto_retry', True)}")
        
        # Enabled Leagues
        print(f"\nEnabled Leagues: {self.get_enabled_leagues()}")
        print("=" * 30)

if __name__ == "__main__":
    config = ConfigManager()
    config.print_status()
    
    # Example usage:
    # config.set_api_key("football_data_org", "your_api_key_here")
    # config.set_data_sources(primary="football_data_org", fallback="api_football")
    # config.store_to_db()
