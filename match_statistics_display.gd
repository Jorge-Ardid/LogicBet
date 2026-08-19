extends Node

# Match Statistics Display Script for Godot
# This script connects to Python backend and displays match statistics

func _ready():
	print("Match Statistics Display Script Ready")

func show_match_statistics(match_id: int):
	# Call Python backend to get match statistics
	var output = []
	var exit_code = OS.execute("python -c \"from main import get_match_statistics; stats = get_match_statistics(" + str(match_id) + "); print('MATCH_ID:' + str(match_id) + '|SHOTS_HOME:' + str(stats['shots']['home']) + '|SHOTS_AWAY:' + str(stats['shots']['away']) + '|CORNERS_HOME:' + str(stats['corners']['home']) + '|CORNERS_AWAY:' + str(stats['corners']['away']) + '|CARDS_HOME_YELLOW:' + str(stats['cards']['home_yellow']) + '|CARDS_AWAY_YELLOW:' + str(stats['cards']['away_yellow']) + '|POSSESSION_HOME:' + str(stats['possession']['home']) + '|POSSESSION_AWAY:' + str(stats['possession']['away']) + '|XG_HOME:' + str(stats['xg']['home']) + '|XG_AWAY:' + str(stats['xg']['away']) + '\"")
	
	if exit_code == OK:
		var result = output[0].strip_edges().split("|")
		
		# Update UI elements
		$HomeTeamLabel.text = result[0].split(":")[1]
		$AwayTeamLabel.text = result[1].split(":")[1]
		$ScoreLabel.text = result[2].split(":")[1]
		$ShotsHomeLabel.text = result[3].split(":")[1]
		$ShotsAwayLabel.text = result[4].split(":")[1]
		$CornersHomeLabel.text = result[5].split(":")[1]
		$CornersAwayLabel.text = result[6].split(":")[1]
		$CardsHomeLabel.text = result[7].split(":")[1] + "/" + result[8].split(":")[1]
		$CardsAwayLabel.text = result[9].split(":")[1] + "/" + result[10].split(":")[1]
		$PossessionHomeLabel.text = result[11].split(":")[1] + "%"
		$PossessionAwayLabel.text = result[12].split(":")[1] + "%"
		$XGHomeLabel.text = result[13].split(":")[1]
		$XGAwayLabel.text = result[14].split(":")[1]
		
		print("Statistics updated for match ", match_id)
	else:
		print("Failed to get statistics for match ", match_id)

func _on_match_selected(match_id: int):
	print("Match selected: ", match_id)
	show_match_statistics(match_id)

# Connect to signal from match selection UI
func connect_signals():
	# Connect to your match selection button/signal
	# For example: $MatchList.item_selected.connect(_on_match_selected)
	pass

# Example usage:
# Call this when a match is selected in your UI
# show_match_statistics(match_id)
