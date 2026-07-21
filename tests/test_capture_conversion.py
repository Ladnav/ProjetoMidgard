"""Regression tests for PIL <-> QPixmap conversion in the Profiles capture path."""

import sys

import pytest
from PIL import Image
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from midgard.ui.pages import ProfilesPage


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


def test_pil_to_qpixmap_uses_int_attributes(app) -> None:
    """PIL width/height are attributes; calling them raised 'int' object is not callable.

    Regression: the game-window capture built a QImage with pil_img.width() /
    pil_img.height(), which threw and forced the primary-screen fallback for
    every pick/verify action.
    """
    pil = Image.new("RGB", (37, 21), color=(10, 20, 30))
    pixmap = ProfilesPage._pil_to_qpixmap(pil)

    assert isinstance(pixmap, QPixmap)
    assert pixmap.width() == 37
    assert pixmap.height() == 21


def test_pil_to_qpixmap_round_trips_through_pixmap_to_pil(app) -> None:
    """Converting PIL -> QPixmap -> PIL preserves the dimensions."""
    pil = Image.new("RGBA", (48, 16), color=(200, 100, 50, 255))
    pixmap = ProfilesPage._pil_to_qpixmap(pil)
    back = ProfilesPage._pixmap_to_pil(pixmap)
    assert back.size == (48, 16)
