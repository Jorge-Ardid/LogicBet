import json
import os
import sqlite3
from datetime import datetime

class BlackboxArchive:
    """
    Чорна скриня (Blackbox Master Archive):
    Зберігає кожний підтверджений результат матчу та оцінку прогнозів у постійний
    архівний JSON-документ (data/blackbox_history_backup.json).
    
    Навіть якщо база даних створюється заново, або API не віддає матчі піврічної давності,
    чорна скриня автоматично відновлює повну історію рахунків і результатів.
    """
    def __init__(self, archive_path=None):
        if archive_path is None:
            self.archive_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/blackbox_history_backup.json"))
        else:
            self.archive_path = archive_path

    def load_archive(self):
        """Завантажує архів матчів з файлу"""
        if not os.path.exists(self.archive_path):
            return {"last_updated": datetime.now().isoformat(), "matches": {}}
        try:
            with open(self.archive_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "matches" not in data:
                    data["matches"] = {}
                return data
        except Exception as e:
            print(f"  [BLACKBOX] Error loading archive: {e}")
            return {"last_updated": datetime.now().isoformat(), "matches": {}}

    def save_archive(self, archive_data):
        """Зберігає архів матчів у файл"""
        try:
            os.makedirs(os.path.dirname(self.archive_path), exist_ok=True)
            archive_data["last_updated"] = datetime.now().isoformat()
            with open(self.archive_path, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, ensure_ascii=False, indent=2)
            print(f"  [BLACKBOX] ✅ Чорна скриня оновлена: {len(archive_data.get('matches', {}))} матчів збережено в {self.archive_path}")
            return True
        except Exception as e:
            print(f"  [BLACKBOX] ❌ Failed to save archive: {e}")
            return False

    def sync_to_blackbox(self, db):
        """
        Сканує базу даних і зберігає ВСІ зіграні матчі з реальним рахунком у чорну скриню.
        """
        print("\n[BLACKBOX] 📦 Збереження історії в чорну скриню...")
        archive = self.load_archive()
        matches_dict = archive.get("matches", {})
        
        saved_count = 0
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Вибираємо тільки матчі з РЕАЛЬНИМ рахунком
            query = """
                SELECT m.*, t1.name as home_name, t2.name as away_name
                FROM matches m
                JOIN teams t1 ON m.home_team_id = t1.id
                JOIN teams t2 ON m.away_team_id = t2.id
                WHERE m.home_score IS NOT NULL AND m.away_score IS NOT NULL
                  AND m.status IN ('FT', 'AET', 'PEN', 'FINISHED')
                ORDER BY m.date ASC
            """
            rows = cursor.execute(query).fetchall()
            
            for row in rows:
                m = dict(row)
                m_id = str(m["id"])
                
                # Fetch predictions for this match
                p_rows = cursor.execute("""
                    SELECT id, algorithm, market, selection, calculated_prob, bookmaker_odd, is_hit
                    FROM predictions
                    WHERE match_id = ?
                """, (m["id"],)).fetchall()
                
                preds = [dict(p) for p in p_rows]
                
                key = f"{m.get('remote_id') or m_id}_{m['home_name']}_{m['away_name']}_{m['date'][:10]}"
                
                matches_dict[key] = {
                    "db_id": m["id"],
                    "remote_id": m.get("remote_id"),
                    "date": m["date"],
                    "league": m["league"],
                    "league_id": m.get("league_id"),
                    "home_team": m["home_name"],
                    "away_team": m["away_name"],
                    "home_score": m["home_score"],
                    "away_score": m["away_score"],
                    "ht_score_h": m.get("ht_score_h"),
                    "ht_score_a": m.get("ht_score_a"),
                    "status": m["status"],
                    "corners_h": m.get("corners_h"),
                    "corners_a": m.get("corners_a"),
                    "yellow_cards_h": m.get("yellow_cards_h"),
                    "yellow_cards_a": m.get("yellow_cards_a"),
                    "red_cards_h": m.get("red_cards_h"),
                    "red_cards_a": m.get("red_cards_a"),
                    "xg_h": m.get("xg_h"),
                    "xg_a": m.get("xg_a"),
                    "predictions": preds
                }
                saved_count += 1

        archive["matches"] = matches_dict
        self.save_archive(archive)
        return saved_count

    def restore_from_blackbox(self, db):
        """
        Відновлює всі підтверджені матчі з чорної скрині в базу даних,
        якщо вони відсутні або мали NULL рахунок.
        """
        print("\n[BLACKBOX] 🔄 Відновлення історії з чорної скрині в базу даних...")
        archive = self.load_archive()
        matches_dict = archive.get("matches", {})
        
        if not matches_dict:
            print("  [BLACKBOX] Чорна скриня порожня або файл ще не створено.")
            return 0

        restored_count = 0
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            for key, m in matches_dict.items():
                if m.get("home_score") is None or m.get("away_score") is None:
                    continue
                
                h_name = db._normalize_name(m["home_team"])
                a_name = db._normalize_name(m["away_team"])
                
                # Direct team fetch/insert using same cursor to avoid locks
                cursor.execute("SELECT id FROM teams WHERE name = ?", (h_name,))
                h_row = cursor.fetchone()
                if h_row:
                    h_id = h_row[0]
                else:
                    cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (h_name,))
                    cursor.execute("SELECT id FROM teams WHERE name = ?", (h_name,))
                    h_id = cursor.fetchone()[0]
                    
                cursor.execute("SELECT id FROM teams WHERE name = ?", (a_name,))
                a_row = cursor.fetchone()
                if a_row:
                    a_id = a_row[0]
                else:
                    cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (a_name,))
                    cursor.execute("SELECT id FROM teams WHERE name = ?", (a_name,))
                    a_id = cursor.fetchone()[0]
                
                # Check if match already exists by remote_id or team/date
                existing = None
                if m.get("remote_id"):
                    cursor.execute("SELECT id, home_score, status FROM matches WHERE remote_id = ?", (m["remote_id"],))
                    existing = cursor.fetchone()
                
                if not existing:
                    cursor.execute("""
                        SELECT id, home_score, status FROM matches 
                        WHERE home_team_id = ? AND away_team_id = ? AND DATE(date) = DATE(?)
                    """, (h_id, a_id, m["date"]))
                    existing = cursor.fetchone()
                
                if existing:
                    # Update score if it was NULL
                    m_id, cur_score, cur_status = existing
                    if cur_score is None or cur_status not in ('FT', 'AET', 'PEN', 'FINISHED'):
                        cursor.execute("""
                            UPDATE matches 
                            SET home_score = ?, away_score = ?, status = ?, ht_score_h = ?, ht_score_a = ?
                            WHERE id = ?
                        """, (m["home_score"], m["away_score"], m["status"], m.get("ht_score_h"), m.get("ht_score_a"), m_id))
                        restored_count += 1
                else:
                    # Insert missing historical match
                    cursor.execute("""
                        INSERT INTO matches (remote_id, date, league, league_id, home_team_id, away_team_id, home_score, away_score, status, ht_score_h, ht_score_a)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        m.get("remote_id"), m["date"], m["league"], m.get("league_id"),
                        h_id, a_id, m["home_score"], m["away_score"], m["status"],
                        m.get("ht_score_h"), m.get("ht_score_a")
                    ))
                    m_id = cursor.lastrowid
                    restored_count += 1
                
                # Restore predictions (check to avoid duplicates)
                for p in m.get("predictions", []):
                    cursor.execute("""
                        SELECT id FROM predictions 
                        WHERE match_id = ? AND market = ? AND selection = ?
                    """, (m_id, p.get("market", ""), p.get("selection", "")))
                    p_existing = cursor.fetchone()
                    if p_existing:
                        if p.get("is_hit") is not None:
                            cursor.execute("UPDATE predictions SET is_hit = ? WHERE id = ?", (p.get("is_hit"), p_existing[0]))
                    else:
                        cursor.execute("""
                            INSERT INTO predictions (match_id, algorithm, market, selection, calculated_prob, bookmaker_odd, is_hit)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            m_id, p.get("algorithm", ""), p.get("market", ""),
                            p.get("selection", ""), p.get("calculated_prob", 0.0),
                            p.get("bookmaker_odd", 0.0), p.get("is_hit")
                        ))
                    
            conn.commit()
            
        print(f"  [BLACKBOX] ✅ Відновлено/оновлено {restored_count} матчів з чорної скрині.")
        return restored_count
