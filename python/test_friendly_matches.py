#!/usr/bin/env python3
"""
Test script to check if API returns friendly matches
"""
from api_client import APIFootballClient
from datetime import datetime

client = APIFootballClient('72afa426ab5fb0a7c964261b8b25f977')

today = datetime.now().strftime("%Y-%m-%d")
print(f"Testing friendly matches for: {today}")
print("=" * 50)

# Test friendly matches league (528)
fixtures = client.fetch_fixtures(date=today, league_id=528)
print(f"Found {len(fixtures)} friendly matches from API")

if fixtures:
    print("\nFriendly matches:")
    for f in fixtures[:10]:
        home = f['teams']['home']['name']
        away = f['teams']['away']['name']
        print(f"  {home} vs {away}")
else:
    print("No friendly matches found with league_id=528")

# Try without league_id to see all matches today
print("\n" + "=" * 50)
print("Testing all matches today (no league filter):")
all_fixtures = client.fetch_fixtures(date=today)
print(f"Found {len(all_fixtures)} total matches today")

if all_fixtures:
    print("\nAll matches today:")
    for f in all_fixtures[:15]:
        home = f['teams']['home']['name']
        away = f['teams']['away']['name']
        league = f['league']['name']
        print(f"  {home} vs {away} ({league})")
