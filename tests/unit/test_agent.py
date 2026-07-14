import pytest
from harness.action import Action, ActionResult, Verdict, GuardrailResult, FeedbackResult, FailureCategory
from harness.llm import MockLLM
from harness.guardrail import RuleEngine, Sandbox, HITLGate, Guardrail
from harness.tools import ToolExecutor
from harness.feedback import FeedbackLoop
from harness.memory import Memory
from harness.agent import AgentHarness


class MockToolExecutor:
    """模拟工具执行器，返回预设结果。"""
    def __init__(self):
        self.executed_actions = []

    def execute(self, action: Action) -> ActionResult:
        self.executed_actions.append(action)
        return ActionResult(success=True, stdout="mock result")


class MockGuardrail:
    def __init__(self, verdict: Verdict = Verdict.ALLOW):
        self.verdict = verdict

    def check(self, action: Action) -> GuardrailResult:
        return GuardrailResult(verdict=self.verdict, layer="test")


def test_agent_completes_task():
    llm = MockLLM(responses=[
        '{"type": "read", "params": {"path": "test.py"}}',
        '{"type": "shell", "params": {"command": "python test.py"}}',
        '{"type": "read", "params": {"path": "test.py"}}',
    ])
    tools = MockToolExecutor()
    guard = MockGuardrail()
    feedback = FeedbackLoop()
    memory = Memory()

    agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory)
    result = agent.run("run test")
    assert result["success"] is True
    assert len(tools.executed_actions) == 3


def test_agent_stops_on_guardrail_deny():
    llm = MockLLM(responses=[
        '{"type": "shell", "params": {"command": "rm -rf /"}}',
    ])
    tools = MockToolExecutor()
    guard = MockGuardrail(verdict=Verdict.DENY)
    feedback = FeedbackLoop()
    memory = Memory()

    agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory)
    result = agent.run("dangerous task")
    assert result["success"] is False
    assert "DENY" in result["reason"]
    assert len(tools.executed_actions) == 0  # 没有执行


def test_agent_stops_after_max_rounds():
    llm = MockLLM(responses=[
        '{"type": "read", "params": {"path": "x.py"}}'
    ] * 25)  # 超过 max_rounds=20
    tools = MockToolExecutor()
    guard = MockGuardrail()
    feedback = FeedbackLoop()
    memory = Memory()

    agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory, max_rounds=5)
    result = agent.run("long task")
    assert result["success"] is False
    assert "max rounds" in result["reason"].lower()
    assert len(tools.executed_actions) <= 5


def test_agent_stops_on_consecutive_failures():
    llm = MockLLM(responses=[
        '{"type": "shell", "params": {"command": "failing command"}}'
    ] * 5)
    tools = MockToolExecutor()

    class FailingFeedback:
        def evaluate(self, result):
            return FeedbackResult(passed=False, category=FailureCategory.TOOL_ERROR, retry_count=0)
        def should_retry(self, fb):
            return fb.retry_count < 3

    guard = MockGuardrail()
    feedback = FailingFeedback()
    memory = Memory()

    agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory, max_rounds=10)
    result = agent.run("failing task")
    assert result["success"] is False
    assert "consecutive failures" in result["reason"].lower()


def test_agent_retries_on_feedback():
    llm = MockLLM(responses=[
        '{"type": "shell", "params": {"command": "fix test"}}',
        '{"type": "shell", "params": {"command": "fix test again"}}',
        '{"type": "shell", "params": {"command": "fix test final"}}',
    ])
    tools = MockToolExecutor()

    call_count = [0]
    class RetryFeedback:
        def evaluate(self, result):
            call_count[0] += 1
            return FeedbackResult(passed=False, category=FailureCategory.TEST_FAILURE, retry_count=call_count[0] - 1)
        def should_retry(self, fb):
            return fb.retry_count < 2

    guard = MockGuardrail()
    feedback = RetryFeedback()
    memory = Memory()

    agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory, max_rounds=10)
    result = agent.run("fix test")
    # 重试 2 次后仍失败，但不应停机（由连续失败判断）
    assert result["success"] is False