import pytest
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


def test_keyring_store_and_get():
    """测试 keyring 模式下存储和读取。"""
    mgr = CredentialManager(service_name="test-harness", use_keyring=True)
    mgr.store_key("test_key", "test-value-123")
    assert mgr.get_key("test_key") == "test-value-123"
    mgr.delete_key("test_key")


def test_keyring_delete():
    """测试 keyring 模式下删除。"""
    mgr = CredentialManager(service_name="test-harness", use_keyring=True)
    mgr.store_key("test_del", "to-delete")
    mgr.delete_key("test_del")
    assert mgr.get_key("test_del") is None


def test_keyring_list_services():
    """测试 keyring 模式下列出服务。"""
    mgr = CredentialManager(service_name="test-harness", use_keyring=True)
    mgr.store_key("svc_a", "val_a")
    mgr.store_key("svc_b", "val_b")
    services = mgr.list_services()
    assert "svc_a" in services
    assert "svc_b" in services
    mgr.delete_key("svc_a")
    mgr.delete_key("svc_b")