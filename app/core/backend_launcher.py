from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


class LocalBackendLauncher:
    def __init__(self, project_root: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.project_root = project_root
        self.backend_dir = project_root / "backend"
        self.host = host
        self.port = port
        self._process: subprocess.Popen | None = None

    def ensure_running(self, timeout_seconds: float = 8.0) -> bool:
        if self.is_running():
            return True

        process = self._spawn_backend()
        if process is None:
            return False

        self._process = process
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.is_running():
                return True
            if self._process.poll() is not None:
                break
            time.sleep(0.15)
        return self.is_running()

    def is_running(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.4):
                return True
        except OSError:
            return False

    def stop(self) -> None:
        if not self._process or self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
        finally:
            self._process = None

    def _spawn_backend(self) -> subprocess.Popen | None:
        if not self.backend_dir.exists():
            return None

        python_executable = self._resolve_python()
        if python_executable is None:
            return None

        command = [
            str(python_executable),
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.Popen(
            command,
            cwd=str(self.backend_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    def _resolve_python(self) -> Path | None:
        venv_python = self.backend_dir / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return venv_python

        current_python = Path(sys.executable)
        if current_python.exists() and current_python.suffix.lower() == ".exe":
            return current_python
        return None
