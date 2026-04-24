extends Control

# --- DESIGN SYSTEM ---
const COLOR_BLACK = Color("#0a0a0a")
const COLOR_GRAPHITE = Color("#181818")
const COLOR_SURFACE = Color("#222222")
const COLOR_GOLD = Color("#d4af37")
const COLOR_GOLD_BRIGHT = Color("#f1c40f")
const COLOR_TEXT = Color("#e0e0e0")
const COLOR_TEXT_DIM = Color("#a0a0a0")
const COLOR_SUCCESS = Color("#2ecc71")
const COLOR_DANGER = Color("#e74c3c")

# UI References
var bank_label: Label
var dash_vbox: VBoxContainer
var history_vbox: VBoxContainer
var refresh_btn: Button
var bet_dialog: ConfirmationDialog
var stake_input: SpinBox
var odd_input: SpinBox
var match_confirm_lbl: Label
var analysis_popup: Window
var settings_bank_input: SpinBox
var settings_stake_input: SpinBox
var sync_status_lbl: Label
var search_vbox: VBoxContainer
var search_input: LineEdit
var team_popup: Window

# Stats Tab UI
var stats_filter: OptionButton
var stats_chart_hb: HBoxContainer
var stats_list_vb: VBoxContainer
var stats_total_lbl: Label
var github_user_input: LineEdit
var github_repo_input: LineEdit

# Context
var current_match_id: int = -1
var current_selection: String = ""
var ai_odd: float = 0.0
var is_syncing: bool = false

# Match statistics data
# @onready var db_viewer = $DBViewer (Keep below)
@onready var db_viewer = $DBViewer

func _ready():
	_setup_theme()
	_setup_ui()
	_refresh_data()
	
	# Auto-sync on startup as requested
	get_tree().create_timer(1.0).timeout.connect(_on_sync_pressed)

func _setup_theme():
	theme = Theme.new()
	var sb_panel = StyleBoxFlat.new(); sb_panel.bg_color = COLOR_BLACK
	theme.set_stylebox("panel", "PanelContainer", sb_panel)
	
	var sb_tab = StyleBoxFlat.new(); sb_tab.bg_color = COLOR_GRAPHITE; sb_tab.content_margin_left = 20; sb_tab.content_margin_right = 20
	theme.set_stylebox("tab_unselected", "TabContainer", sb_tab)
	theme.set_stylebox("tab_selected", "TabContainer", sb_tab)

func _setup_ui():
	var bg = ColorRect.new(); bg.color = COLOR_BLACK; bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); add_child(bg)
	
	var margin = MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 40); margin.add_theme_constant_override("margin_top", 40)
	margin.add_theme_constant_override("margin_right", 40); margin.add_theme_constant_override("margin_bottom", 40)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); add_child(margin)
	
	var v_main := VBoxContainer.new(); v_main.add_theme_constant_override("separation", 25); margin.add_child(v_main)
	v_main.add_child(_create_header())
	
	var tabs := TabContainer.new(); tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL; v_main.add_child(tabs)
	
	# Create Dashboard
	var dash_scroll = ScrollContainer.new(); dash_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL; dash_scroll.name = " 🏟 АНАЛІТИКА "
	var dash_margin = MarginContainer.new()
	dash_margin.add_theme_constant_override("margin_left", 20); dash_margin.add_theme_constant_override("margin_right", 20)
	dash_margin.add_theme_constant_override("margin_top", 20); dash_margin.add_theme_constant_override("margin_bottom", 20)
	dash_margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL; dash_scroll.add_child(dash_margin)
	dash_vbox = VBoxContainer.new(); dash_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL; dash_vbox.add_theme_constant_override("separation", 20); dash_margin.add_child(dash_vbox)
	tabs.add_child(dash_scroll)
	
	# Create History
	var hist_scroll = ScrollContainer.new(); hist_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL; hist_scroll.name = " 📜 ІСТОРІЯ "
	var hist_margin = MarginContainer.new()
	hist_margin.add_theme_constant_override("margin_left", 20); hist_margin.add_theme_constant_override("margin_right", 20)
	hist_margin.add_theme_constant_override("margin_top", 20); hist_margin.add_theme_constant_override("margin_bottom", 20)
	hist_margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL; hist_scroll.add_child(hist_margin)
	history_vbox = VBoxContainer.new(); history_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL; history_vbox.add_theme_constant_override("separation", 15); hist_margin.add_child(history_vbox)
	
	# History tab setup
	tabs.add_child(hist_scroll)
	
	# Create Search Tab
	var search_scroll = ScrollContainer.new(); search_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL; search_scroll.name = " 🔍 ПОШУК "
	var search_margin = MarginContainer.new()
	search_margin.add_theme_constant_override("margin_left", 30); search_margin.add_theme_constant_override("margin_right", 30); search_margin.add_theme_constant_override("margin_top", 30); search_margin.add_theme_constant_override("margin_bottom", 30)
	search_margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL; search_scroll.add_child(search_margin)
	var s_vbox = VBoxContainer.new(); s_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL; s_vbox.add_theme_constant_override("separation", 25); search_margin.add_child(s_vbox)
	
	var search_hb = HBoxContainer.new(); s_vbox.add_child(search_hb)
	search_input = LineEdit.new(); search_input.placeholder_text = "Введіть назву команди (напр. Arsenal)..."; search_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL; search_hb.add_child(search_input)
	search_input.text_changed.connect(_on_search_changed)
	
	search_vbox = VBoxContainer.new(); search_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL; search_vbox.add_theme_constant_override("separation", 15); s_vbox.add_child(search_vbox)
	tabs.add_child(search_scroll)
	
	# Create Statistics Tab
	var stats_scroll = ScrollContainer.new(); stats_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL; stats_scroll.name = " 📈 СТАТИСТИКА "
	var stats_margin = MarginContainer.new()
	stats_margin.add_theme_constant_override("margin_left", 30); stats_margin.add_theme_constant_override("margin_right", 30)
	stats_margin.add_theme_constant_override("margin_top", 30); stats_margin.add_theme_constant_override("margin_bottom", 30)
	stats_margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL; stats_scroll.add_child(stats_margin)
	
	var stats_vbox = VBoxContainer.new(); stats_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL; stats_vbox.add_theme_constant_override("separation", 25); stats_margin.add_child(stats_vbox)
	
	var filter_hb = HBoxContainer.new(); filter_hb.alignment = BoxContainer.ALIGNMENT_CENTER; stats_vbox.add_child(filter_hb)
	filter_hb.add_child(_lbl("Маркет: ", COLOR_TEXT_DIM))
	stats_filter = OptionButton.new()
	stats_filter.add_item("Всі прогнози") # 0
	stats_filter.add_item("Ісход (1X2/DC)") # 1
	stats_filter.add_item("Тотали (Голи)") # 2
	stats_filter.add_item("Кутові") # 3
	stats_filter.add_item("Картки") # 4
	stats_filter.item_selected.connect(_refresh_statistics)
	filter_hb.add_child(stats_filter)
	
	var tot_panel = PanelContainer.new()
	var tot_style = StyleBoxFlat.new(); tot_style.bg_color = COLOR_SURFACE; tot_style.set_corner_radius_all(15); tot_style.content_margin_left=20; tot_style.content_margin_top=20; tot_style.content_margin_bottom=20; tot_panel.add_theme_stylebox_override("panel", tot_style)
	stats_vbox.add_child(tot_panel)
	stats_total_lbl = _lbl("Оберіть категорію...", COLOR_GOLD); stats_total_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER; stats_total_lbl.add_theme_font_size_override("font_size", 24)
	tot_panel.add_child(stats_total_lbl)
	
	stats_vbox.add_child(_lbl("ДИНАМІКА ПО ДНЯХ (Гістограма):", COLOR_TEXT_DIM))
	var chart_panel = PanelContainer.new(); chart_panel.custom_minimum_size.y = 250
	var c_style = StyleBoxFlat.new(); c_style.bg_color = COLOR_GRAPHITE; c_style.set_corner_radius_all(10); c_style.content_margin_left=20; c_style.content_margin_right=20; c_style.content_margin_bottom=20; chart_panel.add_theme_stylebox_override("panel", c_style)
	stats_vbox.add_child(chart_panel)
	stats_chart_hb = HBoxContainer.new(); stats_chart_hb.size_flags_horizontal = Control.SIZE_EXPAND_FILL; stats_chart_hb.size_flags_vertical = Control.SIZE_EXPAND_FILL; stats_chart_hb.alignment = BoxContainer.ALIGNMENT_CENTER; stats_chart_hb.add_theme_constant_override("separation", 15)
	chart_panel.add_child(stats_chart_hb)
	
	stats_vbox.add_child(_lbl("ДЕТАЛІ:", COLOR_TEXT_DIM))
	stats_list_vb = VBoxContainer.new(); stats_list_vb.add_theme_constant_override("separation", 10); stats_vbox.add_child(stats_list_vb)
	
	tabs.add_child(stats_scroll)
	
	var sett = _build_settings(); sett.name = " ⚙️ НАЛАШТУВАННЯ "; tabs.add_child(sett)
	
	_setup_popups()

func _create_header() -> PanelContainer:
	var pc = PanelContainer.new()
	var style = StyleBoxFlat.new(); style.bg_color = COLOR_GRAPHITE; style.content_margin_left = 30; style.content_margin_right = 30; style.content_margin_top = 20; style.content_margin_bottom = 20
	style.set_corner_radius_all(15); style.border_width_bottom = 4; style.border_color = COLOR_GOLD; pc.add_theme_stylebox_override("panel", style)
	
	var hb = HBoxContainer.new(); pc.add_child(hb)
	var title = Label.new(); title.text = "LOGICBET ● PREDICTIVE AI"; title.add_theme_font_size_override("font_size", 32); title.add_theme_color_override("font_color", COLOR_GOLD); hb.add_child(title)
	var spacer = Control.new(); spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL; hb.add_child(spacer)
	
	sync_status_lbl = Label.new(); sync_status_lbl.text = ""; sync_status_lbl.add_theme_color_override("font_color", COLOR_GOLD_BRIGHT); hb.add_child(sync_status_lbl)
	refresh_btn = Button.new(); refresh_btn.text = " ↻ ОНОВИТИ "; refresh_btn.pressed.connect(_on_sync_pressed); hb.add_child(refresh_btn)
	
	var bank_v = VBoxContainer.new(); bank_v.alignment = BoxContainer.ALIGNMENT_CENTER; hb.add_child(bank_v)
	bank_label = Label.new(); bank_label.text = "0.00 грн"; bank_label.add_theme_font_size_override("font_size", 28); bank_label.add_theme_color_override("font_color", COLOR_SUCCESS); bank_v.add_child(bank_label)
	
	return pc

func _build_settings() -> MarginContainer:
	var m = MarginContainer.new(); m.add_theme_constant_override("margin_top", 50)
	var cc = CenterContainer.new(); m.add_child(cc)
	var pc = PanelContainer.new(); cc.add_child(pc)
	var style = StyleBoxFlat.new(); style.bg_color = COLOR_SURFACE; style.set_content_margin_all(50); style.set_corner_radius_all(20); style.border_width_left = 4; style.border_color = COLOR_GOLD; pc.add_theme_stylebox_override("panel", style)
	
	var v = VBoxContainer.new(); v.add_theme_constant_override("separation", 30); pc.add_child(v)
	var l = Label.new(); l.text = "⚙️ НАЛАШТУВАННЯ ТРЕКЕРУ"; l.add_theme_font_size_override("font_size", 24); l.add_theme_color_override("font_color", COLOR_GOLD); v.add_child(l)
	
	var grid = GridContainer.new(); grid.columns = 2; grid.add_theme_constant_override("h_separation", 30); grid.add_theme_constant_override("v_separation", 20); v.add_child(grid)
	grid.add_child(_lbl("Банк (грн):", COLOR_TEXT_DIM)); settings_bank_input = SpinBox.new(); settings_bank_input.max_value = 1000000; settings_bank_input.custom_minimum_size.x = 200; grid.add_child(settings_bank_input)
	grid.add_child(_lbl("Ставка за замовчуванням:", COLOR_TEXT_DIM)); settings_stake_input = SpinBox.new(); settings_stake_input.min_value = 10; settings_stake_input.max_value = 10000; settings_stake_input.custom_minimum_size.x = 200; grid.add_child(settings_stake_input)
	
	v.add_child(_lbl("☁️ НАЛАШТУВАННЯ GITHUB (ДЛЯ ТЕЛЕФОНУ)", COLOR_GOLD))
	var gh_grid = GridContainer.new(); gh_grid.columns = 2; gh_grid.add_theme_constant_override("h_separation", 30); v.add_child(gh_grid)
	gh_grid.add_child(_lbl("User:", COLOR_TEXT_DIM)); github_user_input = LineEdit.new(); github_user_input.custom_minimum_size.x = 200; gh_grid.add_child(github_user_input)
	gh_grid.add_child(_lbl("Repo:", COLOR_TEXT_DIM)); github_repo_input = LineEdit.new(); github_repo_input.custom_minimum_size.x = 200; gh_grid.add_child(github_repo_input)

	var save_btn = Button.new(); save_btn.text = " ЗБЕРЕГТИ ВСІ ЗМІНИ "; save_btn.custom_minimum_size.y = 50; save_btn.pressed.connect(_on_save_settings); v.add_child(save_btn)

	return m

func _setup_popups():
	bet_dialog = ConfirmationDialog.new(); bet_dialog.title = "ОФОРМИТИ ТРЕКЕР"; add_child(bet_dialog)
	var v = VBoxContainer.new(); v.add_theme_constant_override("separation", 20); v.custom_minimum_size = Vector2(400, 150); bet_dialog.add_child(v)
	match_confirm_lbl = Label.new(); match_confirm_lbl.add_theme_color_override("font_color", COLOR_GOLD); match_confirm_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER; v.add_child(match_confirm_lbl)
	var grid = GridContainer.new(); grid.columns = 2; grid.add_theme_constant_override("h_separation", 20); v.add_child(grid)
	grid.add_child(_lbl("Кеф:")); odd_input = SpinBox.new(); odd_input.min_value = 1.01; odd_input.max_value = 50.0; odd_input.step = 0.01; grid.add_child(odd_input)
	grid.add_child(_lbl("Сума (грн):")); stake_input = SpinBox.new(); stake_input.min_value = 1.0; stake_input.max_value = 10000.0; stake_input.step = 1.0; grid.add_child(stake_input)
	bet_dialog.confirmed.connect(_on_bet_confirmed)

	analysis_popup = Window.new(); analysis_popup.title = "АНАЛІЗ КОМАНД"; analysis_popup.size = Vector2(650, 500); analysis_popup.visible = false; add_child(analysis_popup)
	analysis_popup.close_requested.connect(analysis_popup.hide)
	var scroll = ScrollContainer.new(); scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); analysis_popup.add_child(scroll)
	var m_cont = MarginContainer.new()
	m_cont.add_theme_constant_override("margin_left", 30); m_cont.add_theme_constant_override("margin_right", 30); m_cont.add_theme_constant_override("margin_top", 30); m_cont.add_theme_constant_override("margin_bottom", 30)
	scroll.add_child(m_cont)
	analysis_popup.set_meta("content_vbox", VBoxContainer.new())
	var content = analysis_popup.get_meta("content_vbox")
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL; content.add_theme_constant_override("separation", 25); m_cont.add_child(content)

	team_popup = Window.new(); team_popup.title = "ПРОФІЛЬ КОМАНДИ"; team_popup.size = Vector2(850, 650); team_popup.visible = false; add_child(team_popup)
	team_popup.close_requested.connect(team_popup.hide)
	var t_scroll = ScrollContainer.new(); t_scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); team_popup.add_child(t_scroll)
	var t_m_cont = MarginContainer.new()
	t_m_cont.add_theme_constant_override("margin_left", 30); t_m_cont.add_theme_constant_override("margin_right", 30); t_m_cont.add_theme_constant_override("margin_top", 30); t_m_cont.add_theme_constant_override("margin_bottom", 30)
	t_scroll.add_child(t_m_cont)
	team_popup.set_meta("content_vbox", VBoxContainer.new())
	var t_content = team_popup.get_meta("content_vbox")
	t_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL; t_content.add_theme_constant_override("separation", 25); t_m_cont.add_child(t_content)

func _refresh_data():
	if not dash_vbox or not history_vbox: return
	var bank = db_viewer.get_bankroll()
	var def_stake = db_viewer.get_default_stake()
	bank_label.text = str(snapped(bank, 0.01)) + " грн"
	settings_bank_input.value = bank
	settings_stake_input.value = def_stake
	
	github_user_input.text = db_viewer.get_config("github_user") if db_viewer.get_config("github_user") else ""
	github_repo_input.text = db_viewer.get_config("github_repo") if db_viewer.get_config("github_repo") else ""

	
	# Update sync status info
	var status = db_viewer.get_sync_status()
	var req_left = status["limits"]
	
	if status["error"] != "":
		sync_status_lbl.text = status["error"] + " (Залишилось: " + req_left + ")"
		sync_status_lbl.add_theme_color_override("font_color", COLOR_DANGER)
	else:
		var last_sync_f = float(status["last_sync"])
		if last_sync_f > 0:
			var time_dict = Time.get_datetime_dict_from_unix_time(int(last_sync_f))
			sync_status_lbl.text = "ОСТАННЄ ОНОВЛЕННЯ: %02d:%02d (Ліміт: %s) " % [time_dict["hour"], time_dict["minute"], req_left]
			sync_status_lbl.add_theme_color_override("font_color", COLOR_TEXT_DIM)
		else:
			sync_status_lbl.text = "НЕМАЄ ДАНИХ (Ліміт: " + req_left + ") "
			
	_update_dashboard(); _update_history()
	if stats_filter: _refresh_statistics(stats_filter.selected)

func _update_dashboard():
	for child in dash_vbox.get_children(): child.queue_free()
	
	# NEW: AI Stats Tracker
	var ai_stats = db_viewer.get_ai_stats()
	if ai_stats["total"] > 0:
		var stat_panel = PanelContainer.new()
		var p_style = StyleBoxFlat.new(); p_style.bg_color = COLOR_SURFACE; p_style.set_corner_radius_all(10); p_style.content_margin_left = 20; p_style.content_margin_top = 15; p_style.content_margin_bottom = 15
		p_style.border_width_left = 4; p_style.border_color = COLOR_SUCCESS if ai_stats["acc"] >= 50 else COLOR_DANGER
		stat_panel.add_theme_stylebox_override("panel", p_style)
		var stat_hb = HBoxContainer.new(); stat_panel.add_child(stat_hb)
		stat_hb.add_child(_lbl("🧠 ШІ-АВТОТЕСТ: ", COLOR_TEXT_DIM))
		stat_hb.add_child(_lbl("Точність " + str(snapped(ai_stats["acc"], 0.1)) + "%", COLOR_SUCCESS if ai_stats["acc"] >= 50 else COLOR_DANGER))
		stat_hb.add_child(_lbl("  (" + str(ai_stats["hits"]) + "/" + str(ai_stats["total"]) + " успішних прогнозів)", COLOR_TEXT_DIM))
		dash_vbox.add_child(stat_panel)
		
	var predictions = db_viewer.fetch_predictions()
	if predictions.size() == 0:
		dash_vbox.add_child(_lbl("Натисніть «ОНОВИТИ», щоб завантажити ігри на наступні дні.", COLOR_TEXT_DIM))
		return
		
	var last_date = ""
	for p in predictions:
		var current_date = p["date"].split("T")[0] # Get YYYY-MM-DD correctly from ISO
		if current_date != last_date:
			# Add Date Header
			var header_panel = PanelContainer.new()
			var style = StyleBoxFlat.new(); style.bg_color = COLOR_GRAPHITE; style.set_corner_radius_all(10); style.content_margin_left = 15; style.content_margin_top = 10; style.content_margin_bottom = 10
			header_panel.add_theme_stylebox_override("panel", style)
			
			var clean_date = current_date.split("T")[0]
			var header_lbl = _lbl("📆 ПЛАН НА " + clean_date, COLOR_GOLD)
			header_lbl.add_theme_font_size_override("font_size", 18)
			header_panel.add_child(header_lbl)
			dash_vbox.add_child(header_panel)
			last_date = current_date
			
		dash_vbox.add_child(_create_match_card(p))

func _create_match_card(p) -> PanelContainer:
	var card = PanelContainer.new()
	var style = StyleBoxFlat.new(); style.bg_color = COLOR_SURFACE; style.content_margin_left = 25; style.content_margin_right = 25; style.content_margin_top = 20; style.content_margin_bottom = 20
	style.set_corner_radius_all(12); style.border_width_left = 4;
	
	# Status Calculation based on user request:
	# "закінчилася", "йде/проходить/наживо", "скоро буде"
	var unix_match = Time.get_unix_time_from_datetime_string(p["date"].replace(" ", "T"))
	var unix_now = Time.get_unix_time_from_system()
	var diff = unix_now - unix_match
	
	var status_text = "СКОРО БУДЕ"
	var status_color = COLOR_GOLD
	
	if p["status"] == "FT":
		status_text = "ЗАКІНЧИЛАСЯ"
		status_color = COLOR_TEXT_DIM
	elif diff > 0 and diff < 7200: # Ongoing for 2 hours
		status_text = "ЙДЕ / НАЖИВО"
		status_color = COLOR_SUCCESS
	elif diff >= 7200:
		status_text = "ЗАКІНЧИЛАСЯ"
		status_color = COLOR_TEXT_DIM
	
	# Parse metadata
	var tag = "📊"
	if p.get("algorithm") != null:
		var meta_parts = p["algorithm"].split("|")
		tag = meta_parts[0]
	style.border_color = COLOR_GOLD if ("💎" in tag or "🔥" in tag) else Color(0,0,0,0)
	card.add_theme_stylebox_override("panel", style)
	
	var hb = HBoxContainer.new(); hb.add_theme_constant_override("separation", 25); 
	hb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_child(hb)
	
	var tag_container = Control.new(); tag_container.custom_minimum_size = Vector2(120, 0); hb.add_child(tag_container)
	var tag_lbl = _lbl(tag + "\n" + status_text, status_color); tag_lbl.set_anchors_and_offsets_preset(Control.PRESET_CENTER_LEFT); tag_container.add_child(tag_lbl)
	
	var v_info = VBoxContainer.new(); v_info.size_flags_horizontal = Control.SIZE_EXPAND_FILL; v_info.alignment = BoxContainer.ALIGNMENT_CENTER; hb.add_child(v_info)
	
	# Small Header for League/Date inside the card to save width
	var header_hbox = HBoxContainer.new(); v_info.add_child(header_hbox)
	header_hbox.add_child(_lbl(p["league"], COLOR_TEXT_DIM))
	header_hbox.add_child(_lbl(" • ", COLOR_TEXT_DIM))
	var date_lbl = _lbl(_format_match_date(p["date"]), COLOR_GOLD)
	date_lbl.add_theme_font_size_override("font_size", 12)
	header_hbox.add_child(date_lbl)

	
	# Team names row with dynamic coloring
	var match_hb = HBoxContainer.new(); v_info.add_child(match_hb)
	
	# Match buttons with dynamic color based on CURRENT FORM
	var h_form = p.get("form_home", null)
	var a_form = p.get("form_away", null)
	
	var h_btn = LinkButton.new(); h_btn.text = p["home_name"]; h_btn.add_theme_font_size_override("font_size", 18); h_btn.add_theme_color_override("font_color", _form_color(h_form)); h_btn.pressed.connect(_on_show_team_stats.bind(p["home_team_id"])); match_hb.add_child(h_btn)
	
	var sep_btn = LinkButton.new(); sep_btn.underline = LinkButton.UNDERLINE_MODE_NEVER
	var sep_text = " — "
	if p.get("home_score") != null: sep_text = " %d : %d " % [p["home_score"], p["away_score"]]
	sep_btn.text = sep_text; sep_btn.add_theme_color_override("font_color", COLOR_GOLD); sep_btn.pressed.connect(_on_show_analysis.bind(p)); match_hb.add_child(sep_btn)
	
	var a_btn = LinkButton.new(); a_btn.text = p.get("away_name", "N/A"); a_btn.add_theme_font_size_override("font_size", 18); a_btn.add_theme_color_override("font_color", _form_color(a_form)); a_btn.pressed.connect(_on_show_team_stats.bind(p.get("away_team_id", 0))); match_hb.add_child(a_btn)
	
	var v_pred = VBoxContainer.new(); v_pred.alignment = BoxContainer.ALIGNMENT_CENTER; v_pred.size_flags_horizontal = Control.SIZE_EXPAND_FILL; hb.add_child(v_pred)
	if p.get("selection") != null:
		var flow = HFlowContainer.new(); flow.alignment = FlowContainer.ALIGNMENT_CENTER; v_pred.add_child(flow)
		var choices = str(p["selection"]).split(" / ")
		var probs = str(p.get("probabilities", "")).split("|")
		for i in range(choices.size()):
			var choice_text = choices[i].strip_edges()
			if choice_text == "": continue
			var prob_text = ""
			if i < probs.size(): prob_text = " (%d%%)" % (float(probs[i]) * 100)
			var clbl = _lbl(choice_text + prob_text, COLOR_GOLD_BRIGHT); clbl.add_theme_font_size_override("font_size", 14); flow.add_child(clbl)
			if i < choices.size() - 1: flow.add_child(_lbl("  •  ", COLOR_TEXT_DIM))
	else:
		v_pred.add_child(_lbl("АНАЛІЗУЄТЬСЯ...", COLOR_TEXT_DIM))

	var v_odd = VBoxContainer.new(); v_odd.alignment = BoxContainer.ALIGNMENT_CENTER; v_odd.custom_minimum_size.x = 100; hb.add_child(v_odd)
	if p.get("bookmaker_odd") != null and p["bookmaker_odd"] > 0:
		v_odd.add_child(_lbl("%.2f" % p["bookmaker_odd"]))
		var val_pct = p.get("value_percentage", 0) * 100
		v_odd.add_child(_lbl("%+0.1f%%" % val_pct, COLOR_SUCCESS if val_pct > 0 else COLOR_DANGER))
	else:
		v_odd.add_child(_lbl("—", COLOR_TEXT_DIM))
	
	var btn = Button.new(); btn.text = " ТРЕКАТИ "; btn.custom_minimum_size = Vector2(110, 40); btn.pressed.connect(_on_record_pressed.bind(p)); hb.add_child(btn)
	return card

func _update_history():
	for child in history_vbox.get_children(): child.queue_free()
	
	var bets = db_viewer.fetch_user_bets()
	var matches = db_viewer.fetch_global_history()
	
	# Combine into a unified history stream
	var history_items = []
	for b in bets:
		b["h_type"] = "BET"
		history_items.append(b)
	for m in matches:
		# Check if we already have a bet for this match in the list (to avoid duplicates)
		var exists = false
		for b in bets:
			if b.has("match_id") and b["match_id"] == m["id"]: exists = true; break
		if not exists:
			m["h_type"] = "RESULT"
			history_items.append(m)
	
	# Sort by Date DESC (Newest first)
	history_items.sort_custom(func(a, b):
		var time_a = Time.get_unix_time_from_datetime_string(a["date"].replace(" ", "T").split("+")[0])
		var time_b = Time.get_unix_time_from_datetime_string(b["date"].replace(" ", "T").split("+")[0])
		return time_a > time_b
	)
	
	if history_items.size() == 0:
		history_vbox.add_child(_lbl("Історія порожня.", COLOR_TEXT_DIM)); return
		
	for item in history_items:
		if item["h_type"] == "BET":
			history_vbox.add_child(_create_history_card(item))
		else:
			history_vbox.add_child(_create_result_card(item))

func _create_history_card(b) -> PanelContainer:
	var card = PanelContainer.new()
	var style = StyleBoxFlat.new(); style.bg_color = COLOR_SURFACE; style.content_margin_left = 25; style.content_margin_right = 25; style.content_margin_top = 15; style.content_margin_bottom = 15
	style.set_corner_radius_all(10); style.border_width_left = 4; style.border_color = COLOR_GOLD
	card.add_theme_stylebox_override("panel", style)
	
	var hb = HBoxContainer.new(); hb.add_theme_constant_override("separation", 25); card.add_child(hb)
	hb.add_child(_lbl("💰 TRACK", COLOR_GOLD))
	
	var v_info = VBoxContainer.new(); v_info.size_flags_horizontal = Control.SIZE_EXPAND_FILL; hb.add_child(v_info)
	
	var m_name = _lbl(b["home_name"] + " — " + b["away_name"]); m_name.add_theme_font_size_override("font_size", 18); v_info.add_child(m_name)
	
	var pred_lbl = _lbl(b["selection"], COLOR_GOLD_BRIGHT)
	pred_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	pred_lbl.custom_minimum_size.x = 300
	v_info.add_child(pred_lbl)
	
	var status_color = COLOR_GOLD
	if b["status"] == "WON": status_color = COLOR_SUCCESS
	elif b["status"] == "LOST": status_color = COLOR_DANGER
	
	var status_lbl = _lbl(str(b["status"]), status_color)
	hb.add_child(status_lbl)
	
	var del_btn = Button.new(); del_btn.text = " ✕ "; del_btn.add_theme_color_override("font_color", COLOR_DANGER); del_btn.pressed.connect(_on_delete_bet.bind(b["id"])); hb.add_child(del_btn)
	return card

func _create_result_card(m) -> PanelContainer:
	var card = PanelContainer.new()
	var style = StyleBoxFlat.new(); style.bg_color = COLOR_GRAPHITE; style.content_margin_left = 25; style.content_margin_right = 25; style.content_margin_top = 15; style.content_margin_bottom = 15
	style.set_corner_radius_all(10); card.add_theme_stylebox_override("panel", style)
	
	var hb = HBoxContainer.new(); hb.add_theme_constant_override("separation", 25); card.add_child(hb)
	hb.add_child(_lbl("🏟 RESULT", COLOR_TEXT_DIM))
	
	var match_hb = HBoxContainer.new(); match_hb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	match_hb.size_flags_vertical = Control.SIZE_SHRINK_CENTER # Vertical center
	hb.add_child(match_hb)
	
	var h_btn = LinkButton.new(); h_btn.text = m["home_name"]; h_btn.add_theme_color_override("font_color", COLOR_GOLD); h_btn.pressed.connect(_on_show_team_stats.bind(m["home_team_id"])); match_hb.add_child(h_btn)
	
	var s_btn = LinkButton.new(); s_btn.text = "  " + str(m["home_score"]) + " : " + str(m["away_score"]) + "  "; s_btn.add_theme_color_override("font_color", COLOR_TEXT); s_btn.underline = LinkButton.UNDERLINE_MODE_NEVER; s_btn.pressed.connect(_on_show_analysis.bind(m)); match_hb.add_child(s_btn)
	
	var a_btn = LinkButton.new(); a_btn.text = m["away_name"]; a_btn.add_theme_color_override("font_color", COLOR_GOLD); a_btn.pressed.connect(_on_show_team_stats.bind(m["away_team_id"])); match_hb.add_child(a_btn)
	
	if m.has("ai_prediction") and m["ai_prediction"] != null:
		var pred_container = HFlowContainer.new()
		pred_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		hb.add_child(pred_container)
		
		var preds = str(m["ai_prediction"]).split(" / ")
		var hits = str(m["ai_hit"]).split("|")
		
		for i in range(preds.size()):
			var p_text = preds[i].strip_edges()
			if p_text == "": continue
			
			var is_hit = 0
			if i < hits.size(): is_hit = int(hits[i])
			
			var p_color = COLOR_SUCCESS if is_hit > 0 else COLOR_DANGER
			var p_lbl = _lbl(p_text, p_color)
			p_lbl.add_theme_font_size_override("font_size", 12)
			pred_container.add_child(p_lbl)
			
			if i < preds.size() - 1:
				var sep = _lbl(" • ", COLOR_TEXT_DIM)
				pred_container.add_child(sep)
		
		# Set a minimum width to force flow container to wrap its children
		pred_container.custom_minimum_size.x = 400
	
	var clean_date = _format_match_date(m["date"])
	hb.add_child(_lbl(clean_date, COLOR_TEXT_DIM))

	return card

func _on_search_changed(new_text: String):
	for child in search_vbox.get_children(): child.queue_free()
	if new_text.length() < 2: return
	
	var results = db_viewer.search_teams(new_text)
	if results.size() == 0:
		search_vbox.add_child(_lbl("Нічого не знайдено.", COLOR_TEXT_DIM))
		return
		
	for team in results:
		search_vbox.add_child(_create_team_search_card(team))

func _refresh_statistics(idx: int = 0):
	if not stats_chart_hb: return
	for c in stats_chart_hb.get_children(): c.queue_free()
	for c in stats_list_vb.get_children(): c.queue_free()
	
	var filter_str = "ALL"
	if idx == 1: filter_str = "1X2"
	elif idx == 2: filter_str = "TOTALS"
	elif idx == 3: filter_str = "CORNERS"
	elif idx == 4: filter_str = "CARDS"
	
	var stats = db_viewer.fetch_prediction_stats(filter_str)
	if stats["total"] == 0:
		stats_total_lbl.text = "Немає оцінених прогнозів для даного маркету."
		stats_total_lbl.add_theme_color_override("font_color", COLOR_TEXT_DIM)
		return
		
	var global_acc = (float(stats["hits"]) / float(stats["total"])) * 100.0
	stats_total_lbl.text = "🏆 ЗАГАЛЬНА ТОЧНІСТЬ: %.1f%% (%d / %d)" % [global_acc, stats["hits"], stats["total"]]
	stats_total_lbl.add_theme_color_override("font_color", COLOR_SUCCESS if global_acc >= 55 else (COLOR_DANGER if global_acc < 50 else COLOR_GOLD_BRIGHT))
	
	# Reverse days to show oldest to newest left to right in chart
	var days = stats["days"]
	var reversed_days = days.duplicate()
	reversed_days.reverse()
	
	for day in reversed_days:
		var acc = day["acc"]
		var bar_color = COLOR_SUCCESS if acc >= 55 else (COLOR_DANGER if acc < 50 else COLOR_GOLD)
		
		var vbox = VBoxContainer.new(); vbox.alignment = BoxContainer.ALIGNMENT_END; vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
		var lbl_pct = _lbl("%d%%" % acc, bar_color); lbl_pct.add_theme_font_size_override("font_size", 12); lbl_pct.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vbox.add_child(lbl_pct)
		
		# Max height is say 150px
		var rect = ColorRect.new()
		rect.color = bar_color
		rect.custom_minimum_size = Vector2(20, max(5.0, (acc / 100.0) * 150.0))
		vbox.add_child(rect)
		
		var day_text = day["date"].split("-")[2] if day["date"].split("-").size() == 3 else day["date"]
		var lbl_day = _lbl(day_text, COLOR_TEXT_DIM); lbl_day.add_theme_font_size_override("font_size", 12); lbl_day.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vbox.add_child(lbl_day)
		
		stats_chart_hb.add_child(vbox)
		
	# List from newest to oldest
	for day in days:
		var p = PanelContainer.new()
		var s = StyleBoxFlat.new(); s.bg_color = COLOR_SURFACE; s.set_corner_radius_all(8); s.content_margin_left=15; s.content_margin_right=15; s.content_margin_top=10; s.content_margin_bottom=10
		s.border_width_left = 4; s.border_color = COLOR_SUCCESS if day["acc"] >= 55 else (COLOR_DANGER if day["acc"] < 50 else COLOR_GOLD)
		p.add_theme_stylebox_override("panel", s)
		
		var hb = HBoxContainer.new(); p.add_child(hb)
		hb.add_child(_lbl(day["date"], COLOR_TEXT_DIM))
		var spacer = Control.new(); spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL; hb.add_child(spacer)
		hb.add_child(_lbl("Точність: %.1f%%" % day["acc"], s.border_color))
		hb.add_child(_lbl("  (Вгадано: %d / %d)" % [day["won"], day["total"]], COLOR_TEXT_DIM))
		
		stats_list_vb.add_child(p)

func _create_team_search_card(t) -> PanelContainer:
	var card = PanelContainer.new()
	var style = StyleBoxFlat.new(); style.bg_color = COLOR_SURFACE; style.content_margin_left = 25; style.content_margin_right = 25; style.content_margin_top = 15; style.content_margin_bottom = 15; style.set_corner_radius_all(10); card.add_theme_stylebox_override("panel", style)
	
	var hb = HBoxContainer.new(); hb.add_theme_constant_override("separation", 30); card.add_child(hb)
	
	var name_btn = LinkButton.new(); name_btn.text = t["name"]; name_btn.add_theme_color_override("font_color", COLOR_GOLD)
	name_btn.add_theme_font_size_override("font_size", 18); name_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_btn.pressed.connect(_on_show_team_stats.bind(t["id"])); hb.add_child(name_btn)
	
	var form_hb = HBoxContainer.new(); hb.add_child(form_hb)
	if t["current_form"]:
		for c in t["current_form"]:
			var circle = ColorRect.new(); circle.custom_minimum_size = Vector2(12, 12); circle.color = COLOR_SUCCESS if c == 'W' else (COLOR_DANGER if c == 'L' else COLOR_GOLD)
			form_hb.add_child(circle)
	
	hb.add_child(_lbl("Elo: " + str(int(t["elo_rating"])), COLOR_GOLD_BRIGHT))
	hb.add_child(_lbl("⚽ " + str(snapped(t["avg_scored"], 0.1)), COLOR_TEXT_DIM))
	return card

func _on_sync_pressed():
	if is_syncing: return
	
	var user = github_user_input.text
	var repo = github_repo_input.text
	
	# If we have GitHub credentials, prefer cloud sync even on desktop for testing
	if user != "" and repo != "":
		_sync_from_cloud()
		return
		
	# Detect if on Mobile
	if OS.get_name() == "Android" or OS.get_name() == "iOS":
		_sync_from_cloud()
		return

	is_syncing = true; refresh_btn.disabled = true; sync_status_lbl.text = "СИНХРОНІЗАЦІЯ... "
	var root_path = ProjectSettings.globalize_path("res://..")
	var err = OS.create_process("cmd.exe", ["/c", "start /wait \"\" \"" + root_path + "/START_SYNC.bat" + "\""])
	
	if err == -1: # Failed to start process (likely on non-Windows)
		_sync_from_cloud()
	else:
		await get_tree().create_timer(5.0).timeout
		_refresh_data()
		is_syncing = false; refresh_btn.disabled = false; sync_status_lbl.text = "ОНОВЛЕНО ✅"
		await get_tree().create_timer(3.0).timeout; sync_status_lbl.text = ""

func _sync_from_cloud():
	var user = github_user_input.text
	var repo = github_repo_input.text
	if user == "" or repo == "":
		sync_status_lbl.text = "ПОМИЛКА: Вкажіть GitHub User/Repo в налаштуваннях!"
		return
		
	is_syncing = true; refresh_btn.disabled = true; sync_status_lbl.text = "ХМАРНА СИНХРОНІЗАЦІЯ... ☁️"
	
	# Bypass GitHub cache by adding a random parameter
	var cache_buster = str(Time.get_unix_time_from_system())
	var url = "https://raw.githubusercontent.com/" + user + "/" + repo + "/main/python/logicbet_export.json?t=" + cache_buster
	
	var http = HTTPRequest.new(); add_child(http)
	http.request_completed.connect(func(_result, code, _headers, body):
		is_syncing = false; refresh_btn.disabled = false
		if code == 200:
			var json_data = JSON.parse_string(body.get_string_from_utf8())
			if json_data:
				_apply_cloud_data(json_data)
				sync_status_lbl.text = "ОНОВЛЕНО З ХМАРИ ✅"
			else:
				sync_status_lbl.text = "ПОМИЛКА ФОРМАТУ JSON"
		else:
			sync_status_lbl.text = "ПОМИЛКА ЗАВАНТАЖЕННЯ (Код: %d)" % code
		http.queue_free()
		await get_tree().create_timer(3.0).timeout; sync_status_lbl.text = ""
	)
	http.request(url)

func _apply_cloud_data(data):
	# 1. Sync the full JSON state into the local SQLite DB
	db_viewer.sync_from_json(data)
	
	# 2. Refresh the UI from the newly updated local DB
	_refresh_data()

func _update_dashboard_with_data(matches):
	for child in dash_vbox.get_children(): child.queue_free()
	# ... similar to _update_dashboard but using passed matches list ...
	var last_date = ""
	for p in matches:
		var current_date = p["date"].split("T")[0]
		if current_date != last_date:
			var header_panel = PanelContainer.new()
			var style = StyleBoxFlat.new(); style.bg_color = COLOR_GRAPHITE; style.set_corner_radius_all(10); style.content_margin_left = 15; style.content_margin_top = 10; style.content_margin_bottom = 10
			header_panel.add_theme_stylebox_override("panel", style)
			var header_lbl = _lbl("📆 ПЛАН НА " + current_date, COLOR_GOLD); header_lbl.add_theme_font_size_override("font_size", 18); header_panel.add_child(header_lbl)
			dash_vbox.add_child(header_panel)
			last_date = current_date
		dash_vbox.add_child(_create_match_card(p))

func _on_record_pressed(p_data):
	current_match_id = int(p_data["match_id"]); current_selection = p_data["selection"]; ai_odd = p_data["bookmaker_odd"]
	match_confirm_lbl.text = p_data["home_name"] + " — " + p_data["away_name"] + "\nПрогноз: " + current_selection
	odd_input.value = ai_odd if ai_odd > 0 else 1.95; stake_input.value = db_viewer.get_default_stake()
	bet_dialog.popup_centered()

func _on_bet_confirmed():
	db_viewer.record_bet(current_match_id, current_selection, stake_input.value, odd_input.value); _refresh_data()

func _on_delete_bet(bet_id):
	db_viewer.delete_user_bet(bet_id); _refresh_data()

func _on_save_settings():
	db_viewer.set_bankroll(settings_bank_input.value)
	db_viewer.set_default_stake(settings_stake_input.value)
	db_viewer.set_config("github_user", github_user_input.text)
	db_viewer.set_config("github_repo", github_repo_input.text)
	_refresh_data()
	
	sync_status_lbl.text = "НАЛАШТУВАННЯ ЗБЕРЕЖЕНО ✅"
	await get_tree().create_timer(2.0).timeout
	sync_status_lbl.text = ""


func _on_show_analysis(p):
	var content = analysis_popup.get_meta("content_vbox")
	for c in content.get_children(): c.queue_free()
	
	analysis_popup.min_size = Vector2i(950, 600)
	analysis_popup.size = analysis_popup.min_size
	
	var t = Label.new(); t.text = "ДЕТАЛЬНИЙ АНАЛІЗ ШІ"; t.add_theme_font_size_override("font_size", 22); t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER; content.add_child(t)
	content.add_spacer(false)
	
	var h_elo = "1500"; var a_elo = "1500"; var h2h_count = "0"
	if p.has("h_elo_live") and p["h_elo_live"] != null:
		h_elo = str(int(p["h_elo_live"]))
		a_elo = str(int(p["a_elo_live"]))
	elif p.has("algorithm") and p["algorithm"] != "":
		var algo_parts = p["algorithm"].split("|")
		if algo_parts.size() >= 3:
			h_elo = algo_parts[1].split(":")[1]
			a_elo = algo_parts[2].split(":")[1]
		if "H2H:" in p["algorithm"]:
			h2h_count = p["algorithm"].split("H2H:")[1]

	if int(h2h_count) > 0:
		var h2h_lbl = _lbl("Враховано " + h2h_count + " очних зустрічей (H2H)", COLOR_TEXT_DIM)
		h2h_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		content.add_child(h2h_lbl)

	var h_form_str = p.get("form_home", null)
	var a_form_str = p.get("form_away", null)
	
	# Master Grid for absolute alignment
	var grid = GridContainer.new(); grid.columns = 3; grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 0); grid.add_theme_constant_override("v_separation", 15)
	content.add_child(grid)

	# Row 1: Names & Elo
	var h_elo_row = HBoxContainer.new(); h_elo_row.alignment = BoxContainer.ALIGNMENT_END
	h_elo_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL; h_elo_row.size_flags_stretch_ratio = 1.0 
	h_elo_row.custom_minimum_size.x = 320 # Fixed base for symmetry
	var h_btn = LinkButton.new(); h_btn.text = p["home_name"]; h_btn.add_theme_color_override("font_color", _form_color(h_form_str)); h_btn.pressed.connect(_on_show_team_stats.bind(p["home_team_id"])); h_elo_row.add_child(h_btn)
	h_elo_row.add_child(_lbl(" ( ", COLOR_TEXT_DIM))
	h_elo_row.add_child(_lbl(h_elo, COLOR_TEXT_DIM))
	if p.has("h_elo_change") and str(p["h_elo_change"]) != "" and float(p["h_elo_change"]) != 0:
		var d = float(p["h_elo_change"])
		var c = COLOR_SUCCESS if d > 0 else COLOR_DANGER
		h_elo_row.add_child(_lbl(" " + ("+" if d > 0 else "") + str(snapped(d, 0.1)), c))
	h_elo_row.add_child(_lbl(" )", COLOR_TEXT_DIM))
	
	var vs_text = "vs"
	var is_final = p.has("home_score") and p["home_score"] != null
	if is_final:
		vs_text = "%d : %d" % [int(p["home_score"]), int(p["away_score"])]
		
	var vs_lbl = _lbl(vs_text, COLOR_GOLD)
	vs_lbl.custom_minimum_size.x = 220
	vs_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vs_lbl.add_theme_font_size_override("font_size", 48 if is_final else 28)
	
	var a_elo_row = HBoxContainer.new(); a_elo_row.alignment = BoxContainer.ALIGNMENT_BEGIN
	a_elo_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL; a_elo_row.size_flags_stretch_ratio = 1.0
	a_elo_row.custom_minimum_size.x = 320 # Identical base
	var a_btn = LinkButton.new(); a_btn.text = p["away_name"]; a_btn.add_theme_color_override("font_color", _form_color(a_form_str)); a_btn.pressed.connect(_on_show_team_stats.bind(p["away_team_id"])); a_elo_row.add_child(a_btn)
	a_elo_row.add_child(_lbl(" ( ", COLOR_TEXT_DIM))
	a_elo_row.add_child(_lbl(a_elo, COLOR_TEXT_DIM))
	if p.has("a_elo_change") and str(p["a_elo_change"]) != "" and float(p["a_elo_change"]) != 0:
		var d = float(p["a_elo_change"])
		var c = COLOR_SUCCESS if d > 0 else COLOR_DANGER
		a_elo_row.add_child(_lbl(" " + ("+" if d > 0 else "") + str(snapped(d, 0.1)), c))
	a_elo_row.add_child(_lbl(" )", COLOR_TEXT_DIM))
	
	grid.add_child(h_elo_row); grid.add_child(vs_lbl); grid.add_child(a_elo_row)

	
	# Row 3: Statistics Header
	if p.has("corners_h") and p["status"] != "NS":
		grid.add_child(Control.new())
		var s_title = _lbl("📊 СТАТИСТИКА МАТЧУ", COLOR_GOLD); s_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		grid.add_child(s_title)
		grid.add_child(Control.new())
		
		# Stats Rows
		_add_grid_row(grid, "УДАРИ В ПЛОЩИНУ", p.get("shots_on_h", 0), p.get("shots_on_a", 0))
		_add_grid_row(grid, "КУТОВІ", p.get("corners_h", 0), p.get("corners_a", 0))
		_add_grid_row(grid, "ЖОВТІ КАРТКИ", p.get("yellow_cards_h", 0), p.get("yellow_cards_a", 0))
		_add_grid_row(grid, "ЧЕРВОНІ КАРТКИ", p.get("red_cards_h", 0), p.get("red_cards_a", 0))
		_add_grid_row(grid, "ВОЛОДІННЯ (%)", p.get("possession_h", 50), p.get("possession_a", 50))
		_add_grid_row(grid, "УДАРИ", p.get("shots_on_h", 0), p.get("shots_on_a", 0))
		_add_grid_row(grid, "xG", p.get("xg_h", 0.0), p.get("xg_a", 0.0))
	
	content.add_child(HSeparator.new())
	
	# Predictions Section
	content.add_child(_lbl("🤖 ШІ-ПРОГНОЗИ (Мульти-маркет)", COLOR_GOLD))
	var match_id_for_preds = p.get("match_id", -1)
	if match_id_for_preds == -1 and p.has("id"): match_id_for_preds = p["id"]
	
	var preds = db_viewer.fetch_match_predictions(match_id_for_preds)
	if preds.size() > 0:
		var p_grid = GridContainer.new(); p_grid.columns = 2; p_grid.add_theme_constant_override("h_separation", 30); p_grid.add_theme_constant_override("v_separation", 10)
		content.add_child(p_grid)
		for pr in preds:
			var pr_info = HBoxContainer.new(); pr_info.alignment = BoxContainer.ALIGNMENT_BEGIN; pr_info.add_theme_constant_override("separation", 10)
			pr_info.add_child(_lbl("• " + pr["market"] + ":", COLOR_TEXT_DIM))
			pr_info.add_child(_lbl(pr["selection"], COLOR_GOLD_BRIGHT))
			p_grid.add_child(pr_info)
			
			var prob_lbl = _lbl("%.1f%% Ймовірність" % (float(pr["calculated_prob"]) * 100), COLOR_TEXT)
			p_grid.add_child(prob_lbl)
	else:
		content.add_child(_lbl("Оновіть синхронізацію для отримання прогнозів", COLOR_TEXT_DIM))
	
	analysis_popup.popup_centered()

func _add_grid_row(grid: GridContainer, label_text: String, val_h, val_a):
	var l_h = _lbl(str(val_h), COLOR_GOLD_BRIGHT if float(val_h) > float(val_a) else COLOR_TEXT)
	l_h.add_theme_font_size_override("font_size", 18); l_h.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	grid.add_child(l_h)
	
	var l_mid = _lbl(label_text, COLOR_TEXT_DIM)
	l_mid.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	grid.add_child(l_mid)
	
	var l_a = _lbl(str(val_a), COLOR_GOLD_BRIGHT if float(val_a) > float(val_h) else COLOR_TEXT)
	l_a.add_theme_font_size_override("font_size", 18); l_a.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	grid.add_child(l_a)

func _format_match_date(utc_date_str: String) -> String:
	# API returns formats like "2024-03-24T15:00:00Z" or "2024-03-24 15:00:00+00:00"
	var clean_str = utc_date_str.replace("Z", "").replace(" ", "T").split("+")[0]
	var unix_time = Time.get_unix_time_from_datetime_string(clean_str)
	
	# Kyiv Time Zone Adjustment (+2 Winter, +3 Summer)
	var date_dict = Time.get_datetime_dict_from_unix_time(unix_time)
	var offset = 2 # Winter base
	
	# Simple DST check for Ukraine: Summer time is Last Sunday of March to Last Sunday of October
	# (Approximate: April to September is definitely Summer +3)
	if date_dict["month"] > 3 and date_dict["month"] < 11:
		offset = 3
	elif date_dict["month"] == 3 and date_dict["day"] >= 25: # End of March
		offset = 3
	elif date_dict["month"] == 10 and date_dict["day"] < 25: # Start of October
		offset = 3
		
	var local_unix = unix_time + (offset * 3600)
	var local_dict = Time.get_datetime_dict_from_unix_time(local_unix)
	
	return "%04d-%02d-%02d %02d:%02d" % [local_dict["year"], local_dict["month"], local_dict["day"], local_dict["hour"], local_dict["minute"]]

func _lbl(txt, color = COLOR_TEXT) -> Label:
	var l = Label.new(); l.text = str(txt); l.add_theme_color_override("font_color", color); return l

func _on_show_team_stats(team_id):
	var data = db_viewer.fetch_team_stats_report(int(team_id))
	if data.is_empty(): return
	
	var content = team_popup.get_meta("content_vbox")
	for c in content.get_children(): c.queue_free()
	
	# Header
	var hb_head = HBoxContainer.new()
	var name_lbl = _lbl(data["info"]["name"], COLOR_GOLD)
	name_lbl.add_theme_font_size_override("font_size", 32)
	hb_head.add_child(name_lbl)
	hb_head.add_child(_lbl("  |  Elo: " + str(int(data["info"]["elo_rating"])), COLOR_GOLD_BRIGHT))
	
	var rank = data["info"].get("rank", 0)
	if rank > 0:
		hb_head.add_child(_lbl("  |  Місце: " + str(rank), COLOR_SUCCESS))
		
	content.add_child(hb_head)
	
	# Form row
	var hb_form = HBoxContainer.new(); hb_form.add_theme_constant_override("separation", 10)
	hb_form.add_child(_lbl("ОСТАННЯ ФОРМА (10 ігор): ", COLOR_TEXT_DIM))
	var form_str = data["info"].get("current_form", "")
	for c in form_str:
		var circle = ColorRect.new(); circle.custom_minimum_size = Vector2(24, 24)
		circle.color = COLOR_SUCCESS if c == 'W' else (COLOR_DANGER if c == 'L' else COLOR_GOLD)
		hb_form.add_child(circle)
		var l = Label.new(); l.text = c; l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER; l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER; circle.add_child(l)
		l.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	content.add_child(hb_form)
	
	# Section 1: РЕЗУЛЬТАТИ (Останні 10)
	content.add_child(_lbl("📊 ПІДСУМКИ МАТЧІВ", COLOR_GOLD))
	var hb_results = HBoxContainer.new(); hb_results.add_theme_constant_override("separation", 60)
	content.add_child(hb_results)
	_add_stat_box_simple(hb_results, "ПЕРЕМОГИ", str(data["wins"]), COLOR_SUCCESS)
	_add_stat_box_simple(hb_results, "НІЧИЇ", str(data["draws"]), COLOR_GOLD)
	_add_stat_box_simple(hb_results, "ПОРАЗКИ", str(data["losses"]), COLOR_DANGER)
	
	# Section 2: РЕЗУЛЬТАТИВНІСТЬ
	content.add_child(_lbl("⚽ АТАКА ТА ЗАХИСТ (В середньому)", COLOR_GOLD))
	var hb_goals = HBoxContainer.new(); hb_goals.add_theme_constant_override("separation", 60)
	content.add_child(hb_goals)
	_add_stat_box_simple(hb_goals, "ЗАБИТО", "%.1f" % data["gs"], COLOR_GOLD_BRIGHT)
	_add_stat_box_simple(hb_goals, "ПРОПУЩЕНО", "%.1f" % data["gc"], COLOR_TEXT_DIM)
	_add_stat_box_simple(hb_goals, "ОЧІКУВАНІ (xG)", "%.2f" % data["xg"], COLOR_GOLD)
	
	# Section 3: АКТИВНІСТЬ
	content.add_child(_lbl("📈 ІГРОВА СТАТИСТИКА (В середньому)", COLOR_GOLD))
	var hb_activity = HBoxContainer.new(); hb_activity.add_theme_constant_override("separation", 60)
	content.add_child(hb_activity)
	_add_stat_box_simple(hb_activity, "КУТОВІ", "%.1f" % data["corners"], COLOR_TEXT)
	_add_stat_box_simple(hb_activity, "УДАРИ", "%.1f" % data["shots"], COLOR_TEXT)
	_add_stat_box_simple(hb_activity, "ЖОВТІ", "%.1f" % data["yellow_cards"], COLOR_GOLD)
	_add_stat_box_simple(hb_activity, "ЧЕРВОНІ", "%.1f" % data["red_cards"], COLOR_DANGER)
	
	# Last Matches List
	content.add_spacer(false)
	content.add_child(_lbl("📜 ОСТАННІ МАТЧІ", COLOR_GOLD))
	var v_matches = VBoxContainer.new(); v_matches.add_theme_constant_override("separation", 10); content.add_child(v_matches)
	
	for m in data["matches"]:
		var p_item = PanelContainer.new()
		var style = StyleBoxFlat.new(); style.bg_color = COLOR_GRAPHITE; style.set_content_margin_all(10); style.set_corner_radius_all(8)
		p_item.add_theme_stylebox_override("panel", style)
		var hb = HBoxContainer.new(); p_item.add_child(hb)
		hb.add_child(_lbl(m["date"].split(" ")[0].split("T")[0], COLOR_TEXT_DIM))
		
		var m_text = _lbl("  %s %d : %d %s" % [m["h_name"], m["home_score"], m["away_score"], m["a_name"]], COLOR_TEXT)
		m_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL; hb.add_child(m_text)
		v_matches.add_child(p_item)
		
	team_popup.popup_centered()

func _add_stat_box_simple(parent, title, val, color):
	var v = VBoxContainer.new(); parent.add_child(v)
	v.add_child(_lbl(title, COLOR_TEXT_DIM))
	var l = _lbl(val, color); l.add_theme_font_size_override("font_size", 28); v.add_child(l)

func _add_stat_box(grid, title, val, color):
	var v = VBoxContainer.new(); grid.add_child(v)
	v.add_child(_lbl(title, COLOR_TEXT_DIM))
	var l = _lbl(val, color); l.add_theme_font_size_override("font_size", 24); v.add_child(l)

func _form_color(form) -> Color:
	if form == null or str(form) == "" or str(form) == "null" or str(form) == "<null>":
		return COLOR_GOLD
	return COLOR_GOLD
