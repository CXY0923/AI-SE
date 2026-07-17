import json
import os
import keyring
from keyring.errors import NoKeyringError
from typing import Optional


class CredentialManager:
    """凭据管理器，通过 OS Keyring 安全存储 API Key。"""

    def __init__(self, service_name: str = "coding-agent-harness", use_keyring: bool = True):
        self.service_name = service_name
        self._use_keyring = use_keyring
        self._store: dict[str, str] = {}
        self._store_path = os.path.expanduser(f"~/.harness/credentials.json")
        if not use_keyring:
            self._load()

    def store_key(self, service: str, key: str) -> None:
        if self._use_keyring:
            try:
                keyring.set_password(self.service_name, service, key)
            except NoKeyringError:
                raise RuntimeError(
                    "OS Keyring 不可用（通常是容器内无 D-Bus/Secret Service 后端）。"
                    "请改用 OPENAI_API_KEY 环境变量。"
                )
            self._store[service] = key
        else:
            self._store[service] = key
            self._save()

    def get_key(self, service: str) -> Optional[str]:
        if self._use_keyring:
            try:
                return keyring.get_password(self.service_name, service)
            except NoKeyringError:
                return None
        return self._store.get(service)

    def delete_key(self, service: str) -> None:
        if self._use_keyring:
            try:
                keyring.delete_password(self.service_name, service)
            except NoKeyringError:
                pass
            self._store.pop(service, None)
        else:
            self._store.pop(service, None)
            self._save()

    def has_key(self, service: str) -> bool:
        if self._use_keyring:
            try:
                return keyring.get_password(self.service_name, service) is not None
            except NoKeyringError:
                return False
        return service in self._store

    def list_services(self) -> list[str]:
        if self._use_keyring:
            # keyring 不直接支持列出所有服务，使用文件回退记录
            return list(self._store.keys())
        return list(self._store.keys())

    def _load(self) -> None:
        if os.path.exists(self._store_path):
            with open(self._store_path) as f:
                self._store = json.load(f)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
        with open(self._store_path, "w") as f:
            json.dump(self._store, f)