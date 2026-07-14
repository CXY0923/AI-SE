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