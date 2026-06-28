"""Tests for Midgard Runtime process management and IPC."""

import socket
import time
from pathlib import Path

from midgard.runtime.launcher import RuntimeLauncher
from midgard.runtime.protocol import recv_message, send_message


def test_protocol_message_packing() -> None:
    """Pack and unpack messages correctly over a socket pair."""
    parent_sock, child_sock = socket.socketpair()
    try:
        parent_sock.setblocking(False)
        child_sock.setblocking(False)

        test_data = {"type": "test_event", "contents": {"key": "value"}}
        send_message(parent_sock, test_data)

        # Allow non-blocking receive
        received = recv_message(child_sock)
        assert received == test_data
    finally:
        parent_sock.close()
        child_sock.close()


def test_launcher_lifecycle_and_communication(tmp_path: Path) -> None:
    """The launcher spawns the engine, completes registration, and processes commands."""
    db_path = tmp_path / "midgard-test-runtime.db"

    launcher = RuntimeLauncher(profile_id=42, database_path=db_path)
    try:
        launcher.start()
        assert launcher.is_alive()
        assert launcher.port > 0

        # 1. Verify child engine registration
        reg_msg = launcher.receive_event(timeout=1.5)
        assert reg_msg is not None
        assert reg_msg["type"] == "registration"
        assert reg_msg["profile_id"] == 42

        # 2. Send START command
        launcher.send_command("start")

        # Read start confirmation log
        log_msg = launcher.receive_event(timeout=1.0)
        assert log_msg is not None
        assert log_msg["type"] == "log"
        assert "started" in log_msg["message"]

        # Read simulated gameplay status tick
        status_msg = launcher.receive_event(timeout=1.0)
        assert status_msg is not None
        assert status_msg["type"] == "status"
        assert status_msg["profile_id"] == 42
        assert status_msg["hp_pct"] == 92
        assert status_msg["xp_gained"] == 15

        # 3. Send PAUSE command
        launcher.send_command("pause")

        log_pause_msg = launcher.receive_event(timeout=1.0)
        assert log_pause_msg is not None
        assert log_pause_msg["type"] == "log"
        assert "paused" in log_pause_msg["message"]

        # 4. Send STOP command
        launcher.send_command("stop")

        # Read final stop log
        log_stop_msg = launcher.receive_event(timeout=1.0)
        assert log_stop_msg is not None
        assert log_stop_msg["type"] == "log"
        assert "stopped" in log_stop_msg["message"]

        # Wait for process to terminate cleanly
        for _ in range(20):
            if not launcher.is_alive():
                break
            time.sleep(0.05)

        assert not launcher.is_alive()

    finally:
        launcher.terminate()
