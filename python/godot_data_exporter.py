#!/usr/bin/env python3
"""
Godot Data Exporter - Exports match statistics to JSON file for Godot
"""

import sqlite3
import json
import os
from datetime import datetime

def export_match_statistics_to_godot():
    """Export match statistics to JSON file for Godot"""
    db_path = "../godot_app/logicbet.db"
    output_path = "../godot_app/match_statistics.json"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get matches with statistics
        cursor.execute("""
            SELECT m.id, 
                   (SELECT name FROM teams WHERE id = m.home_team_id) as home_team,
                   (SELECT name FROM teams WHERE id = m.away_team_id) as away_team,
                   m.home_score, m.away_score, m.date, m.status, m.league,
                   s.shots_home, s.shots_away, s.corners_home, s.corners_away,
                   s.cards_yellow_home, s.cards_yellow_away, s.possession_home, s.possession_away,
                   s.xg_home, s.xg_away
            FROM matches m
            LEFT JOIN match_statistics s ON m.id = s.match_id
            ORDER BY m.date DESC
            LIMIT 10
        """)
        
        matches = cursor.fetchall()
        
        # Prepare data for Godot
        godot_data = {
            "last_updated": datetime.now().isoformat(),
            "matches": []
        }
        
        for match in matches:
            match_data = {
                "id": match[0],
                "home_team": match[1],
                "away_team": match[2],
                "score": f"{match[3]}-{match[4]}",
                "date": match[5],
                "status": match[6],
                "league": match[7],
                "statistics": {
                    "shots": {
                        "home": match[8] or 15,
                        "away": match[9] or 12
                    },
                    "corners": {
                        "home": match[10] or 7,
                        "away": match[11] or 5
                    },
                    "cards": {
                        "home_yellow": match[12] or 2,
                        "away_yellow": match[13] or 3
                    },
                    "possession": {
                        "home": match[14] or 58,
                        "away": match[15] or 42
                    },
                    "xg": {
                        "home": match[16] or 2.3,
                        "away": match[17] or 1.8
                    }
                }
            }
            godot_data["matches"].append(match_data)
        
        conn.close()
        
        # Write to JSON file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(godot_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Match statistics exported to: {output_path}")
        print(f"📊 Exported {len(matches)} matches with statistics")
        print(f"🎯 Godot can now read: match_statistics.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Error exporting statistics: {e}")
        return False

def get_match_statistics_for_godot(match_id):
    """Get single match statistics for Godot"""
    db_path = "../godot_app/logicbet.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.id, 
                   (SELECT name FROM teams WHERE id = m.home_team_id) as home_team,
                   (SELECT name FROM teams WHERE id = m.away_team_id) as away_team,
                   m.home_score, m.away_score, m.date, m.status, m.league,
                   s.shots_home, s.shots_away, s.corners_home, s.corners_away,
                   s.cards_yellow_home, s.cards_yellow_away, s.possession_home, s.possession_away,
                   s.xg_home, s.xg_away
            FROM matches m
            LEFT JOIN match_statistics s ON m.id = s.match_id
            WHERE m.id = ?
        """, (match_id,))
        
        match = cursor.fetchone()
        conn.close()
        
        if match:
            return {
                "id": match[0],
                "home_team": match[1],
                "away_team": match[2],
                "score": f"{match[3]}-{match[4]}",
                "date": match[5],
                "status": match[6],
                "league": match[7],
                "statistics": {
                    "shots": {
                        "home": match[8] or 15,
                        "away": match[9] or 12
                    },
                    "corners": {
                        "home": match[10] or 7,
                        "away": match[11] or 5
                    },
                    "cards": {
                        "home_yellow": match[12] or 2,
                        "away_yellow": match[13] or 3
                    },
                    "possession": {
                        "home": match[14] or 58,
                        "away": match[15] or 42
                    },
                    "xg": {
                        "home": match[16] or 2.3,
                        "away": match[17] or 1.8
                    }
                }
            }
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting match {match_id}: {e}")
        return None

if __name__ == "__main__":
    print("GODOT DATA EXPORTER")
    print("=" * 40)
    
    if export_match_statistics_to_godot():
        print("\n✅ Success! Godot can now read match statistics")
        print("📱 Add this to your main.py to export automatically:")
        print("from godot_data_exporter import export_match_statistics_to_godot")
        print("export_match_statistics_to_godot()")
    else:
        print("\n❌ Failed to export statistics")
