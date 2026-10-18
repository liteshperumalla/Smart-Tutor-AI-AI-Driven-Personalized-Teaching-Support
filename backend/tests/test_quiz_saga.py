"""
Tests for Quiz Submission Saga and Distributed Transaction Orchestration
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from backend.saga import (
    SagaOrchestrator,
    SagaStatus,
    StepStatus,
    SagaExecutionError,
    create_quiz_submission_saga,
    get_saga_state_store,
)
from backend.services.models import QuizResult


def test_create_quiz_submission_saga_structure():
    saga = create_quiz_submission_saga()
    step_names = [step.name for step in saga.steps]
    assert "validate_quiz" in step_names
    assert "save_submission" in step_names
    assert "grade_quiz" in step_names
    assert "record_assessment" in step_names
    assert "send_notification" in step_names


def test_quiz_saga_executes_successfully():
    mock_quiz_service = MagicMock()
    mock_result = QuizResult(
        id="quiz-saga-1",
        user_id="test_student",
        score=4,
        total_questions=5,
        percentage=80.0,
        created_at=datetime.now(timezone.utc),
        metadata={
            "course_id": "info-5731",
            "responses": [{"question_id": "q1", "correct": True}],
            "difficulty": "medium",
        },
    )
    mock_quiz_service.save_result.return_value = mock_result

    saga = create_quiz_submission_saga()
    context = {
        "user_id": "test_student",
        "quiz_id": "quiz-saga-1",
        "answers": {"q1": "A", "q2": "B"},
        "quiz_service": mock_quiz_service,
    }

    outcome = saga.execute(context)

    assert outcome["status"] == "completed"
    assert outcome["context"]["quiz_result"] == mock_result
    assert outcome["context"]["grade_quiz_result"]["score"] == 4
    assert outcome["context"]["grade_quiz_result"]["percentage"] == 80.0
    mock_quiz_service.save_result.assert_called_once_with(
        user_id="test_student", quiz_id="quiz-saga-1", answers={"q1": "A", "q2": "B"}
    )


def test_quiz_saga_triggers_compensation_on_failure():
    mock_quiz_service = MagicMock()
    # Step 2 succeeds
    mock_result = QuizResult(
        id="quiz-saga-fail",
        user_id="test_student",
        score=2,
        total_questions=2,
        percentage=100.0,
        created_at=datetime.now(timezone.utc),
    )
    mock_quiz_service.save_result.return_value = mock_result

    saga = create_quiz_submission_saga()

    compensated = {"called": False}

    def step_before_failure(ctx):
        return True

    def compensation_for_step(ctx):
        compensated["called"] = True

    saga.add_step(name="step_to_rollback", action=step_before_failure, compensation=compensation_for_step)

    # Inject a failing step
    def failing_step(ctx):
        raise RuntimeError("Downstream ledger failed to record completion")

    saga.add_step(name="failing_ledger", action=failing_step, compensation=lambda ctx: None)

    context = {
        "user_id": "test_student",
        "quiz_id": "quiz-saga-fail",
        "answers": {"q1": "A"},
        "quiz_service": mock_quiz_service,
    }

    with pytest.raises(SagaExecutionError) as exc_info:
        saga.execute(context)

    assert "Downstream ledger failed" in str(exc_info.value)
    # Verify rollback compensation executed
    assert compensated["called"] is True
