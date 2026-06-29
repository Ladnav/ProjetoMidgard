"""Windows GDI screen capture service using ctypes."""

import ctypes
import ctypes.wintypes

from PIL import Image


# Define RECT structure for ctypes
class RECT(ctypes.Structure):
    """RECT structure for Win32 API calls."""

    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


# Configure explicit 64-bit argtypes and restypes for Win32 APIs (TASK-002)
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

user32.IsWindow.argtypes = [ctypes.c_void_p]
user32.IsWindow.restype = ctypes.c_bool

user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
user32.IsWindowVisible.restype = ctypes.c_bool

user32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = ctypes.c_bool

user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = ctypes.c_bool

user32.GetDC.argtypes = [ctypes.c_void_p]
user32.GetDC.restype = ctypes.c_void_p

user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p

gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p

gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p

gdi32.BitBlt.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
]
gdi32.BitBlt.restype = ctypes.c_bool

gdi32.GetBitmapBits.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
gdi32.GetBitmapBits.restype = ctypes.c_long

gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.restype = ctypes.c_bool

gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.restype = ctypes.c_bool

user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong

user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.SetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
user32.SetWindowTextW.restype = ctypes.c_bool

user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.EnumWindows.restype = ctypes.c_bool

user32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.ClientToScreen.restype = ctypes.c_bool

user32.GetDesktopWindow.argtypes = []
user32.GetDesktopWindow.restype = ctypes.c_void_p


def set_process_dpi_aware() -> None:
    """Set the current process to be DPI-aware to prevent capture scaling issues."""
    try:
        # Try Per-Monitor DPI Aware (Windows 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            # Fallback to System DPI Aware (Windows Vista+)
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def find_window_by_title(title_substring: str) -> int | None:
    """Search for a window by matching a substring of its title.

    Returns the HWND handle, or None if no match is found.
    """
    found_hwnds = []

    # Windows EnumWindows callback signature: BOOL (HWND, LPARAM)
    wnd_enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, extra: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                if title_substring.lower() in buffer.value.lower():
                    found_hwnds.append(hwnd)
                    return False  # Stop enumeration
        return True

    # Retain a reference to the callback object to prevent it from being garbage collected
    enum_proc = wnd_enum_proc(callback)
    user32.EnumWindows(enum_proc, 0)
    return found_hwnds[0] if found_hwnds else None


def list_windows_by_title(title_substring: str) -> list[tuple[int, str]]:
    """List all open window handles (HWNDs) and titles matching a substring search."""
    matched = []
    wnd_enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, extra: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                if title_substring.lower() in buffer.value.lower():
                    matched.append((hwnd, buffer.value))
        return True

    enum_proc = wnd_enum_proc(callback)
    user32.EnumWindows(enum_proc, 0)
    return matched


def list_windows_by_title_with_pid(title_substring: str) -> list[tuple[int, int, str]]:
    """List matching window handles, process IDs, and titles."""
    matched = []
    wnd_enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, extra: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                if title_substring.lower() in buffer.value.lower():
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    matched.append((hwnd, pid.value, buffer.value))
        return True

    enum_proc = wnd_enum_proc(callback)
    user32.EnumWindows(enum_proc, 0)
    return matched


def find_hwnd_by_pid(target_pid: int) -> int | None:
    """Find the top-level window handle (HWND) belonging to a specific Process ID (PID)."""
    found_hwnds = []
    wnd_enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, extra: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                found_hwnds.append(hwnd)
                return False
        return True

    enum_proc = wnd_enum_proc(callback)
    user32.EnumWindows(enum_proc, 0)
    return found_hwnds[0] if found_hwnds else None


def rename_window(hwnd: int, new_title: str) -> bool:
    """Set the window text of a specific window by its HWND handle."""
    if not user32.IsWindow(hwnd):
        return False
    return bool(user32.SetWindowTextW(hwnd, new_title))


class WindowCaptureService:
    """Captures specific window client areas via Windows GDI APIs."""

    def __init__(self, hwnd: int) -> None:
        if not user32.IsWindow(hwnd):
            raise ValueError(f"Invalid HWND handle: {hwnd}")
        self.hwnd = hwnd
        set_process_dpi_aware()

    @classmethod
    def from_title(cls, title_substring: str) -> "WindowCaptureService":
        """Factory method to find target window title and instantiate the service."""
        # 1. Check if the title is actually a stored PID binding format "Ragnarok [PID: 1234]"
        if " [pid: " in title_substring.lower():
            try:
                pid_str = title_substring.lower().split(" [pid: ")[-1].replace("]", "").strip()
                pid = int(pid_str)
                hwnd = find_hwnd_by_pid(pid)
                if hwnd is not None and user32.IsWindow(hwnd):
                    return cls(hwnd)
            except Exception:
                pass

        # 2. Try finding by matching title substring (with the PID suffix)
        hwnd = find_window_by_title(title_substring)
        if hwnd is not None:
            return cls(hwnd)

        # 3. Fallback: If title has [PID: ...], split it and look for the base character profile name
        if " [pid: " in title_substring.lower():
            try:
                base_title = title_substring.split(" [PID:")[0].split(" [pid:")[0].strip()
                hwnd = find_window_by_title(base_title)
                if hwnd is not None:
                    return cls(hwnd)
            except Exception:
                pass

        # 4. If all fails, raise
        raise ValueError(f"No window found matching title: '{title_substring}'")

    def capture(self, desktop_fallback: bool = False) -> Image.Image:
        """Capture the client area of the target window.

        If desktop_fallback is True, captures the entire desktop screen using the desktop's DC 
        and crops the game window's bounding box out of it. This avoids direct calls to protected 
        window hooks that trigger anti-cheat locks like GameGuard.
        """
        if not user32.IsWindow(self.hwnd):
            raise RuntimeError(f"Target HWND is no longer valid: {self.hwnd}")

        if desktop_fallback:
            return self._capture_via_desktop()

        # 1. Retrieve the client area rect
        rect = RECT()
        user32.GetClientRect(self.hwnd, ctypes.pointer(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Window client area has invalid dimensions: {width}x{height}")

        # 2. Get device contexts and compatible bitmap
        hdc_window = user32.GetDC(self.hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
        old_bitmap = gdi32.SelectObject(hdc_mem, hbitmap)

        # 3. Perform the BitBlt transfer
        SRCCOPY = 0x00CC0020
        success = gdi32.BitBlt(
            hdc_mem, 0, 0, width, height, hdc_window, 0, 0, SRCCOPY
        )
        if not success:
            # Clean up immediately if transfer failed
            gdi32.SelectObject(hdc_mem, old_bitmap)
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(self.hwnd, hdc_window)
            raise RuntimeError("GDI BitBlt transfer failed.")

        # 4. Extract bits from the bitmap structure
        bitmap_size = width * height * 4
        buffer = ctypes.create_string_buffer(bitmap_size)
        bytes_copied = gdi32.GetBitmapBits(hbitmap, bitmap_size, buffer)

        if bytes_copied <= 0:
            # Clean up immediately
            gdi32.SelectObject(hdc_mem, old_bitmap)
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(self.hwnd, hdc_window)
            raise RuntimeError("Failed to read bits from GDI bitmap.")

        # 5. Pack bits into a Pillow RGBA Image using BGRA raw decoder
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)

        # 6. GDI Teardown & cleanup
        gdi32.SelectObject(hdc_mem, old_bitmap)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(self.hwnd, hdc_window)

        return image

    def _capture_via_desktop(self) -> Image.Image:
        """Capture by querying the Desktop window coordinates and cropping target bounds."""
        # Find absolute window rect
        rect = RECT()
        user32.GetWindowRect(self.hwnd, ctypes.pointer(rect))
        
        # Calculate Client Rect coordinates inside absolute window coords
        client_rect = RECT()
        user32.GetClientRect(self.hwnd, ctypes.pointer(client_rect))
        
        # Map client top-left (0,0) to screen absolute coordinates
        point = ctypes.wintypes.POINT()
        point.x = 0
        point.y = 0
        user32.ClientToScreen(self.hwnd, ctypes.pointer(point))
        
        start_x = point.x
        start_y = point.y
        width = client_rect.right - client_rect.left
        height = client_rect.bottom - client_rect.top

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Desktop fallback crop coordinates are invalid: {width}x{height}")

        # Capture Desktop screen
        hwnd_desktop = user32.GetDesktopWindow()
        hdc_desktop = user32.GetDC(hwnd_desktop)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_desktop)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_desktop, width, height)
        old_bitmap = gdi32.SelectObject(hdc_mem, hbitmap)

        SRCCOPY = 0x00CC0020
        # BitBlt from start_x, start_y on Desktop DC
        success = gdi32.BitBlt(
            hdc_mem, 0, 0, width, height, hdc_desktop, start_x, start_y, SRCCOPY
        )
        if not success:
            gdi32.SelectObject(hdc_mem, old_bitmap)
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd_desktop, hdc_desktop)
            raise RuntimeError("Desktop GDI BitBlt crop failed.")

        bitmap_size = width * height * 4
        buffer = ctypes.create_string_buffer(bitmap_size)
        bytes_copied = gdi32.GetBitmapBits(hbitmap, bitmap_size, buffer)

        if bytes_copied <= 0:
            gdi32.SelectObject(hdc_mem, old_bitmap)
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd_desktop, hdc_desktop)
            raise RuntimeError("Failed to read bits from Desktop GDI bitmap.")

        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)

        # Cleanup
        gdi32.SelectObject(hdc_mem, old_bitmap)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd_desktop, hdc_desktop)

        return image
