"""Tests for Template Matching Visual Recognition Module."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from midgard.vision.detector import TemplateDetector


def test_cv2_image_matching_direct(tmp_path) -> None:
    """Verify that cv2 matchTemplate works when using PIL images directly."""
    # Create canvas: solid black background (0), red square at (50, 60)
    canvas = np.zeros((200, 200, 3), dtype=np.uint8)

    # Red square in BGR is [0, 0, 255]
    canvas[60:90, 50:80] = [0, 0, 255]

    screen_path = tmp_path / "screenshot.png"
    cv2.imwrite(str(screen_path), canvas)

    # Template: 30x30 red square BGR
    template = np.zeros((30, 30, 3), dtype=np.uint8)
    template[:, :] = [0, 0, 255]
    template_path = tmp_path / "red_template.png"
    cv2.imwrite(str(template_path), template)

    # Debug: Check normalized cross-correlation outputs
    screen_loaded = cv2.imread(str(screen_path), cv2.IMREAD_COLOR)
    template_loaded = cv2.imread(str(template_path), cv2.IMREAD_COLOR)

    # We use TM_SQDIFF or TM_SQDIFF_NORMED for uniform template matching.
    # TM_CCOEFF_NORMED on flat background with a template of same background color
    # can output high correlation score at (0, 0) because background matches background.
    # Since TM_SQDIFF has min_val/min_loc as the best match, let's print TM_SQDIFF:
    res = cv2.matchTemplate(screen_loaded, template_loaded, cv2.TM_SQDIFF)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    print(f"DEBUG raw TM_SQDIFF matching: min_val={min_val}, min_loc={min_loc}")

    # Load using PIL to test conversion compatibility
    pil_image = Image.open(screen_path)

    detector = TemplateDetector()
    match_coord = detector.find_template(pil_image, template_path, threshold=0.9)

    assert match_coord is not None
    assert abs(match_coord[0] - 50) <= 2
    assert abs(match_coord[1] - 60) <= 2


def test_template_matching_fail(tmp_path) -> None:
    """TemplateDetector returns None if template is not in the screenshot."""
    canvas = np.zeros((100, 100, 3), dtype=np.uint8)
    screen_path = tmp_path / "screenshot_fail.png"
    cv2.imwrite(str(screen_path), canvas)

    # Blue template
    template = np.zeros((10, 10, 3), dtype=np.uint8)
    template[:, :] = [255, 0, 0]  # BGR Blue
    template_path = tmp_path / "blue_block.png"
    cv2.imwrite(str(template_path), template)

    pil_image = Image.open(screen_path)
    detector = TemplateDetector()
    match_coord = detector.find_template(pil_image, template_path, threshold=0.8)

    assert match_coord is None


def test_template_file_not_found() -> None:
    """TemplateDetector returns None if template file path does not exist."""
    canvas = Image.new("RGB", (50, 50))
    detector = TemplateDetector()
    assert detector.find_template(canvas, Path("invalid_file_path.png")) is None
