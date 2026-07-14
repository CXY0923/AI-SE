import fnmatch
import json
import os
import threading
from typing import Optional
from harness.action import Action, GuardrailResult, Verdict


class RuleEngine:
    def __init__(self, deny_commands: Optional[list[dict]] = None,
                 require_approval: Optional[list[dict]] = None):
        self.deny_commands = deny_commands or []
        self.require_approval = require_approval or []

    def check(self, action: Action) -> GuardrailResult:
        if action.type != "shell" and action.type != "run_test":
            return GuardrailResult(verdict=Verdict.ALLOW, layer="rule_engine")

        command = action.params.get("command", "")

        for rule in self.deny_commands:
            if rule["pattern"] in command or fnmatch.fnmatch(command, rule["pattern"]):
                return GuardrailResult(
                    verdict=Verdict.DENY,
                    reason=rule.get("reason", "Blacklisted command"),
                    layer="rule_engine",
                )

        for rule in self.require_approval:
            if rule["pattern"] in command or fnmatch.fnmatch(command, rule["pattern"]):
                return GuardrailResult(
                    verdict=Verdict.PENDING,
                    reason=rule.get("reason", "Requires approval"),
                    layer="rule_engine",
                )

        return GuardrailResult(verdict=Verdict.ALLOW, layer="rule_engine")


class Sandbox:
    def __init__(self, work_dir: str = ".", allow_commands: tuple[str, ...] = ()):
        self.work_dir = os.path.realpath(work_dir)
        self.allow_commands = allow_commands

    def check(self, action: Action) -> GuardrailResult:
        if action.type in ("read", "write", "edit"):
            return self._check_path(action)
        if action.type in ("shell", "run_test"):
            return self._check_command(action)
        return GuardrailResult(verdict=Verdict.ALLOW, layer="sandbox")

    def _check_path(self, action: Action) -> GuardrailResult:
        path = action.params.get("path", "")
        resolved = os.path.realpath(path)
        if not resolved.startswith(self.work_dir + os.sep) and resolved != self.work_dir:
            return GuardrailResult(
                verdict=Verdict.DENY,
                reason=f"路径逃逸: {resolved} 不在工作目录 {self.work_dir} 内",
                layer="sandbox",
            )
        return GuardrailResult(verdict=Verdict.ALLOW, layer="sandbox")

    def _check_command(self, action: Action) -> GuardrailResult:
        if not self.allow_commands:
            return GuardrailResult(verdict=Verdict.ALLOW, layer="sandbox")
        command = action.params.get("command", "")
        cmd_name = command.split()[0] if command else ""
        if cmd_name not in self.allow_commands:
            return GuardrailResult(
                verdict=Verdict.DENY,
                reason=f"命令不允许: {cmd_name}，白名单: {', '.join(self.allow_commands)}",
                layer="sandbox",
            )
        return GuardrailResult(verdict=Verdict.ALLOW, layer="sandbox")


class HITLGate:
    """HITL 审批状态机，管理需要人工审批的动作。"""

    def __init__(self, timeout: int = 300, state_path: Optional[str] = None):
        self.timeout = timeout
        self.state_path = state_path or os.path.expanduser("~/.harness/hitl_state.json")
        self._pending: list[dict] = []
        self._lock = threading.Lock()
        self._load()

    def add_pending(self, action: Action) -> None:
        with self._lock:
            entry = {
                "id": len(self._pending) + 1,
                "action_type": action.type,
                "params": action.params,
                "thought": action.thought,
                "status": "pending",
            }
            self._pending.append(entry)
            self._save()

    def has_pending(self) -> bool:
        with self._lock:
            return any(p["status"] == "pending" for p in self._pending)

    def list_pending(self) -> list[dict]:
        with self._lock:
            return [p for p in self._pending if p["status"] == "pending"]

    def approve(self, action: Action) -> GuardrailResult:
        with self._lock:
            self._remove_pending(action)
            self._save()
        return GuardrailResult(verdict=Verdict.APPROVED, reason="人工批准", layer="hitl")

    def reject(self, action: Action) -> GuardrailResult:
        with self._lock:
            self._remove_pending(action)
            self._save()
        return GuardrailResult(verdict=Verdict.REJECTED, reason="人工拒绝", layer="hitl")

    def await_approval(self, action: Action) -> GuardrailResult:
        if self.timeout <= 0:
            return GuardrailResult(verdict=Verdict.TIMEOUT, reason="审批超时", layer="hitl")
        self.add_pending(action)
        return GuardrailResult(verdict=Verdict.PENDING, reason="等待人工审批", layer="hitl")

    def _remove_pending(self, action: Action) -> None:
        self._pending = [
            p for p in self._pending
            if not (p["action_type"] == action.type and p["params"] == action.params)
        ]

    def _load(self) -> None:
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                data = json.load(f)
                self._pending = data.get("pending", [])

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump({"pending": self._pending}, f)