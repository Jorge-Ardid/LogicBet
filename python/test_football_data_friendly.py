#!/usr/bin/env python3
"""
Test script to check if Football-Data.org API returns friendly matches
"""
from football_data_client import FootballDataClient
from datetime import datetime, timedelta

client = FootballDataClient('72cd4a1c41ff402eba0da37f4bbc5ff6')

today = datetime.now().strftime("%Y-%m-%d")
print(f"Testing Football-Data.org for matches: {today}")
print("=" * 50)

# Try to get all matches today (this includes international friendlies)
matches = client.fetch_all_matches_batch(today, today)
print(f"Requests remaining: {client.get_limit_left()}")

if matches and 'matches' in matches:
    print(f"Found {len(matches['matches'])} total matches")
    
    # Filter for international matches
    international_matches = []
    for match in matches['matches']:
        comp = match.get('competition', {})
        comp_name = comp.get('name', '').lower()
        comp_code = comp.get('code', '')
        
        # Check if it's an international competition
        if any(keyword in comp_name for keyword in ['world cup', 'euro', 'nations', 'friendly', 'international']):
            international_matches.append(match)
    
    print(f"\nInternational matches found: {len(international_matches)}")
    
    if international_matches:
        print("\nInternational matches:")
        for m in international_matches[:10]:
            home = m['homeTeam']['name']
            away = m['awayTeam']['name']
            comp = m['competition']['name']
            print(f"  {home} vs {away} ({comp})")
    else:
        print("\nNo international matches found")
        print("\nAll competitions in today's matches:")
        comps = set()
        for match in matches['matches']:
            comp = match.get('competition', {})
            comps.add(f"{comp.get('name', 'Unknown')} ({comp.get('code', 'N/A')})")
        for c in sorted(comps):
            print(f"  - {c}")
else:
    print("No matches found")
