"""Tests for Midgard Vision screen capture capabilities using GDI mocks."""

import ctypes
import sys
from unittest.mock import patch

import pytest
from PIL import Image

from midgard.vision.capture import (
    WindowCaptureService,
    find_window_by_title,
    set_process_dpi_aware,
)

# Skip all tests on non-Windows platforms
pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows GDI capture requires Windows OS"
)


def test_dpi_awareness_does_not_crash() -> None:
    """Initializing DPI awareness succeeds."""
    set_process_dpi_aware()


def test_find_window_invalid_title() -> None:
    """Searching for a non-existent window title returns None."""
    with patch("midgard.vision.capture.user32.EnumWindows") as mock_enum:
        mock_enum.return_value = 1
        assert find_window_by_title("ThisWindowDoesNotExistUniqueString_123") is None


def test_instantiate_invalid_hwnd() -> None:
    """Creating capture service with invalid HWND raises ValueError."""
    with patch("midgard.vision.capture.user32.IsWindow", return_value=0):
        with pytest.raises(ValueError, match="Invalid HWND handle"):
            WindowCaptureService(999999)


def test_capture_success_mocked() -> None:
    """The capture pipeline runs successfully and returns a PIL Image."""
    hwnd = 123456

    def mock_get_client_rect(h, rect_ref):
        rect_ref.contents.left = 0
        rect_ref.contents.top = 0
        rect_ref.contents.right = 100
        rect_ref.contents.bottom = 50
        return 1

    def mock_get_bitmap_bits(h, size, buffer):
        # Fill buffer with opaque red pixels in BGRA format
        pixel_data = b"\x00\x00\xff\xff" * (100 * 50)
        ctypes.memmove(buffer, pixel_data, len(pixel_data))
        return len(pixel_data)

    # Mock User32 & GDI32 calls
    with (
        patch("midgard.vision.capture.user32.IsWindow", return_value=1),
        patch("midgard.vision.capture.user32.GetClientRect", side_effect=mock_get_client_rect),
        patch("midgard.vision.capture.user32.GetDC", return_value=11),
        patch("midgard.vision.capture.gdi32.CreateCompatibleDC", return_value=22),
        patch("midgard.vision.capture.gdi32.CreateCompatibleBitmap", return_value=33),
        patch("midgard.vision.capture.gdi32.SelectObject", return_value=44),
        patch("midgard.vision.capture.gdi32.BitBlt", return_value=1),
        patch("midgard.vision.capture.gdi32.GetBitmapBits", side_effect=mock_get_bitmap_bits),
        patch("midgard.vision.capture.gdi32.DeleteObject", return_value=1) as mock_delete_obj,
        patch("midgard.vision.capture.gdi32.DeleteDC", return_value=1) as mock_delete_dc,
        patch("midgard.vision.capture.user32.ReleaseDC", return_value=1) as mock_release_dc,
    ):
        service = WindowCaptureService(hwnd)
        image = service.capture()

        # Verify PIL Image
        assert isinstance(image, Image.Image)
        assert image.size == (100, 50)
        assert image.mode == "RGBA"
        # Check pixel color (red, since we wrote \x00\x00\xff\xff ->
        # Blue=0, Green=0, Red=255, Alpha=255)
        assert image.getpixel((0, 0)) == (255, 0, 0, 255)

        # Verify correct GDI teardown calls
        mock_delete_obj.assert_called_once_with(33)
        mock_delete_dc.assert_called_once_with(22)
        mock_release_dc.assert_called_once_with(hwnd, 11)


def test_capture_failure_bitblt() -> None:
    """A failed BitBlt raises RuntimeError and cleans up GDI resources."""
    hwnd = 123456

    def mock_get_client_rect(h, rect_ref):
        rect_ref.contents.right = 100
        rect_ref.contents.bottom = 50
        return 1

    with (
        patch("midgard.vision.capture.user32.IsWindow", return_value=1),
        patch("midgard.vision.capture.user32.GetClientRect", side_effect=mock_get_client_rect),
        patch("midgard.vision.capture.user32.GetDC", return_value=11),
        patch("midgard.vision.capture.gdi32.CreateCompatibleDC", return_value=22),
        patch("midgard.vision.capture.gdi32.CreateCompatibleBitmap", return_value=33),
        patch("midgard.vision.capture.gdi32.SelectObject", return_value=44),
        patch("midgard.vision.capture.gdi32.BitBlt", return_value=0),  # BitBlt fails
        patch("midgard.vision.capture.gdi32.DeleteObject", return_value=1) as mock_delete_obj,
        patch("midgard.vision.capture.gdi32.DeleteDC", return_value=1) as mock_delete_dc,
        patch("midgard.vision.capture.user32.ReleaseDC", return_value=1) as mock_release_dc,
    ):
        service = WindowCaptureService(hwnd)
        with pytest.raises(RuntimeError, match="GDI BitBlt transfer failed"):
            service.capture()

        # Teardown should still be called to prevent memory leaks
        mock_delete_obj.assert_called_once_with(33)
        mock_delete_dc.assert_called_once_with(22)
        mock_release_dc.assert_called_once_with(hwnd, 11)


def test_capture_failure_get_bitmap_bits() -> None:
    """A failed GetBitmapBits raises RuntimeError and cleans up GDI resources."""
    hwnd = 123456

    def mock_get_client_rect(h, rect_ref):
        rect_ref.contents.right = 100
        rect_ref.contents.bottom = 50
        return 1

    with (
        patch("midgard.vision.capture.user32.IsWindow", return_value=1),
        patch("midgard.vision.capture.user32.GetClientRect", side_effect=mock_get_client_rect),
        patch("midgard.vision.capture.user32.GetDC", return_value=11),
        patch("midgard.vision.capture.gdi32.CreateCompatibleDC", return_value=22),
        patch("midgard.vision.capture.gdi32.CreateCompatibleBitmap", return_value=33),
        patch("midgard.vision.capture.gdi32.SelectObject", return_value=44),
        patch("midgard.vision.capture.gdi32.BitBlt", return_value=1),
        patch("midgard.vision.capture.gdi32.GetBitmapBits", return_value=0),  # Fails to copy bits
        patch("midgard.vision.capture.gdi32.DeleteObject", return_value=1) as mock_delete_obj,
        patch("midgard.vision.capture.gdi32.DeleteDC", return_value=1) as mock_delete_dc,
        patch("midgard.vision.capture.user32.ReleaseDC", return_value=1) as mock_release_dc,
    ):
        service = WindowCaptureService(hwnd)
        with pytest.raises(RuntimeError, match="Failed to read bits"):
            service.capture()

        mock_delete_obj.assert_called_once_with(33)
        mock_delete_dc.assert_called_once_with(22)
        mock_release_dc.assert_called_once_with(hwnd, 11)
