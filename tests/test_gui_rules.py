from unittest.mock import MagicMock

from PySide6.QtWidgets import QMessageBox

from midgard.application import create_application


def test_profiles_gui_rules_loading_and_saving(tmp_path) -> None:
    """The ProfilesPage allows creating profiles and editing/saving rules."""
    # Mock QMessageBox methods to prevent blocking on modal popups
    QMessageBox.information = MagicMock()
    QMessageBox.warning = MagicMock()
    QMessageBox.critical = MagicMock()
    app, window, settings = create_application([], data_directory=tmp_path)
    store = window.profile_store

    profiles_page = window._pages["Profiles"]

    # 1. Assert initial state: combo is empty
    assert profiles_page.profile_combo.count() == 0

    # 2. Create a new profile via the GUI input
    profiles_page.new_profile_input.setText("Odin")
    profiles_page._create_new_profile()
    app.processEvents()

    # Check database and UI selection
    assert profiles_page.profile_combo.count() == 1
    assert profiles_page.profile_combo.currentText() == "Odin"

    profile_id = profiles_page.profile_combo.currentData()
    assert profile_id is not None

    # Check default loaded values
    assert not profiles_page.heal_enabled.isChecked()
    assert profiles_page.heal_hp_threshold.value() == 70
    assert profiles_page.heal_hp_key.currentText() == "F1"

    # 3. Edit rules in UI
    profiles_page.window_title_input.setText("Ragnarok Classic")
    profiles_page.heal_enabled.setChecked(True)
    profiles_page.heal_hp_threshold.setValue(85)
    profiles_page.heal_hp_key.setCurrentText("F4")
    profiles_page.heal_hp_x.setValue(100)
    profiles_page.heal_hp_y.setValue(110)
    profiles_page.heal_hp_w.setValue(60)
    profiles_page.heal_hp_h.setValue(12)

    profiles_page.heal_sp_enabled.setChecked(True)
    profiles_page.heal_sp_threshold.setValue(40)
    profiles_page.heal_sp_key.setCurrentText("F3")
    profiles_page.heal_sp_x.setValue(100)
    profiles_page.heal_sp_y.setValue(120)
    profiles_page.heal_sp_w.setValue(60)
    profiles_page.heal_sp_h.setValue(12)

    profiles_page.consumables_enabled.setChecked(True)
    profiles_page.consumables_text.setPlainText("berserk_potion,F5,180.0")
    profiles_page.status_bar_enabled.setChecked(True)
    profiles_page.status_check_x.setValue(60)
    profiles_page.status_check_y.setValue(60)
    profiles_page.status_color_r.setValue(250)
    profiles_page.status_color_g.setValue(250)
    profiles_page.status_color_b.setValue(250)

    profiles_page.combat_enabled.setChecked(True)
    profiles_page.combat_target_r.setValue(200)
    profiles_page.combat_target_g.setValue(50)
    profiles_page.combat_target_b.setValue(50)
    
    # Edit OpenCV rules in UI
    idx = profiles_page.combat_scanning_mode.findData("template")
    if idx >= 0:
        profiles_page.combat_scanning_mode.setCurrentIndex(idx)
    profiles_page.combat_template_dir.setText("templates/monsters/")
    profiles_page.combat_template_threshold.setValue(0.75)
    profiles_page.combat_priority_enabled.setChecked(True)
    profiles_page.combat_hover_offset_y.setValue(-45)
    profiles_page.combat_hover_box_w.setValue(30)
    profiles_page.combat_hover_box_h.setValue(8)

    profiles_page.nav_enabled.setChecked(True)
    profiles_page.nav_waypoints_text.setPlainText("150,150,2.5;300,300,5.0")
    profiles_page.nav_transition_enabled.setChecked(True)
    profiles_page.nav_current_map.setText("prt_fild08")
    profiles_page.nav_target_map.setText("prt_fild05")
    profiles_page.nav_transitions_text.setPlainText("prt_fild08:prt_fild05:360:20:5.0")

    # Edit Looting rules in UI
    profiles_page.loot_enabled.setChecked(True)
    profiles_page.loot_color_r.setValue(210)
    profiles_page.loot_color_g.setValue(215)
    profiles_page.loot_color_b.setValue(225)
    profiles_page.loot_color_tolerance.setValue(10)
    profiles_page.loot_cooldown.setValue(2.5)
    
    loot_filt_idx = profiles_page.loot_filter_mode.findData("rare_only")
    if loot_filt_idx >= 0:
        profiles_page.loot_filter_mode.setCurrentIndex(loot_filt_idx)
    profiles_page.loot_rare_color_r.setValue(255)
    profiles_page.loot_rare_color_g.setValue(10)
    profiles_page.loot_rare_color_b.setValue(10)
    profiles_page.loot_rare_tolerance.setValue(25)

    # Edit Security rules in UI
    profiles_page.sec_enabled.setChecked(True)
    profiles_page.sec_templates_dir.setText("templates/security/")
    profiles_page.sec_threshold.setValue(0.9)
    sec_idx = profiles_page.sec_panic_action.findData("teleport")
    if sec_idx >= 0:
        profiles_page.sec_panic_action.setCurrentIndex(sec_idx)
    profiles_page.sec_panic_hotkey.setText("F11")
    profiles_page.sec_discord_webhook.setText("https://discord.com/api/webhooks/123")

    # Edit Stash rules in UI
    profiles_page.stash_enabled.setChecked(True)
    profiles_page.stash_teleport_hotkey.setText("F10")
    profiles_page.stash_kafra_x.setValue(450)
    profiles_page.stash_kafra_y.setValue(400)
    profiles_page.stash_weight_check_x.setValue(580)
    profiles_page.stash_weight_check_y.setValue(75)
    profiles_page.stash_restock_enabled.setChecked(True)
    profiles_page.stash_merchant_x.setValue(380)
    profiles_page.stash_merchant_y.setValue(380)

    # Save via GUI
    profiles_page._save_profile_rules()
    app.processEvents()

    # 4. Assert saved rules in database
    db_profile = store.get_profile(profile_id)
    assert db_profile is not None
    assert db_profile.window_title == "Ragnarok Classic"

    healing_rules = db_profile.rules.get("healing", {})
    assert healing_rules.get("heal.enabled") == "true"
    assert healing_rules.get("heal.hp_threshold") == "85"
    assert healing_rules.get("heal.hp_key") == "F4"
    assert healing_rules.get("heal.hp_x") == "100"
    assert healing_rules.get("heal.hp_y") == "110"
    assert healing_rules.get("heal.hp_w") == "60"
    assert healing_rules.get("heal.hp_h") == "12"

    assert healing_rules.get("heal.sp_enabled") == "true"
    assert healing_rules.get("heal.sp_threshold") == "40"
    assert healing_rules.get("heal.sp_key") == "F3"
    assert healing_rules.get("heal.sp_x") == "100"
    assert healing_rules.get("heal.sp_y") == "120"
    assert healing_rules.get("heal.sp_w") == "60"
    assert healing_rules.get("heal.sp_h") == "12"

    consumables_rules = db_profile.rules.get("consumables", {})
    assert consumables_rules.get("consumables.enabled") == "true"
    assert consumables_rules.get("consumables.items") == "berserk_potion,F5,180.0"
    assert consumables_rules.get("consumables.status_bar_enabled") == "true"
    assert consumables_rules.get("consumables.status_check_x") == "60"
    assert consumables_rules.get("consumables.status_check_y") == "60"
    assert consumables_rules.get("consumables.status_color_r") == "250"
    assert consumables_rules.get("consumables.status_color_g") == "250"
    assert consumables_rules.get("consumables.status_color_b") == "250"

    looting_rules = db_profile.rules.get("looting", {})
    assert looting_rules.get("loot.enabled") == "true"
    assert looting_rules.get("loot.color.r") == "210"
    assert looting_rules.get("loot.color.g") == "215"
    assert looting_rules.get("loot.color.b") == "225"
    assert looting_rules.get("loot.color.tolerance") == "10"
    assert looting_rules.get("loot.cooldown") == "2.5"
    assert looting_rules.get("loot.filter_mode") == "rare_only"
    assert looting_rules.get("loot.rare_color.r") == "255"
    assert looting_rules.get("loot.rare_color.g") == "10"
    assert looting_rules.get("loot.rare_color.b") == "10"
    assert looting_rules.get("loot.rare_tolerance") == "25"

    combat_rules = db_profile.rules.get("combat", {})
    assert combat_rules.get("combat.enabled") == "true"
    assert combat_rules.get("combat.target_r") == "200"
    assert combat_rules.get("combat.target_g") == "50"
    assert combat_rules.get("combat.target_b") == "50"
    assert combat_rules.get("combat.scanning_mode") == "template"
    assert combat_rules.get("combat.template_dir") == "templates/monsters/"
    assert combat_rules.get("combat.template_threshold") == "0.75"
    assert combat_rules.get("combat.priority_enabled") == "true"
    assert combat_rules.get("combat.hover_offset_y") == "-45"
    assert combat_rules.get("combat.hover_box_w") == "30"
    assert combat_rules.get("combat.hover_box_h") == "8"

    navigation_rules = db_profile.rules.get("navigation", {})
    assert navigation_rules.get("navigation.enabled") == "true"
    assert navigation_rules.get("navigation.waypoints") == "150,150,2.5;300,300,5.0"
    assert navigation_rules.get("navigation.transition_enabled") == "true"
    assert navigation_rules.get("navigation.current_map") == "prt_fild08"
    assert navigation_rules.get("navigation.target_map") == "prt_fild05"
    assert navigation_rules.get("navigation.transitions") == "prt_fild08:prt_fild05:360:20:5.0"

    security_rules = db_profile.rules.get("security", {})
    assert security_rules.get("security.enabled") == "true"
    assert security_rules.get("security.templates_dir") == "templates/security/"
    assert security_rules.get("security.threshold") == "0.9"
    assert security_rules.get("security.panic_action") == "teleport"
    assert security_rules.get("security.panic_hotkey") == "F11"
    assert security_rules.get("security.discord_webhook") == "https://discord.com/api/webhooks/123"

    stash_rules = db_profile.rules.get("stash", {})
    assert stash_rules.get("stash.enabled") == "true"
    assert stash_rules.get("stash.teleport_hotkey") == "F10"
    assert stash_rules.get("stash.kafra_x") == "450"
    assert stash_rules.get("stash.kafra_y") == "400"
    assert stash_rules.get("stash.weight_check_x") == "580"
    assert stash_rules.get("stash.weight_check_y") == "75"
    assert stash_rules.get("stash.restock_enabled") == "true"
    assert stash_rules.get("stash.merchant_x") == "380"
    assert stash_rules.get("stash.merchant_y") == "380"

    # Close resources
    window.close()
    store.close()
    settings.close()
