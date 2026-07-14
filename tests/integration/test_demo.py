"""
机制演示：在 mock LLM 下确定性地复现三个关键行为。

1. 治理护栏拦截一个危险动作
2. 注入一次失败，反馈闭环使 agent 收到反馈并据此改变下一步动作
3. 治理维度的深度行为（HITL 审批）
"""
import os
import pytest
from harness.action import Action, ActionResult, Verdict, GuardrailResult, FeedbackResult, FailureCategory, ConversationTurn
from harness.llm import MockLLM
from harness.guardrail import RuleEngine, Sandbox, HITLGate, Guardrail
from harness.tools import ToolExecutor
from harness.feedback import FeedbackLoop, ExitCodeValidator
from harness.memory import Memory
from harness.agent import AgentHarness


@pytest.fixture(autouse=True)
def cleanup_state():
    yield
    for f in [os.path.expanduser("~/.harness/hitl_state.json"),
              os.path.expanduser("~/.harness/memory.json")]:
        if os.path.exists(f):
            os.remove(f)


class TestDemo1_GuardrailIntercept:
    """演示 1：治理护栏拦截危险动作。"""

    def test_rule_engine_denies_rm_rf(self):
        engine = RuleEngine(
            deny_commands=[{"pattern": "rm -rf /", "reason": "禁止删除根目录"}]
        )
        action = Action(type="shell", params={"command": "rm -rf /"})
        result = engine.check(action)
        assert result.verdict == Verdict.DENY
        assert "禁止删除根目录" in result.reason
        assert result.layer == "rule_engine"

    def test_sandbox_denies_path_escape(self):
        sandbox = Sandbox(work_dir="/workspace")
        action = Action(type="read", params={"path": "/etc/passwd"})
        result = sandbox.check(action)
        assert result.verdict == Verdict.DENY
        assert "逃逸" in result.reason

    def test_full_guardrail_pipeline_deny(self):
        guard = Guardrail(
            rule_engine=RuleEngine(deny_commands=[{"pattern": "rm -rf /", "reason": "deny"}]),
            sandbox=Sandbox(work_dir="/workspace", allow_commands=("git", "python")),
            hitl=HITLGate(timeout=300),
        )
        action = Action(type="shell", params={"command": "rm -rf /"})
        result = guard.check(action)
        assert result.verdict == Verdict.DENY

    def test_agent_loop_stops_on_deny(self):
        llm = MockLLM(responses=[
            '{"type": "shell", "params": {"command": "rm -rf /"}}',
        ])
        tools = ToolExecutor()
        guard = Guardrail(
            rule_engine=RuleEngine(deny_commands=[{"pattern": "rm -rf /", "reason": "禁止删除根目录"}]),
            sandbox=Sandbox(work_dir="."),
            hitl=HITLGate(timeout=0),
        )
        feedback = FeedbackLoop()
        memory = Memory()

        agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory)
        result = agent.run("delete everything")
        assert result["success"] is False
        assert "DENY" in result["reason"]


class TestDemo2_FeedbackLoop:
    """演示 2：反馈闭环使 agent 收到反馈并改变行为。"""

    def test_feedback_loop_classifies_and_retries(self):
        loop = FeedbackLoop(max_retries=3)
        result = ActionResult(success=False, exit_code=1, stderr="FAILED test_main")
        feedback = loop.evaluate(result)
        assert feedback.passed is False
        assert feedback.category == FailureCategory.TEST_FAILURE
        assert loop.should_retry(feedback) is True

        # 重试 3 次后停止
        feedback.retry_count = 3
        assert loop.should_retry(feedback) is False

    def test_validator_chain(self):
        validator = ExitCodeValidator()
        assert validator.check(ActionResult(success=True, exit_code=0)) is True
        assert validator.check(ActionResult(success=False, exit_code=1)) is False

    def test_agent_retries_on_failure(self):
        """agent 在收到失败反馈后重试，改变下一步动作。"""
        llm = MockLLM(responses=[
            '{"type": "shell", "params": {"command": "run failing test"}}',
            '{"type": "shell", "params": {"command": "fix and rerun"}}',
            '{"type": "shell", "params": {"command": "verify fix"}}',
        ])
        tools = ToolExecutor()

        call_count = [0]
        class SmartFeedback:
            def evaluate(self, result):
                call_count[0] += 1
                passed = call_count[0] >= 3
                return FeedbackResult(
                    passed=passed,
                    category=FailureCategory.TEST_FAILURE if not passed else FailureCategory.UNKNOWN,
                    retry_count=call_count[0] - 1,
                )
            def should_retry(self, fb):
                return fb.retry_count < 3

        guard = Guardrail(
            rule_engine=RuleEngine(),
            sandbox=Sandbox(work_dir="."),
            hitl=HITLGate(timeout=0),
        )
        feedback = SmartFeedback()
        memory = Memory()

        agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory, max_rounds=5)
        result = agent.run("fix test")
        assert call_count[0] >= 2


class TestDemo3_HITLGate:
    """演示 3：治理维度深度行为——HITL 审批。"""

    def test_hitl_state_machine(self):
        gate = HITLGate(timeout=300)
        action = Action(type="shell", params={"command": "git push"})

        assert gate.has_pending() is False

        gate.add_pending(action)
        assert gate.has_pending() is True
        assert len(gate.list_pending()) == 1

        result = gate.approve(action)
        assert result.verdict == Verdict.APPROVED
        assert gate.has_pending() is False

    def test_hitl_reject(self):
        gate = HITLGate(timeout=300)
        action = Action(type="shell", params={"command": "npm publish"})
        gate.add_pending(action)
        result = gate.reject(action)
        assert result.verdict == Verdict.REJECTED
        assert gate.has_pending() is False

    def test_hitl_timeout(self):
        gate = HITLGate(timeout=0)
        action = Action(type="shell", params={"command": "git push"})
        result = gate.await_approval(action)
        assert result.verdict == Verdict.TIMEOUT

    def test_hitl_in_agent_loop(self):
        """HITL 在 agent 主循环中工作。"""
        llm = MockLLM(responses=[
            '{"type": "shell", "params": {"command": "git push"}}',
        ])
        tools = ToolExecutor()
        guard = Guardrail(
            rule_engine=RuleEngine(require_approval=[{"pattern": "git push", "reason": "需要审批"}]),
            sandbox=Sandbox(work_dir="."),
            hitl=HITLGate(timeout=0),
        )
        feedback = FeedbackLoop()
        memory = Memory()

        agent = AgentHarness(llm=llm, tools=tools, guardrail=guard, feedback=feedback, memory=memory)
        result = agent.run("push code")
        assert result["success"] is False
        assert "超时" in result["reason"]