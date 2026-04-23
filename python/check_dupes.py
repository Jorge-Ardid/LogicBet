"""Check if Atletico vs Barcelona entries are duplicates or different competitions."""
import sqlite3

db_path = "../godot_app/logicbet.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find all matches involving Atletico and Barcelona
cursor.execute("""
    SELECT m.id, m.remote_id, m.date, m.league, m.league_id, m.status,
           m.home_score, m.away_score,
           t1.name as home_team, t1.id as home_id,
           t2.name as away_team, t2.id as away_id
    FROM matches m
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    WHERE (t1.name LIKE '%tletico%' OR t1.name LIKE '%tletico%' OR t1.name LIKE '%Atletico%')
       OR (t2.name LIKE '%arcelona%' OR t2.name LIKE '%Barça%')
    ORDER BY m.date DESC
""")

matches = cursor.fetchall()
print(f"\n=== MATCHES INVOLVING ATLETICO / BARCELONA ({len(matches)} found) ===\n")
for m in matches:
    print(f"  Match ID: {m[0]}")
    print(f"  Remote ID: {m[1]}")
    print(f"  Date: {m[2]}")
    print(f"  League: {m[3]} (ID: {m[4]})")
    print(f"  Status: {m[5]}")
    print(f"  Score: {m[6]}-{m[7]}")
    print(f"  Home: {m[8]} (team_id={m[9]})")
    print(f"  Away: {m[10]} (team_id={m[11]})")
    print(f"  ---")

# Also check for duplicate team entries
print("\n=== ALL TEAMS WITH 'ATLETI' or 'BARCE' IN NAME ===")
cursor.execute("SELECT id, name, elo_rating FROM teams WHERE name LIKE '%tleti%' OR name LIKE '%arcel%' OR name LIKE '%arça%'")
for t in cursor.fetchall():
    print(f"  ID={t[0]}: '{t[1]}' (ELO: {t[2]:.0f})")

conn.close()
