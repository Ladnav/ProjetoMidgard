"""Midgard Runtime execution engine."""

import argparse
import select
import socket
import sys
import time
from pathlib import Path

from midgard.runtime.protocol import recv_message, send_message


class RuntimeEngine:
    """Core runtime engine executing the main loop in the elevated/isolated process."""

    def __init__(self, profile_id: int, database_path: Path, studio_port: int) -> None:
        self.profile_id = profile_id
        self.database_path = database_path
        self.studio_port = studio_port
        self.running = True
        self.active = False
        self._sock: socket.socket | None = None

        # Simulated stats for verification
        self.xp_gained = 0
        self.loot_collected = 0

    def run(self) -> None:
        """Connect to Studio, register, and enter the main loop."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.connect(("127.0.0.1", self.studio_port))
        except OSError:
            # Exit if the connection fails
            return

        # Send registration packet
        send_message(self._sock, {"type": "registration", "profile_id": self.profile_id})

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
        """Simulated gameplay tick."""
        self.xp_gained += 15
        self.loot_collected += 1

        status_msg = {
            "type": "status",
            "profile_id": self.profile_id,
            "hp_pct": 92,
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

    args = parser.parse_args()

    engine = RuntimeEngine(
        profile_id=args.profile,
        database_path=Path(args.db),
        studio_port=args.port,
    )
    engine.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
