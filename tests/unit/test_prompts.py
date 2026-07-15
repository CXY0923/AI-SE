import pytest
from harness.prompts import SYSTEM_PROMPT, build_system_prompt


def test_system_prompt_contains_tools():
    prompt = build_system_prompt()
    assert "read" in prompt
    assert "write" in prompt
    assert "edit" in prompt
    assert "shell" in prompt


def test_system_prompt_contains_json_format():
    prompt = build_system_prompt()
    assert "action" in prompt
    assert "params" in prompt
    assert "thought" in prompt


def test_system_prompt_contains_guardrails():
    prompt = build_system_prompt()
    assert "审批" in prompt or "禁止" in prompt


def test_system_prompt_contains_feedback():
    prompt = build_system_prompt()
    assert "反馈" in prompt or "重试" in prompt


def test_system_prompt_customizable():
    prompt = build_system_prompt(tools_override="custom_tools")
    assert "custom_tools" in prompt