extends Node
class_name LogicBetDBViewer

# Godot-SQLite Addon is required.
var db = null
var db_path := "res://logicbet.db" 

func _ready() -> void:
	db = SQLite.new()
	# We use globalize_path to make sure the plugin sees the absolute Windows path
	var full_path = ProjectSettings.globalize_path(db_path)
	
	# Ensure directory exists
	var dir = DirAccess.open("res://")
	if not dir.dir_exists(db_path.get_base_dir()):
		dir.make_dir_recursive(db_path.get_base_dir())
		
	db.path = full_path
	
	if db.open_db():
		print("LogicBet: Connected to DB at: ", full_path)
	else:
		print("LogicBet ERROR: Could not open DB at: ", full_path)

func fetch_predictions() -> Array:
	if not db: 
		print("LogicBet ERROR: DB is null")
		return []
	
	var sql = """
		SELECT 
			m.id as match_id,
			m.home_team_id,
			m.away_team_id,
			t1.name as home_name, 
			t2.name as away_name, 
			'MULTI-MARKET' as algorithm,
			GROUP_CONCAT(p.selection, ' / ') as selection, 
			GROUP_CONCAT(p.calculated_prob, '|') as probabilities, 
			AVG(p.calculated_prob) as avg_prob, 
			MAX(p.bookmaker_odd) as bookmaker_odd, 
			m.league,
			m.date,
			m.status,
			m.home_score,
			m.away_score,
			t1.current_form as form_home,
			t2.current_form as form_away,
			t1.elo_rating as h_elo_live,
			t2.elo_rating as a_elo_live,
			t1.current_form as h_form_live,
			t2.current_form as a_form_live
		FROM matches m
		LEFT JOIN predictions p ON p.match_id = m.id
		JOIN teams t1 ON m.home_team_id = t1.id
		JOIN teams t2 ON m.away_team_id = t2.id
		WHERE m.status IN ('NS', 'TIMED', 'SCHEDULED') AND m.date > datetime('now', '-4 hours')
		GROUP BY m.id
		ORDER BY m.date ASC
		LIMIT 100
	"""
	
	if db.query(sql):
		return db.query_result
	else:
		print("LogicBet SQL ERROR: ", db.error_message)
		return []

func get_ai_stats() -> Dictionary:
	if not db: return {"total": 0, "hits": 0, "acc": 0.0}
	db.query("SELECT COUNT(*) as t, SUM(is_hit) as h FROM predictions WHERE is_hit IS NOT NULL")
	if db.query_result and db.query_result.size() > 0:
		var r = db.query_result[0]
		var total = int(r["t"]) if r["t"] else 0
		var hits = int(r["h"]) if r["h"] else 0
		if total > 0: return {"total": total, "hits": hits, "acc": float(hits)/float(total) * 100.0}
	return {"total": 0, "hits": 0, "acc": 0.0}

func fetch_teams_data() -> Dictionary:
	if not db: return {}
	
	db.query("SELECT * FROM teams")
	var results = db.query_result
	var teams_map = {}
	
	for team in results:
		teams_map[team["name"]] = team
		
	return teams_map

func get_bankroll() -> float:
	if not db: return 1000.0
	db.query("SELECT value FROM config WHERE key = 'bankroll'")
	if db.query_result.size() > 0:
		return float(db.query_result[0]["value"])
	return 1000.0

func set_bankroll(val: float) -> void:
	if not db: return
	db.query("INSERT OR REPLACE INTO config (key, value) VALUES ('bankroll', '" + str(val) + "')")

func get_default_stake() -> float:
	if not db: return 10.0
	db.query("SELECT value FROM config WHERE key = 'default_stake'")
	if db.query_result.size() > 0:
		return float(db.query_result[0]["value"])
	return 10.0

func set_default_stake(val: float) -> void:
	if not db: return
	db.query("INSERT OR REPLACE INTO config (key, value) VALUES ('default_stake', '" + str(val) + "')")

func get_config(key: String) -> String:
	if not db: return ""
	db.query("SELECT value FROM config WHERE key = '" + key + "'")
	if db.query_result.size() > 0:
		return db.query_result[0]["value"]
	return ""

func set_config(key: String, value: String) -> void:
	if not db: return
	db.query("INSERT OR REPLACE INTO config (key, value) VALUES ('" + key + "', '" + value + "')")

func record_bet(match_id: int, selection: String, stake: float, actual_odd: float) -> void:
	if not db: return
	
	# Update bankroll
	var current = get_bankroll()
	var new_bank = current - stake
	set_bankroll(new_bank)
	
	# Insert into user_bets
	var sql = "INSERT INTO user_bets (match_id, selection, stake, odd, status) VALUES (%d, '%s', %f, %f, 'PENDING')" % [match_id, selection, stake, actual_odd]
	db.query(sql)
	print("LogicBet: Bet recorded. MatchID: ", match_id, " Stake: ", stake, " Odds: ", actual_odd)

func fetch_user_bets() -> Array:
	if not db: return []
	var sql = """
		SELECT 
			ub.id,
			t1.name as home_name,
			t2.name as away_name,
			ub.selection,
			ub.stake,
			ub.odd,
			ub.status,
			ub.profit,
			m.date,
			m.home_score,
			m.away_score
		FROM user_bets ub
		JOIN matches m ON ub.match_id = m.id
		JOIN teams t1 ON m.home_team_id = t1.id
		JOIN teams t2 ON m.away_team_id = t2.id
		ORDER BY ub.id DESC
	"""
	if db.query(sql):
		return db.query_result
	return []

func delete_user_bet(bet_id: int) -> void:
	if not db: return
	db.query("DELETE FROM user_bets WHERE id = %d" % bet_id)
	print("LogicBet: Bet %d deleted" % bet_id)

func fetch_match_comparison_data(home_name: String, away_name: String) -> Dictionary:
	# Simplified fetch for team ratings
	var teams = fetch_teams_data()
	if teams.has(home_name) and teams.has(away_name):
		return {
			"home": teams[home_name],
			"away": teams[away_name]
		}
	return {}

func get_sync_status() -> Dictionary:
	if not db: return {"last_sync": "0", "error": "", "limits": "100"}
	db.query("SELECT key, value FROM config WHERE key IN ('last_sync_time', 'sync_error', 'api_requests_left')")
	var status = {"last_sync": "0", "error": "", "limits": "100"}
	for row in db.query_result:
		if row["key"] == "last_sync_time": status["last_sync"] = row["value"]
		elif row["key"] == "sync_error": status["error"] = row["value"]
		elif row["key"] == "api_requests_left": status["limits"] = row["value"]
	return status

func fetch_global_history() -> Array:
	if not db: return []
	var sql = """
		SELECT 
			m.id,
			m.home_team_id,
			m.away_team_id,
			t1.name as home_name, 
			t2.name as away_name,
			m.home_score,
			m.away_score,
			m.date,
			m.league,
			m.status,
			t1.elo_rating as h_elo_live,
			t2.elo_rating as a_elo_live,
			t1.current_form as form_home,
			t2.current_form as form_away,
			m.h_elo_change,
			m.a_elo_change,
			m.corners_h, m.corners_a,
			m.yellow_cards_h, m.yellow_cards_a,
			m.red_cards_h, m.red_cards_a,
			m.shots_on_h, m.shots_on_a,
			m.xg_h, m.xg_a,
			m.possession_h, m.possession_a,
			GROUP_CONCAT(p.selection, ' / ') as ai_prediction,
			GROUP_CONCAT(p.is_hit, '|') as ai_hit
		FROM matches m
		JOIN teams t1 ON m.home_team_id = t1.id
		JOIN teams t2 ON m.away_team_id = t2.id
		LEFT JOIN predictions p ON p.match_id = m.id
		WHERE m.status IN ('FT', 'AET', 'PEN', 'FINISHED') AND m.league_id IN (39, 2, 3, 848, 140, 78, 135, 61, 88, 94, 40)
		GROUP BY m.id
		ORDER BY m.date DESC 
		LIMIT 150
	"""
	if db.query(sql):
		return db.query_result
	return []

func search_teams(query: String) -> Array:
	if not db: return []
	var sql = "SELECT id, name, elo_rating, current_form, avg_scored, avg_conceded FROM teams WHERE name LIKE '%%%s%%' AND id IN (SELECT home_team_id FROM matches WHERE league_id IN (39, 2, 3, 848, 140, 78, 135, 61)) ORDER BY elo_rating DESC LIMIT 30" % query
	if db.query(sql):
		return db.query_result
	return []

func fetch_prediction_stats(market_filter: String = "ALL") -> Dictionary:
	if not db: return {"total": 0, "hits": 0, "days": []}
	
	var where_clause = "WHERE p.is_hit IS NOT NULL"
	if market_filter == "1X2":
		where_clause += " AND p.market = '1X2/DC'"
	elif market_filter == "TOTALS":
		where_clause += " AND (p.market = 'Total Goals' OR p.market = '1st Half Goals' OR p.market = 'Individual Total')"
	elif market_filter == "CORNERS":
		where_clause += " AND p.market = 'Corners'"
	elif market_filter == "CARDS":
		where_clause += " AND p.market = 'Cards'"
		
	var sql = """
		SELECT 
			substr(m.date, 1, 10) as day_date,
			COUNT(*) as total_bets,
			SUM(p.is_hit) as won_bets
		FROM predictions p
		JOIN matches m ON p.match_id = m.id
		%s
		GROUP BY substr(m.date, 1, 10)
		ORDER BY substr(m.date, 1, 10) DESC
		LIMIT 30
	""" % where_clause
	
	var stats = {"total": 0, "hits": 0, "days": []}
	if db.query(sql):
		for row in db.query_result:
			var total = int(row["total_bets"])
			var won = int(row["won_bets"]) if row["won_bets"] else 0
			stats["total"] += total
			stats["hits"] += won
			stats["days"].append({
				"date": row["day_date"],
				"total": total,
				"won": won,
				"acc": (float(won) / float(total)) * 100.0 if total > 0 else 0.0
			})
	return stats

func fetch_team_matches(team_id: int) -> Array:
	if not db: return []
	var sql = """
		SELECT t1.name as h_name, t2.name as a_name, m.home_score, m.away_score, m.date 
		FROM matches m
		JOIN teams t1 ON m.home_team_id = t1.id
		JOIN teams t2 ON m.away_team_id = t2.id
		WHERE (m.home_team_id = %d OR m.away_team_id = %d) AND m.status = 'FT'
		ORDER BY m.date DESC LIMIT 5
	""" % [team_id, team_id]
	if db.query(sql):
		return db.query_result
	return []

func fetch_team_stats_report(team_id: int) -> Dictionary:
	if not db: return {}
	
	# 1. Basic Team Info
	db.query("SELECT * FROM teams WHERE id = %d" % team_id)
	if db.query_result.size() == 0: return {}
	var team_info = db.query_result[0]
	
	# 2. Last 10 Matches for Averages
	var sql = """
		SELECT m.*, t1.name as h_name, t2.name as a_name 
		FROM matches m 
		JOIN teams t1 ON m.home_team_id = t1.id 
		JOIN teams t2 ON m.away_team_id = t2.id 
		WHERE (m.home_team_id = %d OR m.away_team_id = %d) AND m.status IN ('FT', 'AET', 'PEN', 'FINISHED') 
		ORDER BY m.date DESC LIMIT 10
	""" % [team_id, team_id]
	db.query(sql)
	var matches = db.query_result
	
	var stats = {
		"wins": 0, "draws": 0, "losses": 0,
		"gs": 0.0, "gc": 0.0, "xg": 0.0, "corners": 0.0, "shots": 0.0, 
		"yellow_cards": 0.0, "red_cards": 0.0,
		"matches": matches,
		"info": team_info
	}
	
	if matches.size() > 0:
		for m in matches:
			var is_home = (int(m["home_team_id"]) == team_id)
			var hs = m.get("home_score", 0)
			var ascores = m.get("away_score", 0)
			if hs == null: hs = 0
			if ascores == null: ascores = 0
			
			var my_s = int(hs) if is_home else int(ascores)
			var op_s = int(ascores) if is_home else int(hs)
			
			if my_s > op_s: stats["wins"] += 1
			elif my_s < op_s: stats["losses"] += 1
			else: stats["draws"] += 1
			
			stats["gs"] += my_s
			stats["gc"] += op_s
			stats["xg"] += float(m.get("xg_h", 0.0) if is_home else m.get("xg_a", 0.0))
			stats["corners"] += int(m.get("corners_h", 0) if is_home else m.get("corners_a", 0))
			stats["shots"] += int(m.get("shots_on_h", 0) if is_home else m.get("shots_on_a", 0))
			stats["yellow_cards"] += int(m.get("yellow_cards_h", 0) if is_home else m.get("yellow_cards_a", 0))
			stats["red_cards"] += int(m.get("red_cards_h", 0) if is_home else m.get("red_cards_a", 0))
			
		var count = float(matches.size())
		stats["gs"] /= count
		stats["gc"] /= count
		stats["xg"] /= count
		stats["corners"] /= count
		stats["shots"] /= count
		stats["yellow_cards"] /= count
		stats["red_cards"] /= count
		
	return stats

func fetch_match_predictions(match_id: int) -> Array:
	if not db: return []
	db.query("SELECT * FROM predictions WHERE match_id = %d" % match_id)
	return db.query_result

func sync_from_json(data: Dictionary) -> void:
	if not db: return
	
	print("LogicBet: Syncing data from JSON snapshot...")
	
	# 1. Update Config
	if data.has("config"):
		for key in data["config"]:
			set_config(key, str(data["config"][key]))
	
	# 2. Update Teams
	if data.has("teams"):
		# We use a transaction for speed
		db.query("BEGIN TRANSACTION")
		for t in data["teams"]:
			var sql = "INSERT OR REPLACE INTO teams (id, name, elo_rating, current_form, rank, points) VALUES (%d, '%s', %f, '%s', %d, %d)" % [
				t["id"], t["name"].replace("'", "''"), t["elo_rating"], t["current_form"], t["rank"], t["points"]
			]
			db.query(sql)
		db.query("COMMIT")
	
	# 3. Update Matches & Predictions
	# This is more complex because of foreign keys, but since we are syncing, 
	# we can just insert/replace everything from the 'matches' list in the snapshot
	if data.has("matches"):
		db.query("BEGIN TRANSACTION")
		for m in data["matches"]:
			# Ensure teams exist (should be handled by step 2, but just in case)
			var m_sql = "INSERT OR REPLACE INTO matches (id, remote_id, date, league, league_id, home_team_id, away_team_id, home_score, away_score, status, corners_h, corners_a, yellow_cards_h, yellow_cards_a, xg_h, xg_a, possession_h, possession_a) VALUES (%d, %d, '%s', '%s', %d, %d, %d, %s, %s, '%s', %d, %d, %d, %d, %f, %f, %d, %d)" % [
				m["id"], m.get("remote_id", 0), m["date"], m["league"].replace("'", "''"), m.get("league_id", 0), m["home_team_id"], m["away_team_id"],
				str(m["home_score"]) if m["home_score"] != null else "NULL",
				str(m["away_score"]) if m["away_score"] != null else "NULL",
				m["status"], m.get("corners_h", 0), m.get("corners_a", 0), m.get("yellow_cards_h", 0), m.get("yellow_cards_a", 0),
				m.get("xg_h", 0.0), m.get("xg_a", 0.0), m.get("possession_h", 50), m.get("possession_a", 50)
			]
			db.query(m_sql)
			
			# Re-insert predictions for this match if they are in the combined strings
			if m.has("ai_prediction") and m["ai_prediction"]:
				# Note: Our snapshot doesn't have the individual prediction rows for RECENT matches, 
				# but it has them in predictions_history. We'll handle individual rows in step 4.
				pass
				
		db.query("COMMIT")

	# 4. Update Prediction History
	if data.has("predictions_history"):
		db.query("BEGIN TRANSACTION")
		for p in data["predictions_history"]:
			var p_sql = "INSERT OR REPLACE INTO predictions (id, match_id, algorithm, market, selection, calculated_prob, bookmaker_odd, value_percentage, confidence_level, is_hit) VALUES (%d, %d, '%s', '%s', '%s', %f, %f, %f, '%s', %s)" % [
				p["id"], p["match_id"], p["algorithm"].replace("'", "''"), p["market"], p["selection"].replace("'", "''"), 
				p["calculated_prob"], p["bookmaker_odd"], p["value_percentage"], p["confidence_level"],
				str(p["is_hit"]) if p["is_hit"] != null else "NULL"
			]
			db.query(p_sql)
		db.query("COMMIT")

	# 5. Update User Bets
	if data.has("user_bets"):
		db.query("BEGIN TRANSACTION")
		for ub in data["user_bets"]:
			var ub_sql = "INSERT OR REPLACE INTO user_bets (id, match_id, selection, stake, odd, status, profit) VALUES (%d, %d, '%s', %f, %f, '%s', %f)" % [
				ub["id"], ub["match_id"], ub["selection"].replace("'", "''"), ub["stake"], ub["odd"], ub["status"], ub["profit"]
			]
			db.query(ub_sql)
		db.query("COMMIT")
	
	print("LogicBet: Cloud sync applied successfully to local DB.")

func close_db() -> void:
	if db:
		db.close_db()
