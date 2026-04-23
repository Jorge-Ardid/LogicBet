#!/usr/bin/env python3
"""
Football Data Sources Setup Script
This script helps configure API keys and initial settings for the football data sources.
"""

import os
import sys
from config_manager import ConfigManager
from multi_source_sync import MultiSourceSyncEngine

def print_banner():
    print("=" * 60)
    print("🏈 FOOTBALL DATA SOURCES SETUP")
    print("=" * 60)
    print("\nThis script will help you configure:")
    print("1. Football-Data.org API (Recommended - Free Tier)")
    print("2. API-Football via RapidAPI (Free Tier)")
    print("3. Open Goal DB (Historical Data - No API Key Required)")
    print("\n📋 SETUP INSTRUCTIONS:")
    print("-" * 40)

def print_api_instructions():
    print("\n🔑 API KEY INSTRUCTIONS:")
    print("-" * 30)
    
    print("\n1️⃣ FOOTBALL-DATA.ORG (Recommended):")
    print("   • Visit: https://www.football-data.org/")
    print("   • Register for a free account")
    print("   • Get your API key from the dashboard")
    print("   • Free tier: 10 requests/minute")
    print("   • Covers: Top 5 European leagues + Champions League")
    
    print("\n2️⃣ API-FOOTBALL (via RapidAPI):")
    print("   • Visit: https://rapidapi.com/api-sports/api/api-football/")
    print("   • Subscribe to the free plan")
    print("   • Get your RapidAPI key")
    print("   • Free tier: 100 requests/day")
    print("   • Covers: 800+ leagues worldwide")
    
    print("\n3️⃣ OPEN GOAL DB (Historical):")
    print("   • No API key required")
    print("   • Open source historical data")
    print("   • Great for training Elo models")

def get_user_input(prompt, input_type=str, default=None):
    """Get user input with validation"""
    while True:
        try:
            if default:
                user_input = input(f"{prompt} [{default}]: ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{prompt}: ").strip()
            
            if not user_input and input_type != str:
                print("❌ This field is required.")
                continue
                
            if input_type == bool:
                return user_input.lower() in ['y', 'yes', 'true', '1']
            elif input_type == int:
                return int(user_input)
            else:
                return user_input
                
        except ValueError:
            print(f"❌ Please enter a valid {input_type.__name__}.")
        except KeyboardInterrupt:
            print("\n\n❌ Setup cancelled.")
            sys.exit(0)

def setup_football_data_org(config):
    """Setup Football-Data.org API"""
    print("\n🔧 FOOTBALL-DATA.ORG SETUP")
    print("-" * 30)
    
    api_key = get_user_input("Enter your Football-Data.org API key")
    
    if api_key and api_key != "PLACEHOLDER_KEY":
        config.set_api_key("football_data_org", api_key)
        print("✅ Football-Data.org API key configured")
        return True
    else:
        print("⚠️  Football-Data.org API key not set")
        return False

def setup_api_football(config):
    """Setup API-Football via RapidAPI"""
    print("\n🔧 API-FOOTBALL SETUP")
    print("-" * 25)
    
    api_key = get_user_input("Enter your RapidAPI key for API-Football")
    
    if api_key and api_key != "PLACEHOLDER_KEY":
        config.set_api_key("api_football", api_key)
        print("✅ API-Football API key configured")
        return True
    else:
        print("⚠️  API-Football API key not set")
        return False

def setup_data_sources(config):
    """Configure data source priorities"""
    print("\n🔧 DATA SOURCE PRIORITY SETUP")
    print("-" * 35)
    
    available_sources = config.get_available_sources()
    
    if not available_sources:
        print("❌ No API keys configured. Please set up at least one API key first.")
        return False
    
    print(f"\nAvailable sources: {', '.join(available_sources)}")
    
    if len(available_sources) == 1:
        primary = available_sources[0]
        config.set_data_sources(primary=primary)
        print(f"✅ Using {primary} as primary data source")
        return True
    
    print("\nSelect primary data source:")
    for i, source in enumerate(available_sources, 1):
        print(f"  {i}. {source}")
    
    choice = get_user_input("Enter choice number", int)
    
    if 1 <= choice <= len(available_sources):
        primary = available_sources[choice - 1]
        
        # Set fallback
        fallback_options = [s for s in available_sources if s != primary]
        if fallback_options:
            fallback = fallback_options[0]
        else:
            fallback = None
        
        config.set_data_sources(primary=primary, fallback=fallback)
        print(f"✅ Primary: {primary}")
        if fallback:
            print(f"✅ Fallback: {fallback}")
        
        return True
    else:
        print("❌ Invalid choice")
        return False

def setup_leagues(config):
    """Configure enabled leagues"""
    print("\n🔧 LEAGUE CONFIGURATION")
    print("-" * 30)
    
    default_leagues = [39, 140, 78, 61, 135, 2, 3]  # PL, La Liga, Bundesliga, Serie A, Ligue 1, CL, EL
    
    print("\nDefault enabled leagues:")
    league_names = {
        39: "Premier League (England)",
        140: "La Liga (Spain)", 
        78: "Bundesliga (Germany)",
        61: "Serie A (Italy)",
        135: "Ligue 1 (France)",
        2: "Champions League",
        3: "Europa League"
    }
    
    for league_id in default_leagues:
        name = league_names.get(league_id, f"League {league_id}")
        print(f"  {league_id}: {name}")
    
    use_default = get_user_input("Use default leagues?", bool, default=True)
    
    if use_default:
        config.set_enabled_leagues(default_leagues)
        print("✅ Default leagues configured")
        return True
    else:
        print("Enter league IDs (comma-separated, e.g., 39,140,78):")
        leagues_input = input("Leagues: ").strip()
        
        try:
            leagues = [int(x.strip()) for x in leagues_input.split(',') if x.strip()]
            if leagues:
                config.set_enabled_leagues(leagues)
                print(f"✅ Configured leagues: {leagues}")
                return True
            else:
                print("❌ No valid leagues entered")
                return False
        except ValueError:
            print("❌ Invalid league IDs")
            return False

def setup_sync_settings(config):
    """Configure sync settings"""
    print("\n🔧 SYNC SETTINGS")
    print("-" * 20)
    
    use_historical = get_user_input("Use historical data from Open Goal DB?", bool, default=True)
    
    cooldown_hours = get_user_input("Sync cooldown (hours)", int, default=12)
    
    # Update config
    config.config["sync_settings"]["use_historical_data"] = use_historical
    config.config["sync_settings"]["cooldown_seconds"] = cooldown_hours * 3600
    
    config.save_config()
    
    print(f"✅ Historical data: {'Enabled' if use_historical else 'Disabled'}")
    print(f"✅ Sync cooldown: {cooldown_hours} hours")
    
    return True

def test_configuration():
    """Test the configuration"""
    print("\n🧪 TESTING CONFIGURATION")
    print("-" * 30)
    
    try:
        engine = MultiSourceSyncEngine()
        engine.print_status()
        
        # Test API connections
        print("\nTesting API connections...")
        
        if engine.football_data_org:
            print("  🔄 Testing Football-Data.org...")
            try:
                competitions = engine.football_data_org.fetch_competitions()
                if competitions:
                    print("  ✅ Football-Data.org: Connected")
                else:
                    print("  ❌ Football-Data.org: Failed to fetch data")
            except Exception as e:
                print(f"  ❌ Football-Data.org: {e}")
        
        if engine.api_football:
            print("  🔄 Testing API-Football...")
            try:
                leagues = engine.api_football.fetch_leagues()
                if leagues:
                    print("  ✅ API-Football: Connected")
                else:
                    print("  ❌ API-Football: Failed to fetch data")
            except Exception as e:
                print(f"  ❌ API-Football: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Main setup function"""
    print_banner()
    print_api_instructions()
    
    # Initialize config
    config = ConfigManager()
    
    # Setup steps
    steps = [
        ("API Keys", lambda: setup_football_data_org(config) or setup_api_football(config)),
        ("Data Sources", lambda: setup_data_sources(config)),
        ("Leagues", lambda: setup_leagues(config)),
        ("Sync Settings", lambda: setup_sync_settings(config)),
        ("Test Configuration", lambda: test_configuration()),
    ]
    
    completed_steps = []
    
    for step_name, step_func in steps:
        print(f"\n📋 STEP: {step_name}")
        print("=" * 40)
        
        try:
            if step_func():
                completed_steps.append(step_name)
                print(f"✅ {step_name} completed successfully")
            else:
                print(f"⚠️  {step_name} completed with warnings")
                completed_steps.append(f"{step_name} (warnings)")
        except KeyboardInterrupt:
            print(f"\n❌ Setup interrupted during {step_name}")
            break
        except Exception as e:
            print(f"❌ Error in {step_name}: {e}")
            break
        
        # Ask to continue
        if step_name != steps[-1][0]:  # Not the last step
            continue_setup = get_user_input("\nContinue to next step?", bool, default=True)
            if not continue_setup:
                break
    
    # Save configuration to database
    try:
        config.store_to_db()
        print("\n✅ Configuration saved to database")
    except Exception as e:
        print(f"\n⚠️  Failed to save to database: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 SETUP SUMMARY")
    print("=" * 60)
    
    print(f"\nCompleted steps: {len(completed_steps)}/{len(steps)}")
    for step in completed_steps:
        print(f"  ✅ {step}")
    
    print("\n📚 NEXT STEPS:")
    print("1. Run: python main.py --force (to test sync)")
    print("2. Run: python main.py (normal sync)")
    print("3. Use: python main.py --legacy (fallback mode)")
    print("4. Use: python main.py --setup (reconfigure)")
    
    print(f"\n📁 Configuration file: {config.config_file}")
    print(f"🗄️  Database: {config.db.db_path}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
