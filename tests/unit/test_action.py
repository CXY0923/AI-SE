import pytest
from harness.action import Action, ActionResult, GuardrailResult, FeedbackResult
from harness.action import Verdict, FailureCategory


def test_action_creation():
    action = Action(type="read", params={"path": "main.py"}, thought="need to read")
    assert action.type == "read"
    assert action.params == {"path": "main.py"}
    assert action.thought == "need to read"


def test_action_default_thought():
    action = Action(type="shell", params={"command": "ls"})
    assert action.thought == ""


def test_action_result_defaults():
    r = ActionResult(success=True)
    assert r.exit_code == 0
    assert r.stdout == ""
    assert r.stderr == ""


def test_guardrail_result_deny():
    r = GuardrailResult(verdict=Verdict.DENY, reason="dangerous command", layer="rule_engine")
    assert r.verdict == Verdict.DENY
    assert r.reason == "dangerous command"


def test_feedback_result_defaults():
    f = FeedbackResult(passed=False, category=FailureCategory.TEST_FAILURE)
    assert f.retry_count == 0
    assert f.max_retries == 3


def test_verdict_values():
    assert Verdict.ALLOW.value == "allow"
    assert Verdict.DENY.value == "deny"
    assert Verdict.PENDING.value == "pending"
    assert Verdict.APPROVED.value == "approved"
    assert Verdict.REJECTED.value == "rejected"
    assert Verdict.TIMEOUT.value == "timeout"


def test_failure_category_values():
    assert FailureCategory.COMPILE_ERROR.value == "compile_error"
    assert FailureCategory.TEST_FAILURE.value == "test_failure"
    assert FailureCategory.TIMEOUT.value == "timeout"
    assert FailureCategory.TOOL_ERROR.value == "tool_error"
    assert FailureCategory.UNKNOWN.value == "unknown"