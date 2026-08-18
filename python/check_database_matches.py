#!/usr/bin/env python3
"""
Check what matches exist in the database
"""
from database import LogicBetDB
from datetime import datetime

db = LogicBetDB()

with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check total matches
    cursor.execute("SELECT COUNT(*) FROM matches")
    total = cursor.fetchone()[0]
    print(f"Total matches in database: {total}")
    
    # Check matches by league
    cursor.execute("SELECT league, COUNT(*) as count FROM matches GROUP BY league ORDER BY count DESC")
    print("\nMatches by league:")
    for row in cursor.fetchall():
        print(f"  {row[0] or 'Unknown'}: {row[1]}")
    
    # Check recent matches
    cursor.execute("SELECT date, home_team_id, away_team_id, league FROM matches ORDER BY date DESC LIMIT 10")
    print("\nRecent matches:")
    for row in cursor.fetchall():
        # Get team names
        cursor.execute("SELECT name FROM teams WHERE id = ?", (row[1],))
        home = cursor.fetchone()
        cursor.execute("SELECT name FROM teams WHERE id = ?", (row[2],))
        away = cursor.fetchone()
        print(f"  {row[0]}: {home[0] if home else 'Unknown'} vs {away[0] if away else 'Unknown'} ({row[3]})")
    
    # Check for international/friendly leagues
    cursor.execute("SELECT DISTINCT league FROM matches WHERE league LIKE '%World%' OR league LIKE '%Euro%' OR league LIKE '%Friendly%' OR league LIKE '%International%'")
    print("\nInternational leagues in database:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}")
