"""Tests for Studio Dashboard Statistics and Searchable Log Pages."""

from midgard.application import create_application


def test_logs_page_text_filter(tmp_path) -> None:
    """LogsPage search query dynamically filters logs list."""
    app, window, settings = create_application([], data_directory=tmp_path)
    log_file = window._pages["Logs"].log_path

    # Write sample diagnostic lines
    log_content = (
        "[INFO] User logged in\n[WARNING] Low health detected\n[ERROR] Network connection failed\n"
    )
    log_file.write_text(log_content, encoding="utf-8")

    page = window._pages["Logs"]
    page._load_and_filter_logs()
    app.processEvents()

    # Initial load: all 3 lines are shown
    assert "User logged in" in page.log_viewer.toPlainText()
    assert "Low health" in page.log_viewer.toPlainText()

    # Search filter: "network"
    page.search_input.setText("network")
    app.processEvents()
    assert "Network connection failed" in page.log_viewer.toPlainText()
    assert "User logged in" not in page.log_viewer.toPlainText()

    # Level filter: ERROR
    page.search_input.setText("")
    page.level_combo.setCurrentIndex(3)  # ERROR index
    app.processEvents()
    assert "Network connection" in page.log_viewer.toPlainText()
    assert "Low health" not in page.log_viewer.toPlainText()

    window.close()


def test_logs_page_clear_action(tmp_path) -> None:
    """LogsPage clear button truncates logs file."""
    app, window, settings = create_application([], data_directory=tmp_path)
    log_file = window._pages["Logs"].log_path
    log_file.write_text("diagnostics info", encoding="utf-8")

    page = window._pages["Logs"]
    page._load_and_filter_logs()
    app.processEvents()
    assert "diagnostics info" in page.log_viewer.toPlainText()

    page._clear_log_file()
    app.processEvents()
    assert "No logs matched" in page.log_viewer.toPlainText()
    assert log_file.read_text() == ""

    window.close()


def test_statistics_page_displays_profile_stats(tmp_path) -> None:
    """StatisticsPage populates fields using SQLite Profile statistics."""
    app, window, settings = create_application([], data_directory=tmp_path)
    store = window.profile_store
    pid = store.create_profile("PlayerStats")

    # Save mock statistics
    store.update_stats(
        profile_id=pid,
        experience_gained=5000,
        deaths=2,
        loot_count=120,
        runtime_seconds=600.0,  # 10 minutes
    )

    page = window._pages["Statistics"]
    page._refresh_profiles()
    page.profile_combo.setCurrentIndex(page.profile_combo.findData(pid))
    page._load_statistics()
    app.processEvents()

    assert "5000 XP" in page.xp_card.text()
    assert "120 items" in page.loot_card.text()
    assert "2 deaths" in page.deaths_card.text()
    assert "10.0 minutes" in page.time_card.text()

    window.close()
