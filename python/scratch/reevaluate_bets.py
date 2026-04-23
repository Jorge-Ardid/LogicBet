import sqlite3
import os

DB_PATH = r"c:\Users\jvjor\OneDrive\Рабочий стол\Yuri\Footboll\godot_app\logicbet.db"

def reevaluate_all():
    if not os.path.exists(DB_PATH):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Reset is_hit to NULL to force re-evaluation
    cursor.execute("UPDATE predictions SET is_hit = NULL")
    conn.commit()
    
    # Import the evaluation logic (we copy it here for simplicity)
    query = """
        SELECT p.id, p.selection, m.home_score, m.away_score 
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        WHERE m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
    """
    preds = cursor.execute(query).fetchall()
    
    print(f"--- RE-EVALUATING {len(preds)} PREDICTIONS ---")
    
    hits = 0
    for p_id, sel, hs, as_t in preds:
        if hs is None or as_t is None: continue
        is_hit = 0
        s = sel.upper()
        
        if "П1" in s or "HOME" in s: is_hit = 1 if hs > as_t else 0
        elif "П2" in s or "AWAY" in s: is_hit = 1 if as_t > hs else 0
        elif "НІЧИЯ" in s or s == "DRAW" or " X" in s: is_hit = 1 if hs == as_t else 0
        elif "1X" in s or "1 X" in s: is_hit = 1 if hs >= as_t else 0
        elif "X2" in s or "X 2" in s: is_hit = 1 if as_t >= hs else 0
        elif "БІЛЬШЕ" in s or "OVER" in s or "ТБ" in s:
            threshold = 2.5
            if "1.5" in s: threshold = 1.5
            elif "3.5" in s: threshold = 3.5
            elif "8.5" in s: threshold = 8.5
            is_hit = 1 if (hs + as_t) > threshold else 0
        elif "МЕНШЕ" in s or "UNDER" in s or "ТМ" in s:
            threshold = 2.5
            if "1.5" in s: threshold = 1.5
            is_hit = 1 if (hs + as_t) < threshold else 0
            
        cursor.execute("UPDATE predictions SET is_hit = ? WHERE id = ?", (is_hit, p_id))
        if is_hit: hits += 1
        
    conn.commit()
    print(f"Evaluation complete. Hits: {hits}/{len(preds)} ({(hits/len(preds))*100:.1f}%)")
    conn.close()

if __name__ == "__main__":
    reevaluate_all()
