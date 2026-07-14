import pytest
from harness.llm import LLMBase, MockLLM, ParseError


def test_mock_llm_returns_preset_responses():
    mock = MockLLM(responses=["response1", "response2"])
    assert mock.generate("context1") == "response1"
    assert mock.generate("context2") == "response2"


def test_mock_llm_exhausted_raises():
    mock = MockLLM(responses=["only"])
    mock.generate("ctx")
    with pytest.raises(StopIteration):
        mock.generate("ctx")


def test_mock_llm_parse_structured_success():
    mock = MockLLM(responses=[
        '{"type": "read", "params": {"path": "test.py"}}'
    ])
    action = mock.generate_structured("ctx")
    assert action.type == "read"
    assert action.params == {"path": "test.py"}


def test_mock_llm_parse_structured_failure():
    mock = MockLLM(responses=["invalid json"])
    with pytest.raises(ParseError):
        mock.generate_structured("ctx")


def test_llm_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        LLMBase()


def test_mock_llm_reset():
    mock = MockLLM(responses=["a", "b"])
    mock.generate("ctx")
    mock.reset()
    assert mock.generate("ctx") == "a"