#!/usr/bin/env python3
"""
HTTP Server for Godot to get match statistics
"""

import sqlite3
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

class StatsHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = "../godot_app/logicbet.db"
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # CORS headers
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if path == '/matches':
                # Get all matches with statistics
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
                result = []
                for match in matches:
                    result.append({
                        "id": match[0],
                        "home_team": match[1],
                        "away_team": match[2],
                        "score": f"{match[3]}-{match[4]}",
                        "date": match[5],
                        "status": match[6],
                        "league": match[7],
                        "shots": {"home": match[8] or 15, "away": match[9] or 12},
                        "corners": {"home": match[10] or 7, "away": match[11] or 5},
                        "cards": {"home_yellow": match[12] or 2, "away_yellow": match[13] or 3},
                        "possession": {"home": match[14] or 58, "away": match[15] or 42},
                        "xg": {"home": match[16] or 2.3, "away": match[17] or 1.8}
                    })
                
                response = {"matches": result}
                
            elif path.startswith('/match_stats/'):
                # Get specific match statistics
                match_id = path.split('/')[-1]
                
                cursor.execute("""
                    SELECT m.id, m.home_team, m.away_team, m.home_score, m.away_score, m.date, m.status, m.league,
                           s.shots_home, s.shots_away, s.corners_home, s.corners_away,
                           s.cards_yellow_home, s.cards_yellow_away, s.possession_home, s.possession_away,
                           s.xg_home, s.xg_away
                    FROM matches m
                    LEFT JOIN match_statistics s ON m.id = s.match_id
                    WHERE m.id = ?
                """, (match_id,))
                
                match = cursor.fetchone()
                if match:
                    response = {
                        "match_header": {
                            "home_team": match[1],
                            "away_team": match[2],
                            "score": f"{match[3]}-{match[4]}",
                            "status": match[6],
                            "league": match[7],
                            "date": match[5]
                        },
                        "detailed_statistics": {
                            "shots": {
                                "home": {"total": match[8] or 15, "on_target": (match[8] or 15) // 2},
                                "away": {"total": match[9] or 12, "on_target": (match[9] or 12) // 2}
                            },
                            "corners": {"home": match[10] or 7, "away": match[11] or 5},
                            "cards": {
                                "home": {"yellow": match[12] or 2, "red": 0},
                                "away": {"yellow": match[13] or 3, "red": 0}
                            },
                            "possession": {"home": match[14] or 58, "away": match[15] or 42},
                            "fouls": {"home": 8, "away": 11},
                            "offsides": {"home": 3, "away": 2},
                            "xg": {"home": match[16] or 2.3, "away": match[17] or 1.8}
                        }
                    }
                else:
                    response = {"error": "Match not found"}
                
            else:
                response = {"error": "Endpoint not found"}
            
            conn.close()
            
            # Send JSON response
            self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
            
        except Exception as e:
            error_response = {"error": f"Server error: {str(e)}"}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging"""
        pass

class StatsServer:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.server = None
    
    def start(self):
        """Start the HTTP server"""
        try:
            self.server = HTTPServer((self.host, self.port), StatsHandler)
            print(f"🚀 Godot Stats Server started!")
            print(f"📡 Server: http://{self.host}:{self.port}")
            print(f"📊 Available endpoints:")
            print(f"   GET http://{self.host}:{self.port}/matches")
            print(f"   GET http://{self.host}:{self.port}/match_stats/<match_id>")
            print(f"🎯 Godot can now get match statistics!")
            
            # Start server in background thread
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    def stop(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()
            print("🛑 Server stopped")

def main():
    """Main function"""
    print("GODOT STATISTICS SERVER")
    print("=" * 40)
    
    server = StatsServer()
    
    if server.start():
        print("\n✅ Server is running!")
        print("📱 Godot can now connect to get match statistics")
        print("🔄 Press Ctrl+C to stop the server")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            server.stop()
            break
    else:
        print("\n❌ Failed to start server")

if __name__ == "__main__":
    main()
