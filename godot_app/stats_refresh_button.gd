extends Button

# Refresh Statistics Button for Godot
# This button manually refreshes match statistics from JSON file

func _ready():
	text = "🔄 Оновити статистику"
	pressed.connect(_on_refresh_pressed)
	
	# Style the button
	add_theme_font_size_override("font_size", 14)
	add_theme_color_override("font_color", Color.WHITE)
	
	# Set button size
	custom_minimum_size = Vector2(150, 30)

func _on_refresh_pressed():
	print("Manually refreshing match statistics...")
	
	# Load statistics from JSON file
	var file = FileAccess.open("user://match_statistics.json", FileAccess.READ)
	if file:
		var json_text = file.get_as_text()
		file.close()
		
		var json = JSON.new()
		var parse_result = json.parse(json_text)
		
		if parse_result == OK:
			var match_data = json.data
			print("Loaded ", match_data.matches.size(), " matches")
			
			# Find the Main.gd script and call its display function
			var main_script = get_node("/root/Main")
			if main_script and main_script.has_method("_load_match_statistics"):
				main_script._load_match_statistics()
				main_script._display_match_statistics()
				print("Statistics refreshed successfully!")
			else:
				print("Main script not found or missing method")
		else:
			print("Failed to parse statistics JSON")
	else:
		print("Could not open match_statistics.json")
