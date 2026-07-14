from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Verdict(Enum):
    ALLOW = "allow"
    DENY = "deny"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class FailureCategory(Enum):
    COMPILE_ERROR = "compile_error"
    TEST_FAILURE = "test_failure"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


@dataclass
class Action:
    type: str
    params: dict
    thought: str = ""


@dataclass
class ActionResult:
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    output_path: str = ""


@dataclass
class GuardrailResult:
    verdict: Verdict
    reason: str = ""
    layer: str = ""


@dataclass
class FeedbackResult:
    passed: bool
    category: FailureCategory = FailureCategory.UNKNOWN
    details: str = ""
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ConversationTurn:
    action: Action
    result: ActionResult
    feedback: Optional[FeedbackResult] = None