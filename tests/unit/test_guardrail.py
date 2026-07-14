import pytest
import sys
from harness.action import Action, Verdict
from harness.guardrail import RuleEngine


def test_deny_blacklisted_command():
    engine = RuleEngine(
        deny_commands=[{"pattern": "rm -rf /", "reason": "禁止删除根目录"}]
    )
    action = Action(type="shell", params={"command": "rm -rf /"})
    result = engine.check(action)
    assert result.verdict == Verdict.DENY
    assert "禁止删除根目录" in result.reason


def test_allow_safe_command():
    engine = RuleEngine(
        deny_commands=[{"pattern": "rm -rf /", "reason": "test"}]
    )
    action = Action(type="shell", params={"command": "ls -la"})
    result = engine.check(action)
    assert result.verdict == Verdict.ALLOW


def test_deny_blacklist_wildcard():
    engine = RuleEngine(
        deny_commands=[{"pattern": "rm -rf *", "reason": "禁止递归删除"}]
    )
    action = Action(type="shell", params={"command": "rm -rf /tmp"})
    result = engine.check(action)
    assert result.verdict == Verdict.DENY


def test_deny_not_affect_non_shell_actions():
    engine = RuleEngine(
        deny_commands=[{"pattern": "rm -rf *", "reason": "test"}]
    )
    action = Action(type="read", params={"path": "test.py"})
    result = engine.check(action)
    assert result.verdict == Verdict.ALLOW


def test_require_approval_triggers_pending():
    engine = RuleEngine(
        require_approval=[{"pattern": "git push", "reason": "需要人工确认"}]
    )
    action = Action(type="shell", params={"command": "git push origin main"})
    result = engine.check(action)
    assert result.verdict == Verdict.PENDING
    assert "需要人工确认" in result.reason


def test_multiple_rules_first_match_wins():
    engine = RuleEngine(
        deny_commands=[{"pattern": "rm *", "reason": "deny rm"}],
        require_approval=[{"pattern": "rm -rf /tmp", "reason": "需要审批"}],
    )
    action = Action(type="shell", params={"command": "rm -rf /tmp"})
    result = engine.check(action)
    assert result.verdict == Verdict.DENY


def test_rule_engine_layered_correctly():
    engine = RuleEngine(
        deny_commands=[{"pattern": "rm -rf /", "reason": "deny"}],
        require_approval=[{"pattern": "git push", "reason": "approval"}],
    )
    deny_action = Action(type="shell", params={"command": "rm -rf /"})
    assert engine.check(deny_action).verdict == Verdict.DENY
    pending_action = Action(type="shell", params={"command": "git push"})
    assert engine.check(pending_action).verdict == Verdict.PENDING
    allow_action = Action(type="shell", params={"command": "ls"})
    assert engine.check(allow_action).verdict == Verdict.ALLOW


def test_rule_engine_empty_rules():
    engine = RuleEngine()
    action = Action(type="shell", params={"command": "anything"})
    assert engine.check(action).verdict == Verdict.ALLOW


def test_sandbox_denies_path_escape():
    from harness.guardrail import Sandbox
    sandbox = Sandbox(work_dir="/workspace")
    action = Action(type="read", params={"path": "/etc/passwd"})
    result = sandbox.check(action)
    assert result.verdict == Verdict.DENY
    assert "逃逸" in result.reason


def test_sandbox_allows_internal_path():
    from harness.guardrail import Sandbox
    sandbox = Sandbox(work_dir="/workspace")
    action = Action(type="read", params={"path": "/workspace/main.py"})
    result = sandbox.check(action)
    assert result.verdict == Verdict.ALLOW


def test_sandbox_denies_blocked_command():
    from harness.guardrail import Sandbox
    sandbox = Sandbox(work_dir="/workspace", allow_commands=["git", "python"])
    action = Action(type="shell", params={"command": "rm -rf /tmp"})
    result = sandbox.check(action)
    assert result.verdict == Verdict.DENY
    assert "不允许" in result.reason


def test_sandbox_allows_allowed_command():
    from harness.guardrail import Sandbox
    sandbox = Sandbox(work_dir="/workspace", allow_commands=["git", "python"])
    action = Action(type="shell", params={"command": "git status"})
    result = sandbox.check(action)
    assert result.verdict == Verdict.ALLOW


def test_sandbox_relative_path_resolved():
    from harness.guardrail import Sandbox
    sandbox = Sandbox(work_dir="/workspace")
    action = Action(type="read", params={"path": "../../etc/passwd"})
    result = sandbox.check(action)
    assert result.verdict == Verdict.DENY


@pytest.mark.skipif(sys.platform == "win32", reason="symlink requires admin on Windows")
def test_sandbox_resolves_symlink_escape():
    import tempfile
    import os
    from harness.guardrail import Sandbox
    with tempfile.TemporaryDirectory() as tmpdir:
        link_path = os.path.join(tmpdir, "outside_link")
        os.symlink("/etc/passwd", link_path)
        sandbox = Sandbox(work_dir=tmpdir)
        action = Action(type="read", params={"path": link_path})
        result = sandbox.check(action)
        assert result.verdict == Verdict.DENY