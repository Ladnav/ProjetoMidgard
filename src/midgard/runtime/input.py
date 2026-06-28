"""Win32 SendInput keyboard adapter and input interfaces."""

import abc
import ctypes

# Win32 input simulation constants and structures
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT structure for keyboard simulation."""

    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    """Win32 union structure inside INPUT."""

    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    """Win32 INPUT structure for SendInput."""

    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", INPUT_UNION),
    ]


class BaseInputAdapter(abc.ABC):
    """Abstract interface for simulating keyboard actions."""

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


class DummyInputAdapter(BaseInputAdapter):
    """Fallback/Testing adapter that tracks key presses in memory."""

    def __init__(self) -> None:
        self.pressed_keys: list[int] = []
        self.history: list[tuple[str, int]] = []

    def press_key(self, scan_code: int) -> None:
        self.pressed_keys.append(scan_code)
        self.history.append(("press", scan_code))

    def release_key(self, scan_code: int) -> None:
        if scan_code in self.pressed_keys:
            self.pressed_keys.remove(scan_code)
        self.history.append(("release", scan_code))


class Win32InputAdapter(BaseInputAdapter):
    """Sends native hardware keyboard scan codes using SendInput.

    This bypasses basic software hook blockers (like Gepard/GameGuard hooks).
    """

    def press_key(self, scan_code: int) -> None:
        """Simulate holding down a key."""
        # Set up keyboard input structure
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


# Standard Keyboard Hardware Scan Codes (often used for F1-F9 keys in game configurations)
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
