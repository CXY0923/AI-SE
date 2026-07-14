import os
from abc import ABC, abstractmethod
from harness.action import ActionResult, FeedbackResult, FailureCategory


class Validator(ABC):
    @abstractmethod
    def check(self, result: ActionResult) -> bool:
        ...


class ExitCodeValidator(Validator):
    def check(self, result: ActionResult) -> bool:
        return result.exit_code == 0


class ContentValidator(Validator):
    def __init__(self, expected_path: str = ""):
        self.expected_path = expected_path

    def check(self, result: ActionResult) -> bool:
        path = result.output_path or self.expected_path
        if not path:
            return True
        return os.path.exists(path)


class FeedbackLoop:
    def __init__(self, max_retries: int = 3, validators: list | None = None):
        self.max_retries = max_retries
        self.validators = validators or [ExitCodeValidator()]

    def evaluate(self, result: ActionResult) -> FeedbackResult:
        passed = all(v.check(result) for v in self.validators)
        if passed:
            return FeedbackResult(passed=True)
        category = self._classify(result)
        return FeedbackResult(passed=False, category=category, details=result.stderr or result.stdout)

    def should_retry(self, feedback: FeedbackResult) -> bool:
        if feedback.passed:
            return False
        return feedback.retry_count < self.max_retries

    def _classify(self, result: ActionResult) -> FailureCategory:
        if result.exit_code == 124:
            return FailureCategory.TIMEOUT
        stderr = (result.stderr or "").lower()
        stdout = (result.stdout or "").lower()
        combined = stderr + stdout
        if "failed" in combined and "test" in combined:
            return FailureCategory.TEST_FAILURE
        if "syntaxerror" in combined or "compile" in combined:
            return FailureCategory.COMPILE_ERROR
        return FailureCategory.UNKNOWN