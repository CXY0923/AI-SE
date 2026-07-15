import json
import os
from typing import Optional

from harness.action import ConversationTurn


class Memory:
    """上下文与记忆管理，支持会话内历史 + 跨会话知识。"""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.expanduser("~/.harness/memory.json")
        self.history: list[ConversationTurn] = []
        self.knowledge: dict[str, str] = {}
        self._load()

    def add_turn(self, turn: ConversationTurn) -> None:
        self.history.append(turn)
        self._trim_history()
        self._save()

    def get_history(self, max_turns: int = 10) -> list[ConversationTurn]:
        return self.history[-max_turns:]

    def store_knowledge(self, key: str, value: str) -> None:
        self.knowledge[key] = value
        self._save()

    def retrieve_knowledge(self, key: Optional[str] = None) -> str | dict[str, str] | None:
        if key is None:
            return self.knowledge
        return self.knowledge.get(key)

    def build_context(self, task: str) -> str:
        """构建发送给 LLM 的完整上下文（含 system prompt）。"""
        from harness.prompts import build_system_prompt
        parts = [build_system_prompt(), ""]

        parts.append(f"## 当前任务\n{task}")
        parts.append("")

        if self.knowledge:
            parts.append("## 项目知识")
            for k, v in self.knowledge.items():
                parts.append(f"- {k}: {v}")
            parts.append("")

        if self.history:
            parts.append("## 最近操作历史")
            for turn in self.history[-5:]:
                action_desc = f"  → {turn.action.type}({turn.action.params})"
                result_desc = f"  Result: {'OK' if turn.result.success else 'FAIL'}"
                parts.append(action_desc)
                parts.append(result_desc)
            parts.append("")

        parts.append("## 请输出下一步操作")
        return "\n".join(parts)

    def _trim_history(self) -> None:
        if len(self.history) > 100:
            self.history = self.history[-50:]

    def _load(self) -> None:
        if os.path.exists(self.storage_path):
            with open(self.storage_path) as f:
                data = json.load(f)
                self.knowledge = data.get("knowledge", {})
                self.history = []
                for turn_data in data.get("history", []):
                    from harness.action import Action, ActionResult
                    action = Action(**turn_data["action"])
                    result = ActionResult(**turn_data["result"])
                    self.history.append(ConversationTurn(action=action, result=result))

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = {
            "knowledge": self.knowledge,
            "history": [
                {
                    "action": {"type": t.action.type, "params": t.action.params, "thought": t.action.thought},
                    "result": {"success": t.result.success, "exit_code": t.result.exit_code,
                               "stdout": t.result.stdout, "stderr": t.result.stderr,
                               "output_path": t.result.output_path},
                }
                for t in self.history
            ],
        }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)