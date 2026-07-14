import fnmatch
import os
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