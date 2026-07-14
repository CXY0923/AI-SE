import json
from abc import ABC, abstractmethod
from openai import OpenAI
from harness.action import Action


class ParseError(Exception):
    pass


class LLMBase(ABC):

    @abstractmethod
    def generate(self, context: str) -> str:
        ...

    def generate_structured(self, context: str) -> Action:
        raw = self.generate(context)
        try:
            data = json.loads(raw)
            return Action(
                type=data["type"],
                params=data.get("params", {}),
                thought=data.get("thought", ""),
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ParseError(f"Failed to parse LLM output: {e}") from e


class OpenAILLM(LLMBase):

    def __init__(self, api_key: str, model: str = "gpt-4o",
                 base_url: str = "https://api.openai.com/v1",
                 temperature: float = 0.2):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature

    def generate(self, context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": context}],
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""


class MockLLM(LLMBase):

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._index = 0

    def generate(self, context: str) -> str:
        if self._index >= len(self._responses):
            raise StopIteration("MockLLM has no more responses")
        response = self._responses[self._index]
        self._index += 1
        return response

    def reset(self) -> None:
        self._index = 0