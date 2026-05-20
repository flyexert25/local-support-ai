from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Any


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_INSTALLED = False
_ALLOW_LOCALHOST = True
_TEMP_ALLOWED_HOSTS: set[str] = set()
_TEMP_ALLOWED_IPS: set[str] = set()


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


@contextmanager
def allow_hosts_temporarily(*hosts: str):
    normalized = {host.strip().lower() for host in hosts if host.strip()}
    resolved_ips: set[str] = set()
    for host in normalized:
        try:
            infos = socket.getaddrinfo(host, None)
            resolved_ips.update(str(info[4][0]).strip("[]").lower() for info in infos if info[4])
        except OSError:
            continue
    _TEMP_ALLOWED_HOSTS.update(normalized)
    _TEMP_ALLOWED_IPS.update(resolved_ips)
    try:
        yield
    finally:
        _TEMP_ALLOWED_HOSTS.difference_update(normalized)
        _TEMP_ALLOWED_IPS.difference_update(resolved_ips)


def _is_allowed(address: Any) -> bool:
    host = _extract_host(address)
    if not _ALLOW_LOCALHOST:
        return False
    return host in LOCAL_HOSTS or _matches_temp_allowed(host)


def _matches_temp_allowed(host: str) -> bool:
    return host in _TEMP_ALLOWED_IPS or any(host == allowed or host.endswith(f".{allowed}") for allowed in _TEMP_ALLOWED_HOSTS)


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
