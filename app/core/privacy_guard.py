from __future__ import annotations

import socket
from typing import Any


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_INSTALLED = False
_ALLOW_LOCALHOST = True


class NetworkBlockedError(OSError):
    """Raised when the app tries to open a blocked network connection."""


def install_network_guard(allow_localhost: bool = True) -> None:
    """Block non-local network connections made by this Python process.

    This is a process-level safety net in addition to AIManager's localhost-only
    HTTP client. It catches accidental network use from dependencies too.
    """
    global _INSTALLED, _ALLOW_LOCALHOST
    _ALLOW_LOCALHOST = allow_localhost
    if _INSTALLED:
        return
    socket.create_connection = _guarded_create_connection
    socket.socket.connect = _guarded_socket_connect
    _INSTALLED = True


def set_allow_localhost(allow_localhost: bool) -> None:
    global _ALLOW_LOCALHOST
    _ALLOW_LOCALHOST = allow_localhost


def _is_allowed(address: Any) -> bool:
    if not _ALLOW_LOCALHOST:
        return False
    host = _extract_host(address)
    return host in LOCAL_HOSTS


def _extract_host(address: Any) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0]).strip("[]").lower()
    return str(address).strip("[]").lower()


def _guarded_create_connection(address: Any, *args: Any, **kwargs: Any):
    if not _is_allowed(address):
        raise NetworkBlockedError(f"Blocked non-local connection: {address}")
    return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)


def _guarded_socket_connect(self: socket.socket, address: Any) -> None:
    if not _is_allowed(address):
        raise NetworkBlockedError(f"Blocked non-local connection: {address}")
    return _ORIGINAL_SOCKET_CONNECT(self, address)
