from database import LogicBetDB
from analytics import BettingAnalytics

def test_logic():
    db = LogicBetDB()
    analytics = BettingAnalytics(db)
    
    print("--- TESTING AI ACCURACY LOGIC ---")
    
    # 1. Fetch some finished matches to test
    with db.get_connection() as conn:
        matches = conn.execute("""
            SELECT m.id, t1.name, t2.name, m.home_score, m.away_score, t1.id, t2.id
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            WHERE m.status IN ('FT', 'FINISHED')
            LIMIT 5
        """).fetchall()
        
    if not matches:
        print("No matches found in DB to test.")
        return

    for m in matches:
        m_id, h_name, a_name, h_s, a_s, h_id, a_id = m
        print(f"\nMatch: {h_name} vs {a_name} (Result: {h_s}:{a_s})")
        
        # Test prediction logic
        preds = analytics.determine_predictions(m_id, h_id, a_id, None)
        for p in preds:
            print(f"  > Market: {p['market']} | Selection: {p['selection']} | Prob: {p['calculated_prob']:.1%}")
            print(f"    Algo Meta: {p['algorithm']}")
            
            # Simple check if "hit"
            hit = "???"
            s = p['selection'].upper()
            if "П1" in s or "HOME" in s: hit = "✅" if h_s > a_s else "❌"
            elif "П2" in s or "AWAY" in s: hit = "✅" if a_s > h_s else "❌"
            elif "X" in s or "DRAW" in s: hit = "✅" if h_s == a_s else "❌"
            print(f"    Status: {hit}")

if __name__ == "__main__":
    test_logic()
