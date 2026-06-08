from __future__ import annotations

import socket
import subprocess
import sys
import time
import os
from pathlib import Path


class LocalBackendLauncher:
    def __init__(self, project_root: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.project_root = project_root
        self.backend_dir = project_root / "backend"
        self.host = host
        self.port = port
        self._process: subprocess.Popen | None = None

    def ensure_running(self, timeout_seconds: float = 8.0) -> bool:
        # If something old is already listening on the backend port,
        # restart it to guarantee we run the current backend code.
        if self.is_running():
            existing_pid = self._listening_pid()
            own_pid = self._process.pid if self._process and self._process.poll() is None else None
            if existing_pid and existing_pid != own_pid:
                self._terminate_pid(existing_pid)
                time.sleep(0.2)
            else:
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
            # Best effort: if some orphan backend still listens on this port, stop it.
            existing_pid = self._listening_pid()
            if existing_pid:
                self._terminate_pid(existing_pid)
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
        finally:
            self._process = None
        # Extra guard against zombie listeners.
        existing_pid = self._listening_pid()
        if existing_pid:
            self._terminate_pid(existing_pid)

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
        env = os.environ.copy()
        models_path = Path("D:/OllamaModels")
        if models_path.exists() and not env.get("OLLAMA_MODELS"):
            env["OLLAMA_MODELS"] = str(models_path)
        return subprocess.Popen(
            command,
            cwd=str(self.backend_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            env=env,
        )

    def _resolve_python(self) -> Path | None:
        venv_python = self.backend_dir / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return venv_python
        current_python = Path(sys.executable)
        if current_python.exists() and current_python.suffix.lower() == ".exe":
            return current_python
        return None

    def _listening_pid(self) -> int | None:
        try:
            output = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return None

        port_suffix = f":{self.port}"
        for line in output.splitlines():
            normalized = " ".join(line.split())
            if not normalized or "LISTENING" not in normalized:
                continue
            parts = normalized.split(" ")
            if len(parts) < 5:
                continue
            local_addr = parts[1]
            state = parts[3]
            pid_raw = parts[4]
            if state != "LISTENING" or not local_addr.endswith(port_suffix):
                continue
            try:
                return int(pid_raw)
            except ValueError:
                return None
        return None

    @staticmethod
    def _terminate_pid(pid: int) -> None:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
