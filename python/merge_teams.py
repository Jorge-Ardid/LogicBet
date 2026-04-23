import sqlite3
import os
import sys

# Add current dir to path to import database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import LogicBetDB

def merge_teams(source_id, target_id):
    """Merges source_id team into target_id team."""
    db = LogicBetDB()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Get names for logging
        cursor.execute("SELECT name FROM teams WHERE id = ?", (source_id,))
        source_name = cursor.fetchone()
        cursor.execute("SELECT name FROM teams WHERE id = ?", (target_id,))
        target_name = cursor.fetchone()
        
        if not source_name or not target_name:
            print(f"Error: One of the IDs not found ({source_id} or {target_id})")
            return
            
        source_name = source_name[0]
        target_name = target_name[0]
        print(f"--- MERGING: {source_name} (ID:{source_id}) -> {target_name} (ID:{target_id}) ---")
        
        # 2. Update MATCHES: Home team
        cursor.execute("UPDATE matches SET home_team_id = ? WHERE home_team_id = ?", (target_id, source_id))
        h_count = cursor.rowcount
        
        # 3. Update MATCHES: Away team
        cursor.execute("UPDATE matches SET away_team_id = ? WHERE away_team_id = ?", (target_id, source_id))
        a_count = cursor.rowcount
        
        print(f"  [MATCHES] Updated {h_count} home and {a_count} away matches.")
        
        # 4. Create SYNONYM for the target team
        cursor.execute("INSERT OR IGNORE INTO team_synonyms (team_id, synonym) VALUES (?, ?)", (target_id, source_name))
        print(f"  [SYNONYMS] Added '{source_name}' as synonym for '{target_name}'.")
        
        # 5. TODO: Optionally merge/recalculate Elo if needed. 
        # For now, we keep the target's Elo.
        
        # 6. DELETE the source team
        cursor.execute("DELETE FROM teams WHERE id = ?", (source_id,))
        print(f"  [TEAMS] Remnants of {source_name} removed.")
        
        conn.commit()
        print(f"✅ SUCCESSFULLY MERGED {source_name} INTO {target_name}!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ FAILED TO MERGE: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Merge two teams in LogicBet DB")
    parser.add_argument("source", type=int, help="ID of the team to BE REMOVED (source)")
    parser.add_argument("target", type=int, help="ID of the team to KEEP (target)")
    
    args = parser.parse_args()
    merge_teams(args.source, args.target)
