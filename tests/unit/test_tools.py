import pytest
import tempfile
import os
from harness.action import Action, ActionResult
from harness.tools import ToolExecutor


@pytest.fixture
def executor():
    return ToolExecutor(work_dir=tempfile.gettempdir())


def test_read_file(executor):
    path = os.path.join(tempfile.gettempdir(), "test_read.txt")
    with open(path, "w") as f:
        f.write("hello world")
    result = executor.execute(Action(type="read", params={"path": path}))
    assert result.success is True
    assert result.stdout == "hello world"


def test_read_nonexistent_file(executor):
    result = executor.execute(Action(type="read", params={"path": "/nonexistent/path/file.txt"}))
    assert result.success is False
    assert result.exit_code == 1


def test_write_file(executor):
    path = os.path.join(tempfile.gettempdir(), "test_write.txt")
    result = executor.execute(Action(type="write", params={"path": path, "content": "test content"}))
    assert result.success is True
    with open(path) as f:
        assert f.read() == "test content"
    os.unlink(path)


def test_shell_echo(executor):
    result = executor.execute(Action(type="shell", params={"command": "echo hello"}))
    assert result.success is True
    assert "hello" in result.stdout


def test_shell_failure(executor):
    result = executor.execute(Action(type="shell", params={"command": "exit 1"}))
    assert result.success is False
    assert result.exit_code == 1


def test_unknown_action_type(executor):
    result = executor.execute(Action(type="unknown", params={}))
    assert result.success is False
    assert result.exit_code == 1


def test_edit_file(executor):
    path = os.path.join(tempfile.gettempdir(), "test_edit.txt")
    with open(path, "w") as f:
        f.write("hello world")
    result = executor.execute(Action(
        type="edit",
        params={"path": path, "old_str": "hello", "new_str": "goodbye"}
    ))
    assert result.success is True
    with open(path) as f:
        assert f.read() == "goodbye world"
    os.unlink(path)


def test_edit_file_pattern_not_found(executor):
    path = os.path.join(tempfile.gettempdir(), "test_edit_notfound.txt")
    with open(path, "w") as f:
        f.write("hello world")
    result = executor.execute(Action(
        type="edit",
        params={"path": path, "old_str": "nonexistent", "new_str": "replacement"}
    ))
    assert result.success is False
    assert result.exit_code == 1
    os.unlink(path)