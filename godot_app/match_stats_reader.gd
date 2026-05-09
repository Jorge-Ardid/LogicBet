extends Node

# Match Statistics Reader for Godot
# Reads match_statistics.json file and displays statistics

var match_data = {}
var current_match_index = 0

func _ready():
	print("Match Statistics Reader Ready")
	load_match_statistics()

func load_match_statistics():
	# Load match statistics from JSON file
	var file = FileAccess.open("res://match_statistics.json", FileAccess.READ)
	if file:
		var json_text = file.get_as_text()
		file.close()
		
		var json = JSON.new()
		var parse_result = json.parse(json_text)
		
		if parse_result == OK:
			match_data = json.data
			print("Loaded ", match_data.matches.size(), " matches with statistics")
			update_match_display()
		else:
			print("Failed to parse match statistics JSON")
	else:
		print("Could not open match_statistics.json file")

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
	load_match_statistics()

func get_current_match_stats():
	# Get current match statistics for other scripts
	if match_data.matches.size() > 0 and current_match_index < match_data.matches.size():
		return match_data.matches[current_match_index]
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

# Example UI structure needed:
# - $MatchHeader (Label)
# - $ScoreLabel (Label)
# - $StatusLabel (Label)
# - $DateLabel (Label)
# - $ShotsHomeLabel, $ShotsAwayLabel (Labels)
# - $CornersHomeLabel, $CornersAwayLabel (Labels)
# - $CardsHomeLabel, $CardsAwayLabel (Labels)
# - $PossessionHomeLabel, $PossessionAwayLabel (Labels)
# - $XGHomeLabel, $XGAwayLabel (Labels)
# - Next/Previous buttons with _on_next_match_pressed, _on_previous_match_pressed signals
