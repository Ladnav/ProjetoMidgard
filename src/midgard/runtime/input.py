"""Win32 SendInput keyboard and mouse adapter interfaces."""

import abc
import ctypes
import random
import time

# Win32 input simulation constants and structures
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT structure for keyboard simulation."""

    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    """Win32 MOUSEINPUT structure for mouse simulation."""

    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    """Win32 union structure inside INPUT."""

    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    """Win32 INPUT structure for SendInput."""

    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", INPUT_UNION),
    ]


class POINT(ctypes.Structure):
    """Win32 POINT structure."""

    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def generate_bezier_path(
    start: tuple[int, int], end: tuple[int, int], steps: int = 15
) -> list[tuple[int, int]]:
    """Generate smooth cursor coordinates along a cubic Bezier curve."""

    x0, y0 = start
    x3, y3 = end

    # Return end point if start/end are too close
    distance = ((x3 - x0) ** 2 + (y3 - y0) ** 2) ** 0.5
    if distance < 5:
        return [end]

    # Generate random control points for realistic hand instability
    ctrl_offset_x = (x3 - x0) * 0.25
    ctrl_offset_y = (y3 - y0) * 0.25

    x1 = x0 + ctrl_offset_x + random.uniform(-20, 20)
    y1 = y0 + ctrl_offset_y + random.uniform(-20, 20)

    x2 = x3 - ctrl_offset_x + random.uniform(-20, 20)
    y2 = y3 - ctrl_offset_y + random.uniform(-20, 20)

    path = []
    for i in range(steps + 1):
        t = i / steps
        xt = (1 - t) ** 3 * x0 + 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t**2 * x2 + t**3 * x3
        yt = (1 - t) ** 3 * y0 + 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t**2 * y2 + t**3 * y3
        
        # Add micro-deviations (polymorphic hand jitter) via Gaussian random noise
        # Decrease noise amplitude as we approach the final destination (end point)
        damping = 1.0 - t
        jitter_x = random.gauss(0.0, 1.5) * damping
        jitter_y = random.gauss(0.0, 1.5) * damping
        
        path.append((int(xt + jitter_x), int(yt + jitter_y)))
    return path


class BaseInputAdapter(abc.ABC):
    """Abstract interface for simulating keyboard and mouse actions."""

    @abc.abstractmethod
    def press_key(self, scan_code: int) -> None:
        """Simulate holding a key down by its hardware scan code."""
        pass

    @abc.abstractmethod
    def release_key(self, scan_code: int) -> None:
        """Simulate releasing a key by its hardware scan code."""
        pass

    def tap_key(self, scan_code: int) -> None:
        """Tap a key (press and release) with a randomized human-like hold time."""
        self.press_key(scan_code)
        time.sleep(random.uniform(0.04, 0.09))
        self.release_key(scan_code)

    @abc.abstractmethod
    def move_mouse_relative(self, hwnd: int, client_x: int, client_y: int) -> None:
        """Move the mouse cursor relative to the window client area coordinates."""
        pass

    @abc.abstractmethod
    def click_mouse(self, button: str = "left") -> None:
        """Trigger a mouse click (down then up) for 'left' or 'right' button."""
        pass


class DummyInputAdapter(BaseInputAdapter):
    """Fallback/Testing adapter that tracks key presses and mouse movements in memory."""

    def __init__(self) -> None:
        self.pressed_keys: list[int] = []
        self.history: list[tuple[str, str | int | tuple[int, int]]] = []
        self.mouse_x = 0
        self.mouse_y = 0

    def press_key(self, scan_code: int) -> None:
        self.pressed_keys.append(scan_code)
        self.history.append(("press", scan_code))

    def release_key(self, scan_code: int) -> None:
        if scan_code in self.pressed_keys:
            self.pressed_keys.remove(scan_code)
        self.history.append(("release", scan_code))

    def move_mouse_relative(self, hwnd: int, client_x: int, client_y: int) -> None:
        self.mouse_x = client_x
        self.mouse_y = client_y
        self.history.append(("move_mouse", (client_x, client_y)))

    def click_mouse(self, button: str = "left") -> None:
        self.history.append(("click_mouse", button))


class Win32InputAdapter(BaseInputAdapter):
    """Sends native hardware keyboard and mouse inputs using SendInput."""

    def press_key(self, scan_code: int) -> None:
        """Simulate holding down a key."""
        ki = KEYBDINPUT(
            wVk=0,
            wScan=scan_code,
            dwFlags=KEYEVENTF_SCANCODE,
            time=0,
            dwExtraInfo=None,
        )
        inp = INPUT(type=INPUT_KEYBOARD, ii=INPUT_UNION(ki=ki))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def release_key(self, scan_code: int) -> None:
        """Simulate releasing a key."""
        ki = KEYBDINPUT(
            wVk=0,
            wScan=scan_code,
            dwFlags=KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=None,
        )
        inp = INPUT(type=INPUT_KEYBOARD, ii=INPUT_UNION(ki=ki))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def move_mouse_relative(self, hwnd: int, client_x: int, client_y: int) -> None:
        """Move the mouse relative to the client area using a smooth Bezier path.
        
        Clamps client coordinates to keep them at least 25 pixels inside borders,
        preventing Ragexe coordinate calculation crashes when hitting edges.
        """
        # Retrieve client area rect to clamp coordinates safely
        rect = RECT()
        if ctypes.windll.user32.GetClientRect(hwnd, ctypes.pointer(rect)):
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            margin = 25
            if w > margin * 2:
                client_x = max(margin, min(client_x, w - margin))
            if h > margin * 2:
                client_y = max(margin, min(client_y, h - margin))

        # Get current cursor position on the screen
        cursor = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.pointer(cursor))
        start_pos = (cursor.x, cursor.y)

        # Convert target client coordinates to screen coordinates
        target_point = POINT(client_x, client_y)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.pointer(target_point))
        end_pos = (target_point.x, target_point.y)

        # Get system screen resolution
        width = ctypes.windll.user32.GetSystemMetrics(0)
        height = ctypes.windll.user32.GetSystemMetrics(1)

        # Generate smooth trajectory path
        path = generate_bezier_path(start_pos, end_pos, steps=10)

        # Perform step-by-step movements along the curve (TASK-031 Fitts' Law)
        total_steps = len(path)
        for i, (pt_x, pt_y) in enumerate(path):
            dx = int((pt_x * 65535) / (width - 1)) if width > 1 else 0
            dy = int((pt_y * 65535) / (height - 1)) if height > 1 else 0

            mi = MOUSEINPUT(
                dx=dx,
                dy=dy,
                mouseData=0,
                dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                time=0,
                dwExtraInfo=None,
            )
            inp = INPUT(type=INPUT_MOUSE, ii=INPUT_UNION(mi=mi))
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            
            # Sinusoidal sleep speed scaling: accelerate first half, decelerate second half (Fitts' Law)
            t = (i + 1) / total_steps
            import math
            # Velocity peak is around middle (t=0.5 -> sleep time minimum), slow start (t=0 -> high sleep), slow end (t=1 -> high sleep)
            speed_factor = math.sin(t * math.pi)  # ranges from 0 to 1
            if speed_factor < 0.1:
                speed_factor = 0.1
            sleep_time = 0.001 + (0.009 * (1.0 - speed_factor))
            time.sleep(random.uniform(sleep_time * 0.8, sleep_time * 1.2))

    def click_mouse(self, button: str = "left") -> None:
        """Trigger a mouse click (down then up) with a randomized human-like hold time."""
        if button == "left":
            down_flag = MOUSEEVENTF_LEFTDOWN
            up_flag = MOUSEEVENTF_LEFTUP
        else:
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP

        # Down event
        mi_down = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=down_flag, time=0, dwExtraInfo=None)
        inp_down = INPUT(type=INPUT_MOUSE, ii=INPUT_UNION(mi=mi_down))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))

        # Human-like click hold delay
        time.sleep(random.uniform(0.04, 0.09))

        # Up event
        mi_up = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=up_flag, time=0, dwExtraInfo=None)
        inp_up = INPUT(type=INPUT_MOUSE, ii=INPUT_UNION(mi=mi_up))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))


# Standard Keyboard Hardware Scan Codes
SCAN_CODES = {
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    "0": 0x0B,
    "F1": 0x3B,
    "F2": 0x3C,
    "F3": 0x3D,
    "F4": 0x3E,
    "F5": 0x3F,
    "F6": 0x40,
    "F7": 0x41,
    "F8": 0x42,
    "F9": 0x43,
    "F10": 0x44,
}
