import pytest
from unittest.mock import patch, MagicMock
from harness.cli import main


def test_cli_setup_requires_key(monkeypatch):
    inputs = iter(["sk-test-key-123"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr("getpass.getpass", lambda _: "sk-test-key-123")

    with patch("harness.cli.CredentialManager") as MockCred:
        instance = MockCred.return_value
        instance.has_key.return_value = False
        from harness.cli import setup_command
        setup_command()
        instance.store_key.assert_called_once()


def test_cli_status_shows_configured(monkeypatch, capsys):
    with patch("harness.cli.CredentialManager") as MockCred:
        instance = MockCred.return_value
        instance.has_key.return_value = True
        instance.list_services.return_value = ["openai"]

        from harness.cli import status_command
        status_command()
        captured = capsys.readouterr()
        assert "✅" in captured.out
        assert "openai" in captured.out
        assert "sk-" not in captured.out  # 不显示明文


def test_cli_status_shows_not_configured(monkeypatch, capsys):
    with patch("harness.cli.CredentialManager") as MockCred:
        instance = MockCred.return_value
        instance.has_key.return_value = False
        instance.list_services.return_value = []

        from harness.cli import status_command
        status_command()
        captured = capsys.readouterr()
        assert "未配置" in captured.out


def test_cli_approve_no_pending(monkeypatch, capsys):
    from harness.cli import approve_command
    from harness.guardrail import HITLGate
    import tempfile
    import os

    tmpdir = tempfile.mkdtemp()
    state_path = os.path.join(tmpdir, "hitl.json")
    gate = HITLGate(timeout=300, state_path=state_path)

    monkeypatch.setattr("harness.cli.get_hitl_gate", lambda: gate)
    approve_command()
    captured = capsys.readouterr()
    assert "待审批" in captured.out or "pending" in captured.out.lower()

    import shutil
    shutil.rmtree(tmpdir)