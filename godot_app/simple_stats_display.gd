extends Control

# Simple Match Statistics Display for Godot
# Reads match_statistics.json and displays statistics

var match_data = {}
var current_match_index = 0

func _ready():
	print("Simple Statistics Display Ready")
	load_statistics()
	
	# Create refresh button
	var refresh_button = Button.new()
	refresh_button.text = "Refresh Stats"
	refresh_button.position = Vector2(10, 10)
	refresh_button.pressed.connect(_on_refresh_pressed)
	add_child(refresh_button)
	
	# Create navigation buttons
	var next_button = Button.new()
	next_button.text = "Next Match"
	next_button.position = Vector2(10, 50)
	next_button.pressed.connect(_on_next_match)
	add_child(next_button)
	
	var prev_button = Button.new()
	prev_button.text = "Previous Match"
	prev_button.position = Vector2(120, 50)
	prev_button.pressed.connect(_on_previous_match)
	add_child(prev_button)
	
	# Create labels for display
	create_display_labels()
	update_display()

func load_statistics():
	# Load match statistics from JSON file
	var file = FileAccess.open("res://match_statistics.json", FileAccess.READ)
	if file:
		var json_text = file.get_as_text()
		file.close()
		
		var json = JSON.new()
		var parse_result = json.parse(json_text)
		
		if parse_result == OK:
			match_data = json.data
			print("Loaded ", match_data.matches.size(), " matches")
		else:
			print("Failed to parse statistics JSON")
	else:
		print("Could not open match_statistics.json")

func create_display_labels():
	# Create UI labels for statistics display
	var y_offset = 100
	
	# Match header
	var header_label = Label.new()
	header_label.name = "MatchHeader"
	header_label.position = Vector2(10, y_offset)
	header_label.size.x = 400
	add_child(header_label)
	y_offset += 30
	
	# Statistics labels
	var stats_labels = [
		"Shots Home", "Shots Away",
		"Corners Home", "Corners Away", 
		"Cards Home", "Cards Away",
		"Possession Home", "Possession Away",
		"xG Home", "xG Away"
	]
	
	for i in range(stats_labels.size()):
		var label = Label.new()
		label.name = "Stat" + str(i)
		label.position = Vector2(10 + (i % 2) * 200, y_offset + (i / 2) * 25)
		label.size.x = 180
		add_child(label)

func update_display():
	# Update all labels with current match data
	if match_data.has("matches") and match_data.matches.size() > 0:
		var match = match_data.matches[current_match_index]
		
		# Update header
		var header = get_node("MatchHeader")
		if header:
			header.text = match.home_team + " vs " + match.away_team + " (" + match.score + ")"
		
		# Update statistics
		var stats = match.statistics
		var stat_values = [
			str(stats.shots.home), str(stats.shots.away),
			str(stats.corners.home), str(stats.corners.away),
			str(stats.cards.home_yellow), str(stats.cards.away_yellow),
			str(stats.possession.home) + "%", str(stats.possession.away) + "%",
			str(stats.xg.home), str(stats.xg.away)
		]
		
		for i in range(stat_values.size()):
			var label = get_node("Stat" + str(i))
			if label:
				var stat_names = ["Shots Home", "Shots Away", "Corners Home", "Corners Away", 
				                "Cards Home", "Cards Away", "Possession Home", "Possession Away",
				                "xG Home", "xG Away"]
				label.text = stat_names[i] + ": " + stat_values[i]
		
		print("Updated display for match: ", match.home_team, " vs ", match.away_team)

func _on_refresh_pressed():
	# Refresh statistics data
	print("Refreshing statistics...")
	load_statistics()
	update_display()

func _on_next_match():
	# Show next match
	if match_data.has("matches") and current_match_index < match_data.matches.size() - 1:
		current_match_index += 1
		update_display()
		print("Next match (", current_match_index + 1, "/", match_data.matches.size(), ")")

func _on_previous_match():
	# Show previous match
	if current_match_index > 0:
		current_match_index -= 1
		update_display()
		print("Previous match (", current_match_index + 1, "/", match_data.matches.size(), ")")

func _input(event):
	# Handle keyboard input
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_RIGHT:
			_on_next_match()
		elif event.keycode == KEY_LEFT:
			_on_previous_match()
		elif event.keycode == KEY_F5:
			_on_refresh_pressed()
