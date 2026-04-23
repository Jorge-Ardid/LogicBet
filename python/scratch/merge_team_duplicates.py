import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def clean_name(name):
    if not name: return ""
    n = name.strip()
    n = n.replace(".", "").replace("ö", "o").replace("ü", "u").replace("ä", "a").replace("á", "a").replace("é", "e")
    
    prefixes = ["1 ", "AFC ", "FC ", "AC ", "SC ", "RC ", "SS ", "SSC ", "US ", "AS ", "LOSC ", "VfL ", "VfB ", "RCD ", "UD ", "SV ", "Werder "]
    for p in prefixes:
        if n.upper().startswith(p.upper()): n = n[len(p):].strip()
    
    suffixes = [" FC", " CF", " AFC", " SC", " AC", " BC", " FK", " SK", " 04", " 05", " 1909", " 1910", " 1846", " 29", " 63"]
    for s in suffixes:
        if n.upper().endswith(s.upper()): n = n[:-len(s)].strip()
    return n.upper()

def merge_teams():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name FROM teams")
    teams = cursor.fetchall()
    
    cleaned_map = {} # clean_name -> [list of IDs]
    for t_id, t_name in teams:
        c = clean_name(t_name)
        if c not in cleaned_map: cleaned_map[c] = []
        cleaned_map[c].append((t_id, t_name))
        
    merged_count = 0
    for c_name, matches in cleaned_map.items():
        if len(matches) > 1:
            # Keep the one with the shortest name or first one
            matches.sort(key=lambda x: len(x[1]))
            keep_id, keep_name = matches[0]
            to_remove = matches[1:]
            
            print(f"Merging into '{keep_name}' ({keep_id}): {[m[1] for m in to_remove]}")
            
            for rem_id, rem_name in to_remove:
                # Update matches
                cursor.execute("UPDATE matches SET home_team_id = ? WHERE home_team_id = ?", (keep_id, rem_id))
                cursor.execute("UPDATE matches SET away_team_id = ? WHERE away_team_id = ?", (keep_id, rem_id))
                # Update predictions (if match_id isn't enough, but usually it is)
                # Delete duplicate team
                cursor.execute("DELETE FROM teams WHERE id = ?", (rem_id,))
                merged_count += 1
                
    conn.commit()
    print(f"Finished. Merged {merged_count} teams.")
    conn.close()

if __name__ == "__main__":
    merge_teams()
