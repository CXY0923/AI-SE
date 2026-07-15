import pytest
import tempfile
import os
from harness.action import Action, ActionResult, ConversationTurn
from harness.memory import Memory


@pytest.fixture
def memory():
    tmpdir = tempfile.mkdtemp()
    m = Memory(storage_path=os.path.join(tmpdir, "memory.json"))
    yield m
    import shutil
    shutil.rmtree(tmpdir)


def test_add_and_get_turns(memory):
    turn = ConversationTurn(
        action=Action(type="read", params={"path": "test.py"}),
        result=ActionResult(success=True, stdout="content"),
    )
    memory.add_turn(turn)
    history = memory.get_history()
    assert len(history) == 1
    assert history[0].action.type == "read"


def test_history_trimming(memory):
    for i in range(5):
        turn = ConversationTurn(
            action=Action(type="read", params={"path": f"file{i}.py"}),
            result=ActionResult(success=True),
        )
        memory.add_turn(turn)
    history = memory.get_history(max_turns=3)
    assert len(history) == 3


def test_store_and_retrieve_knowledge(memory):
    memory.store_knowledge("project_language", "Python")
    memory.store_knowledge("test_framework", "pytest")
    result = memory.retrieve_knowledge("project_language")
    assert result == "Python"
    all_knowledge = memory.retrieve_knowledge()
    assert "project_language" in all_knowledge
    assert "test_framework" in all_knowledge


def test_persistence():
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "memory.json")

    m1 = Memory(storage_path=path)
    m1.store_knowledge("key", "value")
    m1.add_turn(ConversationTurn(
        action=Action(type="shell", params={"command": "echo hello"}),
        result=ActionResult(success=True, stdout="hello"),
    ))

    m2 = Memory(storage_path=path)
    assert m2.retrieve_knowledge("key") == "value"
    assert len(m2.get_history()) == 1

    import shutil
    shutil.rmtree(tmpdir)


def test_context_building(memory):
    memory.store_knowledge("project_language", "Python 3.12")
    memory.add_turn(ConversationTurn(
        action=Action(type="read", params={"path": "main.py"}),
        result=ActionResult(success=True, stdout="print('hello')"),
    ))
    context = memory.build_context("修改 main.py 添加新功能")
    assert "Python 3.12" in context
    assert "main.py" in context
    assert "修改 main.py 添加新功能" in context


def test_build_context_with_system_prompt(memory):
    """测试 context 包含 system prompt。"""
    from harness.prompts import build_system_prompt
    context = memory.build_context("测试任务")
    assert "read" in context
    assert "write" in context
    assert "测试任务" in context