#!/usr/bin/env python3
"""
Manually add international friendly matches to the database
This is a temporary solution since API-Football account is suspended
"""
from database import LogicBetDB
from datetime import datetime, timezone, timedelta

db = LogicBetDB()

# Ukrainian timezone (UTC+2 standard, UTC+3 daylight)
# May 31, 2026 is during daylight saving time (last Sunday of March to last Sunday of October)
# So Ukraine is UTC+3
def get_ukrainian_time(year, month, day, hour, minute=0):
    """Convert Ukrainian local time to UTC for storage"""
    # Check if it's daylight saving time (last Sunday of March to last Sunday of October)
    # For simplicity, we'll use UTC+3 for May (daylight saving)
    utc_offset = 3  # UTC+3 during daylight saving
    dt_ua = datetime(year, month, day, hour, minute)
    dt_utc = dt_ua - timedelta(hours=utc_offset)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

# Sample friendly matches for today (2026-05-31)
# Times are in Ukrainian local time
friendly_matches = [
    {
        "home": "Ukraine",
        "away": "Poland",
        "date": get_ukrainian_time(2026, 5, 31, 18, 30),  # 18:30 Kyiv time
        "league": "Friendly Match"
    },
    {
        "home": "England",
        "away": "Germany",
        "date": get_ukrainian_time(2026, 5, 31, 15, 00),  # 15:00 Kyiv time
        "league": "Friendly Match"
    },
    {
        "home": "France",
        "away": "Spain",
        "date": get_ukrainian_time(2026, 5, 31, 20, 00),  # 20:00 Kyiv time
        "league": "Friendly Match"
    },
    {
        "home": "Italy",
        "away": "Netherlands",
        "date": get_ukrainian_time(2026, 5, 31, 17, 00),  # 17:00 Kyiv time
        "league": "Friendly Match"
    },
    {
        "home": "Brazil",
        "away": "Argentina",
        "date": get_ukrainian_time(2026, 5, 31, 19, 00),  # 19:00 Kyiv time
        "league": "Friendly Match"
    }
]

print("Adding friendly matches to database...")
print("=" * 50)

for match in friendly_matches:
    home_team = match["home"]
    away_team = match["away"]
    date = match["date"]
    league = match["league"]
    
    # Get or create team IDs
    home_id = db.add_team_if_not_exists(home_team)
    away_id = db.add_team_if_not_exists(away_team)
    
    # Insert match
    match_id = db.insert_match(
        remote_id=None,  # No API ID for manual matches
        date=date,
        league=league,
        league_id=528,  # Friendly matches league ID
        home_id=home_id,
        away_id=away_id,
        h_score=None,
        a_score=None,
        status='SCHEDULED'
    )
    
    print(f"Added: {home_team} vs {away_team} (ID: {match_id})")

print("\n" + "=" * 50)
print("Friendly matches added successfully!")
print("Note: These are sample matches. Replace with actual friendly matches.")
print("\nIMPORTANT: Your API-Football account is suspended.")
print("Please check https://dashboard.api-football.com to reactivate it.")
