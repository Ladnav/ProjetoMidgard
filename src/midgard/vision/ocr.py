"""Lightweight template-matching based digit recognition service for classic game pixel fonts."""

import numpy as np
from PIL import Image

CHAR_PATTERNS = {
    '0': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ],
    '1': [
        [0, 0, 1, 0, 0],
        [0, 1, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 1, 1, 0]
    ],
    '2': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 1, 1, 0],
        [0, 1, 0, 0, 0],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 1]
    ],
    '3': [
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ],
    '4': [
        [0, 0, 0, 1, 0],
        [0, 0, 1, 1, 0],
        [0, 1, 0, 1, 0],
        [1, 0, 0, 1, 0],
        [1, 1, 1, 1, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 0, 1, 0]
    ],
    '5': [
        [1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ],
    '6': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ],
    '7': [
        [1, 1, 1, 1, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 1, 0, 0, 0]
    ],
    '8': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ],
    '9': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 1],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0]
    ],
    '/': [
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [1, 0, 0, 0, 0],
        [1, 0, 0, 0, 0],
        [1, 0, 0, 0, 0]
    ],
    '%': [
        [1, 1, 0, 0, 1],
        [1, 1, 0, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 1, 0, 1, 1],
        [1, 0, 0, 1, 1],
        [1, 0, 0, 1, 1]
    ]
}


class DigitRecognizer:
    """Solves text segments representing numeric states (like '120/150' or '90%')."""

    def __init__(self) -> None:
        # Pre-build numpy arrays of templates
        self.templates = {k: np.array(v, dtype=np.uint8) for k, v in CHAR_PATTERNS.items()}

    def parse_image(self, image: Image.Image) -> str:
        """Process image crop, match templates, and return the resolved string."""
        # Convert to grayscale
        gray = image.convert("L")
        arr = np.array(gray)
        if np.sum(arr) == 0:
            return ""

        # Determine if text is dark or light based on average background brightness
        mean_val = np.mean(arr)
        if mean_val > 127:
            # Background is light, text is dark (e.g. black text on light background)
            # Threshold: pixels below 100 become white (foreground)
            binarized = (arr < 100).astype(np.uint8)
        else:
            # Background is dark, text is light (e.g. white text on dark background)
            # Threshold: pixels above 160 become white (foreground)
            binarized = (arr > 160).astype(np.uint8)

        # Clear borders that might contain frame edges
        binarized[0, :] = 0
        binarized[-1, :] = 0

        # Segment characters vertically based on pixel projection with tolerance of 1 empty column
        col_sums = np.sum(binarized, axis=0)
        char_ranges = []
        in_char = False
        start_idx = 0
        empty_streak = 0
        
        for x in range(binarized.shape[1]):
            has_pixels = col_sums[x] > 0
            if has_pixels:
                if not in_char:
                    start_idx = x
                    in_char = True
                empty_streak = 0
            else:
                if in_char:
                    empty_streak += 1
                    # Tolerate up to 1 consecutive empty column (TASK-035)
                    if empty_streak > 1:
                        char_ranges.append((start_idx, x - empty_streak + 1))
                        in_char = False
                        empty_streak = 0
        if in_char:
            char_ranges.append((start_idx, binarized.shape[1]))

        result_chars = []
        for start, end in char_ranges:
            char_crop = binarized[:, start:end]
            
            # Find vertical boundary box inside this column segment to crop extra empty space
            row_sums = np.sum(char_crop, axis=1)
            y_indices = np.where(row_sums > 0)[0]
            if len(y_indices) == 0:
                continue
            y_start, y_end = y_indices[0], y_indices[-1] + 1
            char_crop = char_crop[y_start:y_end, :]

            # Score this segment against all character templates
            best_char = "?"
            best_score = -1.0
            
            ch_h, ch_w = char_crop.shape
            if ch_h <= 2 or ch_w <= 0:
                continue

            for char_key, temp_arr in self.templates.items():
                temp_h, temp_w = temp_arr.shape
                
                # Scale template or crop to match sizes for comparison
                # We scale the template to match the segment size
                from PIL import Image as PILImage
                temp_img = PILImage.fromarray(temp_arr * 255)
                temp_img_scaled = temp_img.resize((ch_w, ch_h), PILImage.Resampling.NEAREST)
                temp_scaled_arr = (np.array(temp_img_scaled) > 127).astype(np.uint8)

                # Compute match score (percentage of matching pixels)
                matches = np.sum(char_crop == temp_scaled_arr)
                score = matches / (ch_h * ch_w)

                if score > best_score:
                    best_score = score
                    best_char = char_key

            # Accept character classification if it matches sufficiently well
            if best_score > 0.65:
                # Post-processing to distinguish similar characters (TASK-035)
                # '8' and '0' look very similar scaled, but '8' has pixels in the middle row, '0' is empty.
                if best_char in ('0', '8'):
                    mid_y = ch_h // 2
                    mid_row = char_crop[mid_y, :]
                    # Sum middle row pixels (excluding borders)
                    if len(mid_row) > 2:
                        center_sum = np.sum(mid_row[1:-1])
                        if center_sum >= 1:
                            best_char = '8'
                        else:
                            best_char = '0'
                    else:
                        # Fallback to total density check
                        density = np.sum(char_crop) / (ch_h * ch_w)
                        if density > 0.6:
                            best_char = '8'
                        else:
                            best_char = '0'
                
                result_chars.append(best_char)

        return "".join(result_chars)

    def extract_percentage_or_values(self, image: Image.Image) -> tuple[int, int]:
        """Parse status numbers (e.g. '120/150' or '90%') and return a tuple of (current, max)."""
        text = self.parse_image(image)
        if not text:
            return 100, 100

        if "/" in text:
            try:
                parts = text.split("/")
                current = int(parts[0])
                maximum = int(parts[1])
                return current, maximum
            except Exception:
                pass

        # Try extracting digits if slash not present
        digits = "".join([c for c in text if c.isdigit()])
        if digits:
            try:
                val = int(digits)
                if "%" in text or val <= 100:
                    return val, 100
                else:
                    # Fallback default
                    return val, val
            except Exception:
                pass

        return 100, 100
