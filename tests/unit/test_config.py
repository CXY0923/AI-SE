import pytest
import yaml
import tempfile
import os
from harness.config import HarnessConfig, load_config


def test_default_config():
    config = HarnessConfig()
    assert config.max_rounds == 20
    assert config.llm_provider == "openai"
    assert config.llm_base_url == "https://api.openai.com/v1"
    assert config.llm_model == "gpt-4o"
    assert config.llm_temperature == 0.2
    assert config.hitl_timeout == 300
    assert config.feedback_max_retries == 3
    assert config.sandbox_work_dir == "."
    assert "git" in config.sandbox_allow_commands


def test_load_config_from_yaml():
    data = {
        "harness": {
            "max_rounds": 10,
            "llm": {
                "provider": "openai",
                "base_url": "http://localhost:11434/v1",
                "model": "local-model",
                "temperature": 0.5,
            },
            "guardrails": {
                "hitl_timeout": 60,
            },
            "sandbox": {
                "work_dir": "/workspace",
                "allow_commands": ["python", "pytest"],
            },
            "feedback": {
                "max_retries": 5,
            },
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        config = load_config(path)
        assert config.max_rounds == 10
        assert config.llm_base_url == "http://localhost:11434/v1"
        assert config.llm_model == "local-model"
        assert config.llm_temperature == 0.5
        assert config.hitl_timeout == 60
        assert config.sandbox_work_dir == "/workspace"
        assert config.sandbox_allow_commands == ("python", "pytest")
        assert config.feedback_max_retries == 5
    finally:
        os.unlink(path)


def test_load_config_missing_file_returns_default():
    config = load_config("/nonexistent/path/config.yaml")
    assert config.max_rounds == 20


def test_load_config_partial_overrides():
    data = {"harness": {"max_rounds": 5}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        config = load_config(path)
        assert config.max_rounds == 5
        assert config.llm_provider == "openai"  # 默认值
    finally:
        os.unlink(path)