import json
import logging
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

LOG = logging.getLogger("qq-bridge")


class OpenCodeClient:
    def __init__(self, config: dict, state_path: str = None):
        options = config["opencode"]
        self.base_url = options["base_url"].rstrip("/")
        self.agent = options["agent"]
        self.model = options["model"]
        self.timeout = float(options.get("timeout_sec", 180))
        self.keep_sessions = bool(options.get("keep_sessions", False))
        self.auto_start = bool(options.get("auto_start", False))
        self.server_command = options.get("server_command", "")
        self.server_cwd = options.get("server_cwd", "")
        self.state_path = Path(state_path) if state_path else None
        self.session_cache = {}
        if self.state_path and self.state_path.exists():
            try:
                self.session_cache = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.session_cache = {}

        username = os.environ.get(options.get("username_env", "OPENCODE_SERVER_USERNAME"), "opencode")
        password = os.environ.get(options.get("password_env", "OPENCODE_SERVER_PASSWORD"), "")
        self.auth = (username, password) if password else None

        if "/" in self.model:
            self.provider_id, self.model_id = self.model.split("/", 1)
        else:
            self.provider_id, self.model_id = "opencode", self.model

    def health(self, timeout: float = 10):
        response = requests.get(f"{self.base_url}/global/health", auth=self.auth, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def available(self) -> bool:
        try:
            self.health(timeout=4)
            return True
        except requests.RequestException:
            return False

    def _spawn_server(self) -> bool:
        parsed = urlparse(self.base_url)
        port = parsed.port or 4096
        host = parsed.hostname or "127.0.0.1"
        if not self.server_command:
            LOG.error("opencode auto_start on, but server_command is empty")
            return False
        script = (
            f"Start-Process -FilePath '{self.server_command}' "
            f"-ArgumentList @('serve','--port','{port}','--hostname','{host}') "
            f"-WorkingDirectory '{self.server_cwd}' -WindowStyle Hidden"
        )
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", script],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            LOG.error("opencode server start failed: %s", exc)
            return False
        LOG.info("opencode server starting: %s", self.base_url)
        return True

    def ensure_available(self, wait_sec: float = 30) -> bool:
        if self.available():
            return True
        if not self.auto_start:
            return False
        LOG.warning("opencode server down: %s", self.base_url)
        if not self._spawn_server():
            return False
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            time.sleep(2.0)
            if self.available():
                LOG.info("opencode server ready: %s", self.base_url)
                return True
        LOG.error("opencode server still down after %.0fs", wait_sec)
        return False

    def list_sessions(self):
        response = requests.get(f"{self.base_url}/session", auth=self.auth, timeout=20)
        response.raise_for_status()
        return response.json()

    def session_exists(self, session_id: str) -> bool:
        try:
            response = requests.get(f"{self.base_url}/session/{session_id}", auth=self.auth, timeout=20)
        except requests.RequestException:
            return False
        return response.status_code == 200

    def abort(self, session_id: str) -> None:
        try:
            requests.post(f"{self.base_url}/session/{session_id}/abort", auth=self.auth, timeout=20)
        except requests.RequestException:
            pass

    def delete(self, session_id: str) -> None:
        try:
            requests.delete(f"{self.base_url}/session/{session_id}", auth=self.auth, timeout=15)
        except requests.RequestException:
            pass

    def discard(self, session_id: str) -> None:
        self.abort(session_id)
        self.delete(session_id)

    def create_session(self, title: str) -> str:
        response = requests.post(
            f"{self.base_url}/session",
            auth=self.auth,
            json={"title": title},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["id"]

    def _save_state(self) -> None:
        if not self.state_path:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(self.session_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def session_title(self, agent: str) -> str:
        name = agent[3:] if agent.startswith("qq-") else agent
        return f"qq-bridge-{name}"

    def get_or_create_session(self, agent: str) -> str:
        session_id = self.session_cache.get(agent)
        if session_id and self.session_exists(session_id):
            return session_id
        session_id = self.create_session(self.session_title(agent))
        self.session_cache[agent] = session_id
        self._save_state()
        return session_id

    def cleanup_sessions(self) -> int:
        keep = {value for value in self.session_cache.values() if value}
        removed = 0
        try:
            sessions = self.list_sessions()
        except requests.RequestException:
            return 0
        for session in sessions:
            title = str(session.get("title", ""))
            session_id = session.get("id")
            if not session_id:
                continue
            if title == "qq-bridge" or (title.startswith("qq-bridge-") and session_id not in keep):
                self.discard(session_id)
                removed += 1
        return removed

    def send(self, text: str, agent: str = None) -> str:
        agent_name = agent or self.agent
        ephemeral = not self.keep_sessions
        if ephemeral:
            session_id = self.create_session("qq-bridge")
        else:
            session_id = self.get_or_create_session(agent_name)
        try:
            response = requests.post(
                f"{self.base_url}/session/{session_id}/message",
                auth=self.auth,
                json={
                    "agent": agent_name,
                    "model": {
                        "providerID": self.provider_id,
                        "modelID": self.model_id,
                    },
                    "parts": [{"type": "text", "text": text}],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            parts = response.json().get("parts", [])
            texts = [part.get("text", "") for part in parts if part.get("type") == "text"]
            return "\n".join(value for value in texts if value).strip()
        except requests.RequestException:
            if not ephemeral:
                self.abort(session_id)
            raise
        finally:
            if ephemeral:
                self.discard(session_id)
