"""Visual template matching engine for detecting sub-images on game screens."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class TemplateDetector:
    """Detects sub-image templates on captured screen frames using OpenCV."""

    def find_template(
        self, screen_image: Image.Image, template_path: Path, threshold: float = 0.8
    ) -> tuple[int, int] | None:
        """Find the location of a sub-image template inside the screen_image.

        Returns (x, y) coordinates of the top-left corner of the match if found,
        otherwise returns None.
        """
        if not template_path.exists():
            return None

        # Convert PIL Image to OpenCV BGR numpy array
        screen_rgb = screen_image.convert("RGB")
        screen_np = np.array(screen_rgb, dtype=np.uint8)
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

        # Load template image in color (BGR)
        template_cv = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if template_cv is None:
            return None

        # If matching dimensions are invalid
        if screen_cv.shape[0] < template_cv.shape[0] or screen_cv.shape[1] < template_cv.shape[1]:
            return None

        # For flat/solid backgrounds, TM_CCOEFF_NORMED can evaluate matches with the template
        # background color at (0, 0) as 1.0 due to mathematical normalization limits.
        # We use TM_SQDIFF_NORMED which handles uniform solid color borders much more robustly.
        res = cv2.matchTemplate(screen_cv, template_cv, cv2.TM_SQDIFF_NORMED)

        # In SQDIFF, 0.0 is a perfect match and 1.0 is a complete mismatch.
        # So we look for the minimum value.
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # Convert threshold (e.g. 0.8 match similarity -> 0.2 difference limit)
        max_diff = 1.0 - threshold
        if min_val <= max_diff:
            return (int(min_loc[0]), int(min_loc[1]))

        return None
