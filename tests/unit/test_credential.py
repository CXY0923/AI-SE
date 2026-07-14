import pytest
from unittest.mock import patch, MagicMock
from harness.credential import CredentialManager

SERVICE_NAME = "coding-agent-harness-test"


@pytest.fixture
def mgr():
    return CredentialManager(service_name=SERVICE_NAME, use_keyring=False)


def test_store_and_get_key(mgr):
    mgr.store_key("openai", "sk-test-key-123")
    assert mgr.get_key("openai") == "sk-test-key-123"


def test_get_key_not_found(mgr):
    assert mgr.get_key("nonexistent") is None


def test_has_key(mgr):
    mgr.store_key("openai", "sk-test")
    assert mgr.has_key("openai") is True
    assert mgr.has_key("nonexistent") is False


def test_delete_key(mgr):
    mgr.store_key("openai", "sk-test")
    mgr.delete_key("openai")
    assert mgr.has_key("openai") is False


def test_list_services(mgr):
    mgr.store_key("openai", "sk-1")
    mgr.store_key("anthropic", "sk-2")
    services = mgr.list_services()
    assert "openai" in services
    assert "anthropic" in services


def test_get_key_returns_none_after_delete(mgr):
    mgr.store_key("openai", "sk-test")
    mgr.delete_key("openai")
    assert mgr.get_key("openai") is None


def test_store_key_overwrites(mgr):
    mgr.store_key("openai", "sk-old")
    mgr.store_key("openai", "sk-new")
    assert mgr.get_key("openai") == "sk-new"