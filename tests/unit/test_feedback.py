import pytest
from harness.action import ActionResult, FailureCategory, FeedbackResult
from harness.feedback import FeedbackLoop, ExitCodeValidator, ContentValidator


def test_exit_code_validator_passes():
    validator = ExitCodeValidator()
    result = ActionResult(success=True, exit_code=0)
    assert validator.check(result) is True


def test_exit_code_validator_fails():
    validator = ExitCodeValidator()
    result = ActionResult(success=False, exit_code=1)
    assert validator.check(result) is False


def test_content_validator_passes():
    import tempfile
    import os
    path = os.path.join(tempfile.gettempdir(), "test_content.txt")
    with open(path, "w") as f:
        f.write("content")
    validator = ContentValidator(expected_path=path)
    result = ActionResult(success=True, exit_code=0, output_path=path)
    assert validator.check(result) is True
    os.unlink(path)


def test_content_validator_fails():
    validator = ContentValidator(expected_path="/nonexistent/path")
    result = ActionResult(success=True, exit_code=0)
    assert validator.check(result) is False


def test_feedback_loop_classify_test_failure():
    loop = FeedbackLoop()
    result = ActionResult(success=False, exit_code=1, stderr="FAILED test_foo")
    feedback = loop.evaluate(result)
    assert feedback.passed is False
    assert feedback.category == FailureCategory.TEST_FAILURE


def test_feedback_loop_classify_compile_error():
    loop = FeedbackLoop()
    result = ActionResult(success=False, exit_code=1, stderr="SyntaxError: invalid syntax")
    feedback = loop.evaluate(result)
    assert feedback.passed is False
    assert feedback.category == FailureCategory.COMPILE_ERROR


def test_feedback_loop_classify_timeout():
    loop = FeedbackLoop()
    result = ActionResult(success=False, exit_code=124, stderr="timed out")
    feedback = loop.evaluate(result)
    assert feedback.passed is False
    assert feedback.category == FailureCategory.TIMEOUT


def test_feedback_loop_classify_unknown():
    loop = FeedbackLoop()
    result = ActionResult(success=False, exit_code=255, stderr="something went wrong")
    feedback = loop.evaluate(result)
    assert feedback.passed is False
    assert feedback.category == FailureCategory.UNKNOWN


def test_feedback_loop_passed():
    loop = FeedbackLoop()
    result = ActionResult(success=True, exit_code=0)
    feedback = loop.evaluate(result)
    assert feedback.passed is True


def test_feedback_loop_should_retry():
    loop = FeedbackLoop(max_retries=3)
    assert loop.should_retry(FeedbackResult(passed=False, category=FailureCategory.TEST_FAILURE, retry_count=0)) is True
    assert loop.should_retry(FeedbackResult(passed=False, category=FailureCategory.TEST_FAILURE, retry_count=2)) is True
    assert loop.should_retry(FeedbackResult(passed=False, category=FailureCategory.TEST_FAILURE, retry_count=3)) is False


def test_feedback_loop_should_not_retry_on_pass():
    loop = FeedbackLoop()
    assert loop.should_retry(FeedbackResult(passed=True)) is False