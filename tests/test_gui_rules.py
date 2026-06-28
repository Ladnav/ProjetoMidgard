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
    profiles_page.heal_enabled.setChecked(True)
    profiles_page.heal_hp_threshold.setValue(85)
    profiles_page.heal_hp_key.setCurrentText("F4")
    profiles_page.heal_hp_x.setValue(220)
    profiles_page.heal_hp_y.setValue(110)

    profiles_page.consumables_enabled.setChecked(True)
    profiles_page.consumables_text.setPlainText("berserk_potion,F5,180.0")

    profiles_page.combat_enabled.setChecked(True)
    profiles_page.combat_target_r.setValue(200)
    profiles_page.combat_target_g.setValue(50)
    profiles_page.combat_target_b.setValue(50)

    profiles_page.nav_enabled.setChecked(True)
    profiles_page.nav_waypoints_text.setPlainText("150,150,2.5;300,300,5.0")

    # Save via GUI
    profiles_page._save_profile_rules()
    app.processEvents()

    # 4. Assert saved rules in database
    db_profile = store.get_profile(profile_id)
    assert db_profile is not None
    assert db_profile.name == "Odin"

    healing_rules = db_profile.rules.get("healing", {})
    assert healing_rules.get("heal.enabled") == "true"
    assert healing_rules.get("heal.hp_threshold") == "85"
    assert healing_rules.get("heal.hp_key") == "F4"
    assert healing_rules.get("heal.hp_x") == "220"
    assert healing_rules.get("heal.hp_y") == "110"

    consumables_rules = db_profile.rules.get("consumables", {})
    assert consumables_rules.get("consumables.enabled") == "true"
    assert consumables_rules.get("consumables.items") == "berserk_potion,F5,180.0"

    combat_rules = db_profile.rules.get("combat", {})
    assert combat_rules.get("combat.enabled") == "true"
    assert combat_rules.get("combat.target_r") == "200"
    assert combat_rules.get("combat.target_g") == "50"
    assert combat_rules.get("combat.target_b") == "50"

    navigation_rules = db_profile.rules.get("navigation", {})
    assert navigation_rules.get("navigation.enabled") == "true"
    assert navigation_rules.get("navigation.waypoints") == "150,150,2.5;300,300,5.0"

    # Close resources
    window.close()
    store.close()
    settings.close()
