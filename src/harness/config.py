import os
from dataclasses import dataclass
from typing import Optional
import yaml


@dataclass
class HarnessConfig:
    max_rounds: int = 20
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    hitl_timeout: int = 300
    sandbox_work_dir: str = "."
    sandbox_allow_commands: tuple = ("git", "npm", "python", "pytest", "cat", "ls", "mkdir", "cp", "echo")
    feedback_max_retries: int = 3


def load_config(path: Optional[str] = None) -> HarnessConfig:
    config = HarnessConfig()
    if path is None:
        path = os.path.expanduser("~/.harness/config.yaml")
    if not os.path.exists(path):
        return config
    with open(path) as f:
        raw = yaml.safe_load(f)
    if raw is None or "harness" not in raw:
        return config
    h = raw["harness"]

    if "max_rounds" in h:
        config.max_rounds = h["max_rounds"]

    llm = h.get("llm", {})
    if "provider" in llm:
        config.llm_provider = llm["provider"]
    if "base_url" in llm:
        config.llm_base_url = llm["base_url"]
    if "model" in llm:
        config.llm_model = llm["model"]
    if "temperature" in llm:
        config.llm_temperature = llm["temperature"]

    guardrails = h.get("guardrails", {})
    if "hitl_timeout" in guardrails:
        config.hitl_timeout = guardrails["hitl_timeout"]

    sandbox = h.get("sandbox", {})
    if "work_dir" in sandbox:
        config.sandbox_work_dir = sandbox["work_dir"]
    if "allow_commands" in sandbox:
        config.sandbox_allow_commands = tuple(sandbox["allow_commands"])

    feedback = h.get("feedback", {})
    if "max_retries" in feedback:
        config.feedback_max_retries = feedback["max_retries"]

    return config