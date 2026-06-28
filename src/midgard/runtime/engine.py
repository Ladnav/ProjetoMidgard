"""Midgard Runtime execution engine."""

import argparse
import select
import socket
import sys
import time
from pathlib import Path

from midgard.profile import ProfileStore
from midgard.runtime.combat import CombatModule
from midgard.runtime.consumables import ConsumablesModule
from midgard.runtime.evasion import EvasionModule
from midgard.runtime.heal import HealModule
from midgard.runtime.input import DummyInputAdapter, Win32InputAdapter
from midgard.runtime.navigation import NavigationModule
from midgard.runtime.protocol import recv_message, send_message
from midgard.vision.capture import WindowCaptureService
from midgard.vision.detector import TemplateDetector


class RuntimeEngine:
    """Core runtime engine executing the main loop in the elevated/isolated process."""

    def __init__(
        self,
        profile_id: int,
        database_path: Path,
        studio_port: int,
        *,
        use_dummy_input: bool = False,
    ) -> None:
        self.profile_id = profile_id
        self.database_path = database_path
        self.studio_port = studio_port
        self.running = True
        self.active = False
        self._sock: socket.socket | None = None

        # Input and capture abstractions
        self.input_adapter = DummyInputAdapter() if use_dummy_input else Win32InputAdapter()
        self.capture_service: WindowCaptureService | None = None
        self.heal_module: HealModule | None = None
        self.combat_module: CombatModule | None = None
        self.navigation_module: NavigationModule | None = None
        self.consumables_module: ConsumablesModule | None = None
        self.evasion_module: EvasionModule | None = None
        self.template_detector = TemplateDetector()
        self.detector_rules: dict[str, str] = {}
        self.capture_failures = 0

        # Stats
        self.xp_gained = 0
        self.loot_collected = 0

    def run(self) -> None:
        """Connect to Studio, register, load profile, and enter the main loop."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.connect(("127.0.0.1", self.studio_port))
        except OSError:
            # Exit if the connection fails
            return

        # Send registration packet
        send_message(self._sock, {"type": "registration", "profile_id": self.profile_id})

        # Load profile configuration rules from SQLite database
        try:
            store = ProfileStore(self.database_path)
            profile = store.get_profile(self.profile_id)
            store.close()

            if profile:
                # Initialize heal rules dict
                heal_rules = profile.rules.get("healing", {})
                self.heal_module = HealModule(heal_rules, self.input_adapter)

                # Initialize consumables rules dict
                consumable_rules = profile.rules.get("consumables", {})
                self.consumables_module = ConsumablesModule(consumable_rules, self.input_adapter)

                # Initialize evasion rules dict
                evasion_rules = profile.rules.get("evasion", {})
                self.evasion_module = EvasionModule(evasion_rules, self.input_adapter)

                # Initialize looting rules dict
                looting_rules = profile.rules.get("looting", {})
                from midgard.runtime.loot import LootModule
                self.loot_module = LootModule(looting_rules, self.input_adapter)

                # Initialize anomaly security rules dict
                security_rules = profile.rules.get("security", {})
                from midgard.runtime.anomaly import AnomalyModule
                self.anomaly_module = AnomalyModule(security_rules, self.input_adapter)

                # Initialize combat rules dict
                combat_rules = profile.rules.get("combat", {})

                # Initialize navigation rules dict
                nav_rules = profile.rules.get("navigation", {})

                # Initialize detector rules dict
                self.detector_rules = profile.rules.get("detector", {})

                # Find and initialize WindowCaptureService if window_title is set
                try:
                    self.capture_service = WindowCaptureService.from_title(profile.window_title)
                    self.combat_module = CombatModule(
                        combat_rules, self.input_adapter, self.capture_service.hwnd
                    )
                    self.navigation_module = NavigationModule(
                        nav_rules, self.input_adapter, self.capture_service.hwnd
                    )
                    window_log = (
                        f"Connected to game window '{profile.window_title}' "
                        f"(HWND: {self.capture_service.hwnd})"
                    )
                    send_message(
                        self._sock,
                        {
                            "type": "log",
                            "message": window_log,
                            "level": "INFO",
                        },
                    )
                except ValueError as e:
                    send_message(
                        self._sock,
                        {
                            "type": "log",
                            "message": f"Window discovery warning: {e}",
                            "level": "WARNING",
                        },
                    )
            else:
                send_message(
                    self._sock,
                    {
                        "type": "log",
                        "message": f"Profile ID {self.profile_id} not found in database",
                        "level": "ERROR",
                    },
                )
        except Exception as e:
            try:
                send_message(
                    self._sock,
                    {
                        "type": "log",
                        "message": f"Failed to initialize profile database: {e}",
                        "level": "ERROR",
                    },
                )
            except OSError:
                pass

        try:
            while self.running:
                # 1. Non-blocking command check
                readable, _, _ = select.select([self._sock], [], [], 0.02)
                if readable:
                    msg = recv_message(self._sock)
                    if msg is None:
                        # Studio disconnected
                        break
                    self._handle_message(msg)

                # 2. Tick cycle if started
                if self.active:
                    self._tick()

                time.sleep(0.05)
        except Exception as e:
            # Try to send crash report if possible
            try:
                crash_msg = {
                    "type": "log",
                    "message": f"Engine crashed: {e}",
                    "level": "ERROR",
                }
                send_message(self._sock, crash_msg)
            except OSError:
                pass
        finally:
            if self._sock:
                self._sock.close()

    def _handle_message(self, msg: dict) -> None:
        if msg.get("type") == "command":
            action = msg.get("action")
            if action == "start":
                self.active = True
                send_message(
                    self._sock,
                    {
                        "type": "log",
                        "message": f"Profile {self.profile_id} automation started",
                        "level": "INFO",
                    },
                )
            elif action == "pause":
                self.active = False
                send_message(
                    self._sock,
                    {
                        "type": "log",
                        "message": f"Profile {self.profile_id} automation paused",
                        "level": "INFO",
                    },
                )
            elif action == "stop":
                self.active = False
                self.running = False
                send_message(
                    self._sock,
                    {
                        "type": "log",
                        "message": f"Profile {self.profile_id} automation stopped",
                        "level": "INFO",
                    },
                )

    def _tick(self) -> None:
        """Execute active automation modules."""
        # Simulate base metrics
        self.xp_gained += 15
        self.loot_collected += 1

        hp_pct = 92
        # Run GDI Screen Capture and Modules
        if self.capture_service:
            try:
                image = self.capture_service.capture()
                self.capture_failures = 0

                # 1. Calculate dynamic HP status percentage first so evasion has real data
                if self.heal_module and self.heal_module.enabled:
                    try:
                        width, height = image.size
                        hx, hy = self.heal_module.hp_x, self.heal_module.hp_y
                        hw, hh = self.heal_module.hp_w, self.heal_module.hp_h
                        hx2 = min(hx + hw, width)
                        hy2 = min(hy + hh, height)
                        hp_crop = image.crop((hx, hy, hx2, hy2))
                        
                        hp_cur, hp_max = self.heal_module.recognizer.extract_percentage_or_values(hp_crop)
                        if hp_max > 0:
                            hp_pct = int(hp_cur / hp_max * 100.0)
                        else:
                            hp_pct = 92
                    except Exception:
                        hp_pct = 92

                # Check for configured visual search templates
                # Format: detector.template_path = "/path/to/template.png"
                # If template_path is set, run search check
                template_path_str = self.detector_rules.get("detector.template_path")
                if template_path_str:
                    try:
                        th = float(self.detector_rules.get("detector.threshold", "0.8"))
                        match_coord = self.template_detector.find_template(
                            image, Path(template_path_str), th
                        )
                        if match_coord:
                            send_message(
                                self._sock,
                                {
                                    "type": "log",
                                    "message": (
                                        f"Visual template match found at coordinates: {match_coord}"
                                    ),
                                    "level": "INFO",
                                },
                            )
                            # If configured to alarm on template detection
                            alarm_on = (
                                self.detector_rules.get("detector.alarm_on_match", "false").lower()
                                == "true"
                            )
                            if alarm_on:
                                try:
                                    send_message(
                                        self._sock,
                                        {
                                            "type": "alarm",
                                            "alarm_type": "template_match",
                                            "message": (
                                                f"Target visual state detected: {template_path_str}"
                                            ),
                                        },
                                    )
                                except OSError:
                                    pass
                    except Exception:
                        pass

                # Evaluate modules based on priority:
                # 1. Heal (Highest Priority)
                # 2. Evasion (Panic Evasion Trigger)
                # 3. Consumables (Third Priority)
                # 4. Combat (Fourth Priority)
                # 5. Navigation (Lowest Priority)
                triggered_action = False

                # 1. Anomaly Security detection (Highest Priority)
                if hasattr(self, "anomaly_module") and self.anomaly_module:
                    anomaly_log = self.anomaly_module.evaluate(image)
                    if anomaly_log:
                        triggered_action = True
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": anomaly_log,
                                "level": "CRITICAL",
                            },
                        )
                        # Fire visual/audio alarm event
                        send_message(
                            self._sock,
                            {
                                "type": "alarm",
                                "alarm_type": "anomaly",
                                "message": anomaly_log,
                            },
                        )
                        # Pause loop execution for security
                        self.active = False

                if not triggered_action and self.heal_module:
                    heal_log = self.heal_module.evaluate(image)
                    if heal_log:
                        triggered_action = True
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": heal_log,
                                "level": "INFO",
                            },
                        )

                # Emergency evasion check
                if not triggered_action and self.evasion_module:
                    evasion_log = self.evasion_module.evaluate_hp(hp_pct)
                    if evasion_log:
                        triggered_action = True
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": evasion_log,
                                "level": "WARNING",
                            },
                        )

                # 3. Auto-Loot check
                if not triggered_action and hasattr(self, "loot_module") and self.loot_module:
                    loot_log = self.loot_module.evaluate(image)
                    if loot_log:
                        triggered_action = True
                        self.loot_collected += 1
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": loot_log,
                                "level": "INFO",
                            },
                        )

                # Only evaluate consumables if no healing or evasion triggered
                if not triggered_action and self.consumables_module:
                    consumables_log = self.consumables_module.evaluate(image)
                    if consumables_log:
                        triggered_action = True
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": consumables_log,
                                "level": "INFO",
                            },
                        )

                # Only combat if no healing, evasion, or consumables triggered
                if not triggered_action and self.combat_module:
                    combat_log = self.combat_module.evaluate(image)
                    if combat_log:
                        triggered_action = True
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": combat_log,
                                "level": "INFO",
                            },
                        )

                # Only navigate if no healing, evasion, consumables, or combat action triggered
                if not triggered_action and self.navigation_module:
                    nav_log = self.navigation_module.evaluate(image)
                    if nav_log:
                        send_message(
                            self._sock,
                            {
                                "type": "log",
                                "message": nav_log,
                                "level": "INFO",
                            },
                        )
            except Exception as e:
                self.capture_failures += 1
                if self.capture_failures == 5:
                    try:
                        send_message(
                            self._sock,
                            {
                                "type": "alarm",
                                "alarm_type": "disconnect",
                                "message": (
                                    f"Game client disconnected (failures: {self.capture_failures})."
                                ),
                            },
                        )
                    except OSError:
                        pass

                # Log any runtime capture / evaluation warnings
                try:
                    send_message(
                        self._sock,
                        {
                            "type": "log",
                            "message": f"Automation evaluation error: {e}",
                            "level": "WARNING",
                        },
                    )
                except OSError:
                    pass

        # Trigger death alarm event if hp_pct hits 0
        if hp_pct == 0:
            try:
                send_message(
                    self._sock,
                    {
                        "type": "alarm",
                        "alarm_type": "death",
                        "message": "Character death detected! HP is 0%.",
                    },
                )
            except OSError:
                pass

        status_msg = {
            "type": "status",
            "profile_id": self.profile_id,
            "hp_pct": hp_pct,
            "sp_pct": 74,
            "xp_gained": self.xp_gained,
            "loot_collected": self.loot_collected,
        }
        try:
            send_message(self._sock, status_msg)
        except OSError:
            self.running = False


def main() -> int:
    """Command-line entry point for runtime engine subprocess."""
    parser = argparse.ArgumentParser(description="Midgard Runtime Engine")
    parser.add_argument("--profile", type=int, required=True, help="Profile ID")
    parser.add_argument("--db", type=str, required=True, help="Database path")
    parser.add_argument("--port", type=int, required=True, help="Studio TCP port")
    parser.add_argument("--dummy-input", action="store_true", help="Use dummy memory input adapter")

    args = parser.parse_args()

    engine = RuntimeEngine(
        profile_id=args.profile,
        database_path=Path(args.db),
        studio_port=args.port,
        use_dummy_input=args.dummy_input,
    )
    engine.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
