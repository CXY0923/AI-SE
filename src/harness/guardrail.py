import fnmatch
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