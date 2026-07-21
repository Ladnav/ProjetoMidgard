"""Tests for the navigation route preview widget."""

import sys

import pytest
from PySide6.QtWidgets import QApplication

from midgard.ui.pages import NavigationMapView


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


def test_set_waypoints_normalises_to_int_tuples(app) -> None:
    view = NavigationMapView()
    assert view.waypoints == []

    view.set_waypoints([(10.0, 20.0), (30, 40)])
    assert view.waypoints == [(10, 20), (30, 40)]


def test_render_empty_does_not_raise(app) -> None:
    from PySide6.QtGui import QPixmap

    view = NavigationMapView()
    view.resize(420, 360)
    view.render(QPixmap(420, 360))  # forces paintEvent with no waypoints


def test_render_route_does_not_raise(app) -> None:
    from PySide6.QtGui import QPixmap

    view = NavigationMapView()
    view.resize(420, 360)
    view.set_waypoints([(100, 100), (400, 120), (250, 380), (100, 100)])
    view.render(QPixmap(420, 360))


def test_render_single_and_collinear_points(app) -> None:
    """Degenerate routes (one point, or a straight line) must not divide by zero."""
    from PySide6.QtGui import QPixmap

    view = NavigationMapView()
    view.resize(420, 360)

    view.set_waypoints([(200, 200)])
    view.render(QPixmap(420, 360))

    view.set_waypoints([(0, 100), (0, 200), (0, 300)])  # zero span on X
    view.render(QPixmap(420, 360))


def test_preview_reuses_runtime_waypoint_parser(app) -> None:
    """The preview handler parses waypoints the same way the engine does."""
    from midgard.runtime.input import DummyInputAdapter
    from midgard.runtime.navigation import NavigationModule

    module = NavigationModule(
        {"navigation.enabled": "true", "navigation.waypoints": "200,200,3.0;400,200,4.0"},
        DummyInputAdapter(),
        hwnd=0,
    )
    waypoints = [(wx, wy) for wx, wy, _wait in module.waypoints]
    assert waypoints == [(200, 200), (400, 200)]
