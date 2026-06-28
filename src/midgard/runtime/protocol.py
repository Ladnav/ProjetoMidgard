"""TCP socket message framing protocol."""

import json
import socket
import struct


def send_message(sock: socket.socket, message: dict) -> None:
    """Pack and send a JSON message over a socket using length prefixing."""
    payload = json.dumps(message).encode("utf-8")
    header = struct.pack("!I", len(payload))
    sock.sendall(header + payload)


def recv_message(sock: socket.socket) -> dict | None:
    """Receive and unpack a length-prefixed JSON message from a socket."""
    try:
        header = recv_all(sock, 4)
        if not header:
            return None
        length = struct.unpack("!I", header)[0]
        payload = recv_all(sock, length)
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))
    except (OSError, ValueError, struct.error):
        return None


def recv_all(sock: socket.socket, length: int) -> bytes | None:
    """Read exactly `length` bytes from a socket, or return None if EOF is reached."""
    data = bytearray()
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)
