"""Midgard Runtime process launcher and controller."""

import os
import select
import socket
import subprocess
import sys
from pathlib import Path

from midgard.runtime.protocol import recv_message, send_message


class RuntimeLauncher:
    """Manages the lifecycle of a runtime subprocess and communicates via IPC."""

    def __init__(
        self, profile_id: int, database_path: Path, *, use_dummy_input: bool = False
    ) -> None:
        self.profile_id = profile_id
        self.database_path = database_path
        self.use_dummy_input = use_dummy_input
        self.port: int = 0

        self._server_sock: socket.socket | None = None
        self._client_sock: socket.socket | None = None
        self._process: subprocess.Popen | None = None

    def start(self) -> None:
        """Bind to a local port, spawn the engine child process, and accept its connection."""
        # 1. Start TCP listener on a dynamic local port
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.bind(("127.0.0.1", 0))
        self._server_sock.listen(1)
        self.port = self._server_sock.getsockname()[1]

        # 2. Spawn the elevated or standard child process
        cmd = [
            sys.executable,
            "-m",
            "midgard.runtime.engine",
            "--profile",
            str(self.profile_id),
            "--db",
            str(self.database_path.resolve()),
            "--port",
            str(self.port),
        ]
        if self.use_dummy_input:
            cmd.append("--dummy-input")

        # Ensure PYTHONPATH includes the src/ directory so the child process can import midgard
        src_dir = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(src_dir) + (
            os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else ""
        )

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        # 3. Await connection from child process
        self._server_sock.settimeout(5.0)
        try:
            self._client_sock, _addr = self._server_sock.accept()
            self._client_sock.setblocking(False)
        except TimeoutError:
            self.terminate()
            raise TimeoutError("Midgard Runtime child process connection timeout.")
        finally:
            if self._server_sock:
                self._server_sock.close()
                self._server_sock = None

    def send_command(self, action: str) -> None:
        """Send a control command (start, pause, stop) to the child engine."""
        if not self._client_sock:
            raise RuntimeError("Runtime process is not connected.")

        # Temporarily use blocking mode to ensure command delivery
        self._client_sock.setblocking(True)
        try:
            send_message(self._client_sock, {"type": "command", "action": action})
        finally:
            self._client_sock.setblocking(False)

    def receive_event(self, timeout: float = 0.0) -> dict | None:
        """Check for events (status, log) sent by the engine without blocking."""
        if not self._client_sock:
            return None

        readable, _, _ = select.select([self._client_sock], [], [], timeout)
        if readable:
            return recv_message(self._client_sock)
        return None

    def is_alive(self) -> bool:
        """Check if the child process is still running."""
        return self._process is not None and self._process.poll() is None

    def terminate(self) -> None:
        """Clean up connections and terminate the child process cleanly."""
        if self._client_sock:
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None

        if self._process:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None

        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
