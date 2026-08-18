#!/usr/bin/env python3
"""
Update friendly match times to correct Ukrainian timezone
"""
from database import LogicBetDB
from datetime import datetime, timedelta

db = LogicBetDB()

# Ukrainian timezone (UTC+3 during daylight saving in May)
def get_ukrainian_time(year, month, day, hour, minute=0):
    """Convert Ukrainian local time to UTC for storage"""
    utc_offset = 3  # UTC+3 during daylight saving
    dt_ua = datetime(year, month, day, hour, minute)
    dt_utc = dt_ua - timedelta(hours=utc_offset)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

# Update Ukraine vs Poland match time to 18:30 Kyiv time
correct_time = get_ukrainian_time(2026, 5, 31, 18, 30)

print(f"Updating Ukraine vs Poland match time to: 18:30 Kyiv (UTC: {correct_time})")
print("=" * 50)

with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Find the Ukraine vs Poland match
    cursor.execute("""
        SELECT id, home_team_id, away_team_id, date 
        FROM matches 
        WHERE id IN (SELECT id FROM matches WHERE home_team_id = (SELECT id FROM teams WHERE name = 'Ukraine') 
                     AND away_team_id = (SELECT id FROM teams WHERE name = 'Poland'))
    """)
    
    match = cursor.fetchone()
    
    if match:
        match_id, home_id, away_id, old_date = match
        print(f"Found match ID: {match_id}")
        print(f"Old time: {old_date}")
        print(f"New time: {correct_time}")
        
        # Update the match time
        cursor.execute("""
            UPDATE matches 
            SET date = ? 
            WHERE id = ?
        """, (correct_time, match_id))
        
        conn.commit()
        print("Match time updated successfully!")
    else:
        print("Match not found. Adding new match...")
        
        # Add the match with correct time
        home_id = db.add_team_if_not_exists("Ukraine")
        away_id = db.add_team_if_not_exists("Poland")
        
        match_id = db.insert_match(
            remote_id=None,
            date=correct_time,
            league="Friendly Match",
            league_id=528,
            home_id=home_id,
            away_id=away_id,
            h_score=None,
            a_score=None,
            status='SCHEDULED'
        )
        
        print(f"Match added with ID: {match_id}")

print("\n" + "=" * 50)
print("Time conversion: Ukrainian time (UTC+3) -> UTC for storage")
print("18:30 Kyiv = 15:30 UTC")
