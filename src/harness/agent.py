from typing import Optional

from harness.action import Action, ActionResult, Verdict
from harness.llm import LLMBase, ParseError
from harness.guardrail import Guardrail
from harness.tools import ToolExecutor
from harness.feedback import FeedbackLoop
from harness.memory import Memory
from harness.config import HarnessConfig


class AgentHarness:
    """Agent 主循环，编排所有组件。"""

    def __init__(
        self,
        llm: LLMBase,
        tools: ToolExecutor,
        guardrail: Guardrail,
        feedback: FeedbackLoop,
        memory: Memory,
        config: Optional[HarnessConfig] = None,
        max_rounds: int = 20,
    ):
        self.llm = llm
        self.tools = tools
        self.guardrail = guardrail
        self.feedback = feedback
        self.memory = memory
        self.max_rounds = max_rounds
        self.config = config or HarnessConfig()

    def run(self, task: str) -> dict:
        """运行 agent 主循环。"""
        round_num = 0
        consecutive_failures = 0
        parse_failures = 0

        while round_num < self.max_rounds:
            round_num += 1

            # 1. 构建上下文
            context = self.memory.build_context(task)

            # 2. 调用 LLM
            try:
                action = self.llm.generate_structured(context)
            except StopIteration:
                return {
                    "success": True,
                    "reason": "task completed",
                    "rounds": round_num - 1,
                }
            except ParseError:
                parse_failures += 1
                if parse_failures >= 3:
                    return {
                        "success": False,
                        "reason": "3 consecutive parse failures, aborting",
                        "rounds": round_num,
                    }
                continue

            # 3. 治理检查
            guard_result = self.guardrail.check(action)
            if guard_result.verdict == Verdict.DENY:
                return {
                    "success": False,
                    "reason": f"guardrail DENY: {guard_result.reason}",
                    "rounds": round_num,
                    "action": action,
                }
            elif guard_result.verdict == Verdict.PENDING:
                hitl_result = self.guardrail.hitl.await_approval(action)
                if hitl_result.verdict == Verdict.REJECTED:
                    return {
                        "success": False,
                        "reason": f"human rejected: {hitl_result.reason}",
                        "rounds": round_num,
                    }
                elif hitl_result.verdict == Verdict.TIMEOUT:
                    return {
                        "success": False,
                        "reason": "approval timed out",
                        "rounds": round_num,
                    }

            # 4. 执行动作
            result = self.tools.execute(action)

            # 5. 反馈评估
            feedback = self.feedback.evaluate(result)
            self.memory.store_knowledge(f"round_{round_num}_feedback", f"passed={feedback.passed}")

            if feedback.passed:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    return {
                        "success": False,
                        "reason": f"{consecutive_failures} consecutive failures, aborting",
                        "rounds": round_num,
                    }
                if self.feedback.should_retry(feedback):
                    self.memory.store_knowledge("last_failure", feedback.details)
                    continue

            # 6. 记录本轮
            from harness.action import ConversationTurn
            self.memory.add_turn(ConversationTurn(action=action, result=result, feedback=feedback))

            if feedback.passed:
                if action.type == "run_test" or "完成" in (result.stdout or ""):
                    return {
                        "success": True,
                        "reason": "task completed",
                        "rounds": round_num,
                    }

        return {
            "success": False,
            "reason": f"max rounds {self.max_rounds} reached, aborting",
            "rounds": self.max_rounds,
        }