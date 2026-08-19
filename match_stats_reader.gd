extends Node

# Match Statistics Reader for Godot
# Reads match_statistics.json file and displays statistics

var match_data = {}
var current_match_index = 0
var last_update_time = 0

func _ready():
	print("Match Statistics Reader Ready")
	check_for_updates()

func check_for_updates():
	# Check for updates from GitHub
	var current_time = OS.get_unix_time()
	if current_time - last_update_time > 3600:  # Check every hour
		print("Checking for updates...")
		var http_request = HTTPRequest.new()
		http_request.connect("request_completed", self, "_on_request_completed")
		http_request.request("https://raw.githubusercontent.com/Jorge-Ardid/LogicBet/main/data/match_statistics.json?t=" + str(current_time))

func _on_request_completed(result, response_code, headers, body):
	if result == OK and response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body)
		if parse_result == OK:
			match_data = json.data
			last_update_time = OS.get_unix_time()
			print("Loaded ", match_data.matches.size(), " matches with statistics")
			update_match_display()
		else:
			print("Failed to parse match statistics JSON")
	else:
		print("Failed to fetch match statistics from GitHub")

func update_match_display():
	# Update UI with current match statistics
	if match_data.matches.size() > 0 and current_match_index < match_data.matches.size():
		var match = match_data.matches[current_match_index]
		
		# Update match header
		$MatchHeader.text = match.home_team + " vs " + match.away_team
		$ScoreLabel.text = "Score: " + match.score
		$StatusLabel.text = "Status: " + match.status
		$DateLabel.text = match.date
		
		# Update statistics
		var stats = match.statistics
		
		$ShotsHomeLabel.text = str(stats.shots.home)
		$ShotsAwayLabel.text = str(stats.shots.away)
		
		$CornersHomeLabel.text = str(stats.corners.home)
		$CornersAwayLabel.text = str(stats.corners.away)
		
		$CardsHomeLabel.text = str(stats.cards.home_yellow)
		$CardsAwayLabel.text = str(stats.cards.away_yellow)
		
		$PossessionHomeLabel.text = str(stats.possession.home) + "%"
		$PossessionAwayLabel.text = str(stats.possession.away) + "%"
		
		$XGHomeLabel.text = str(stats.xg.home)
		$XGAwayLabel.text = str(stats.xg.away)
		
		print("Updated display for match: ", match.home_team, " vs ", match.away_team)

func _on_next_match_pressed():
	# Show next match
	if current_match_index < match_data.matches.size() - 1:
		current_match_index += 1
		update_match_display()
		print("Next match (", current_match_index + 1, "/", match_data.matches.size(), ")")

func _on_previous_match_pressed():
	# Show previous match
	if current_match_index > 0:
		current_match_index -= 1
		update_match_display()
		print("Previous match (", current_match_index + 1, "/", match_data.matches.size(), ")")

func _on_refresh_pressed():
	# Refresh statistics data
	print("Refreshing match statistics...")
	check_for_updates()

func get_current_match_stats():
	# Get current match statistics for other scripts
	if match_data.matches.size() > 0 and current_match_index < match_data.matches.size():
		return match_data.matches[current_index]
	else:
		return null

func _on_match_selected(match_id):
	# Select specific match by ID
	for i in range(match_data.matches.size()):
		if match_data.matches[i].id == match_id:
			current_match_index = i
			update_match_display()
			print("Selected match ID: ", match_id)
			break
