"""Win32 SendInput keyboard and mouse adapter interfaces."""

import abc
import ctypes

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
        """Tap a key (press and release)."""
        self.press_key(scan_code)
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
        """Move the mouse relative to the client area of a window."""
        point = POINT(client_x, client_y)
        # Convert client point to screen coordinates
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.pointer(point))

        # Get system screen resolution
        width = ctypes.windll.user32.GetSystemMetrics(0)
        height = ctypes.windll.user32.GetSystemMetrics(1)

        # Map to absolute 65535 grid
        dx = int((point.x * 65535) / (width - 1)) if width > 1 else 0
        dy = int((point.y * 65535) / (height - 1)) if height > 1 else 0

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

    def click_mouse(self, button: str = "left") -> None:
        """Trigger a mouse click (down then up)."""
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
