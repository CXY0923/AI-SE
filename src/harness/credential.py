import json
import os
from typing import Optional


class CredentialManager:
    def __init__(self, service_name: str = "coding-agent-harness", use_keyring: bool = True):
        self.service_name = service_name
        self._use_keyring = use_keyring
        self._store: dict[str, str] = {}
        self._store_path = os.path.expanduser(f"~/.harness/credentials.json")
        self._load()

    def store_key(self, service: str, key: str) -> None:
        self._store[service] = key
        self._save()

    def get_key(self, service: str) -> Optional[str]:
        return self._store.get(service)

    def delete_key(self, service: str) -> None:
        self._store.pop(service, None)
        self._save()

    def has_key(self, service: str) -> bool:
        return service in self._store

    def list_services(self) -> list[str]:
        return list(self._store.keys())

    def _load(self) -> None:
        if os.path.exists(self._store_path):
            with open(self._store_path) as f:
                self._store = json.load(f)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
        with open(self._store_path, "w") as f:
            json.dump(self._store, f)