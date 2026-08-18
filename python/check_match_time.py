#!/usr/bin/env python3
"""
Check the current time in database for Ukraine vs Poland match
"""
from database import LogicBetDB

db = LogicBetDB()

with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Find Ukraine vs Poland match
    cursor.execute("""
        SELECT m.id, m.date, t1.name as home, t2.name as away, m.league
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE t1.name = 'Ukraine' AND t2.name = 'Poland'
    """)
    
    match = cursor.fetchone()
    
    if match:
        match_id, date_utc, home, away, league = match
        print(f"Match ID: {match_id}")
        print(f"Teams: {home} vs {away}")
        print(f"League: {league}")
        print(f"UTC time in DB: {date_utc}")
        
        # Convert to Ukrainian time
        from datetime import datetime, timedelta
        dt_utc = datetime.fromisoformat(date_utc.replace('Z', '+00:00'))
        dt_ua = dt_utc + timedelta(hours=3)  # UTC+3 for May (daylight saving)
        print(f"Ukrainian time: {dt_ua.strftime('%Y-%m-%d %H:%M')}")
        
        print("\nExpected: 18:30 Kyiv time (15:30 UTC)")
        print(f"Actual: {dt_ua.strftime('%H:%M')} Kyiv time ({dt_utc.strftime('%H:%M')} UTC)")
        
        if dt_ua.hour == 18 and dt_ua.minute == 30:
            print("\n✅ Time is CORRECT!")
        else:
            print("\n❌ Time is INCORRECT!")
    else:
        print("Match not found")
