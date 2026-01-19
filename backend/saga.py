"""
Saga Pattern Implementation for Distributed Transactions
Ensures eventual consistency across microservices

Implements:
- Choreography-based sagas (event-driven)
- Orchestration-based sagas (coordinator)
- Compensation logic for rollback
- Saga state management
"""

import logging
import json
from enum import Enum
from typing import Callable, List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import uuid

logger = logging.getLogger(__name__)


class SagaStatus(str, Enum):
    """Saga execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepStatus(str, Enum):
    """Individual step status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """
    Individual step in a saga

    Each step has:
    - Action: Forward transaction
    - Compensation: Rollback action
    """
    name: str
    action: Callable
    compensation: Callable
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def execute(self, context: Dict[str, Any]) -> Any:
        """Execute the forward action"""
        try:
            self.status = StepStatus.RUNNING
            self.started_at = datetime.utcnow()

            logger.info(f"Executing saga step: {self.name}")
            self.result = self.action(context)

            self.status = StepStatus.COMPLETED
            self.completed_at = datetime.utcnow()

            logger.info(f"Saga step completed: {self.name}")
            return self.result

        except Exception as e:
            self.status = StepStatus.FAILED
            self.error = str(e)
            self.completed_at = datetime.utcnow()

            logger.error(f"Saga step failed: {self.name} - {e}", exc_info=True)
            raise

    def compensate(self, context: Dict[str, Any]) -> Any:
        """Execute the compensation action"""
        try:
            self.status = StepStatus.COMPENSATING

            logger.info(f"Compensating saga step: {self.name}")
            result = self.compensation(context)

            self.status = StepStatus.COMPENSATED
            logger.info(f"Saga step compensated: {self.name}")

            return result

        except Exception as e:
            logger.error(f"Compensation failed for step {self.name}: {e}", exc_info=True)
            raise


@dataclass
class SagaState:
    """Saga execution state"""
    saga_id: str
    saga_name: str
    status: SagaStatus
    steps: List[SagaStep]
    context: Dict[str, Any]
    current_step_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize saga state"""
        return {
            "saga_id": self.saga_id,
            "saga_name": self.saga_name,
            "status": self.status.value,
            "current_step_index": self.current_step_index,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "error": step.error,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                }
                for step in self.steps
            ]
        }


class SagaOrchestrator:
    """
    Orchestration-based saga coordinator

    Usage:
        saga = SagaOrchestrator("quiz-submission-saga")

        saga.add_step(
            name="validate_quiz",
            action=validate_quiz,
            compensation=lambda ctx: None  # No compensation needed
        )

        saga.add_step(
            name="save_submission",
            action=save_submission,
            compensation=delete_submission
        )

        saga.add_step(
            name="grade_quiz",
            action=grade_quiz,
            compensation=delete_grades
        )

        result = saga.execute(context={"user_id": "123", "quiz_id": "456"})
    """

    def __init__(
        self,
        saga_name: str,
        state_store: Optional['SagaStateStore'] = None
    ):
        """
        Initialize saga orchestrator

        Args:
            saga_name: Name of the saga
            state_store: Optional state store for persistence
        """
        self.saga_id = str(uuid.uuid4())
        self.saga_name = saga_name
        self.steps: List[SagaStep] = []
        self.state_store = state_store

        logger.info(f"Created saga: {saga_name} (ID: {self.saga_id})")

    def add_step(
        self,
        name: str,
        action: Callable[[Dict[str, Any]], Any],
        compensation: Callable[[Dict[str, Any]], Any],
    ) -> 'SagaOrchestrator':
        """
        Add a step to the saga

        Args:
            name: Step name
            action: Forward transaction function
            compensation: Rollback function

        Returns:
            Self for chaining
        """
        step = SagaStep(name=name, action=action, compensation=compensation)
        self.steps.append(step)

        logger.debug(f"Added step to saga {self.saga_name}: {name}")
        return self

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the saga

        Args:
            context: Initial context for saga execution

        Returns:
            Saga execution result

        Raises:
            SagaExecutionError: If saga fails and cannot be compensated
        """
        if context is None:
            context = {}

        # Create saga state
        state = SagaState(
            saga_id=self.saga_id,
            saga_name=self.saga_name,
            status=SagaStatus.RUNNING,
            steps=self.steps,
            context=context,
        )

        # Save initial state
        if self.state_store:
            self.state_store.save_state(state)

        completed_steps: List[SagaStep] = []

        try:
            # Execute steps sequentially
            for i, step in enumerate(self.steps):
                state.current_step_index = i
                state.updated_at = datetime.utcnow()

                # Execute step
                result = step.execute(context)

                # Add result to context for next steps
                context[f"{step.name}_result"] = result

                completed_steps.append(step)

                # Save state after each step
                if self.state_store:
                    self.state_store.save_state(state)

            # All steps completed successfully
            state.status = SagaStatus.COMPLETED
            state.completed_at = datetime.utcnow()

            if self.state_store:
                self.state_store.save_state(state)

            logger.info(f"Saga completed successfully: {self.saga_name}")

            return {
                "saga_id": self.saga_id,
                "status": "completed",
                "context": context,
            }

        except Exception as e:
            # Saga failed, start compensation
            logger.error(f"Saga failed: {self.saga_name} - {e}", exc_info=True)

            state.status = SagaStatus.COMPENSATING
            state.error = str(e)
            state.updated_at = datetime.utcnow()

            if self.state_store:
                self.state_store.save_state(state)

            # Compensate completed steps in reverse order
            self._compensate(completed_steps, context, state)

            state.status = SagaStatus.COMPENSATED
            state.completed_at = datetime.utcnow()

            if self.state_store:
                self.state_store.save_state(state)

            raise SagaExecutionError(
                f"Saga {self.saga_name} failed and was compensated. Original error: {e}"
            ) from e

    def _compensate(
        self,
        completed_steps: List[SagaStep],
        context: Dict[str, Any],
        state: SagaState,
    ):
        """Compensate completed steps in reverse order"""
        logger.info(f"Starting compensation for saga: {self.saga_name}")

        compensation_errors = []

        # Compensate in reverse order
        for step in reversed(completed_steps):
            try:
                step.compensate(context)
            except Exception as comp_error:
                logger.error(
                    f"Compensation failed for step {step.name}: {comp_error}",
                    exc_info=True
                )
                compensation_errors.append({
                    "step": step.name,
                    "error": str(comp_error)
                })

        if compensation_errors:
            logger.error(
                f"Some compensations failed for saga {self.saga_name}: {compensation_errors}"
            )


class SagaExecutionError(Exception):
    """Raised when saga execution fails"""
    pass


class SagaStateStore:
    """
    Store saga state for recovery and monitoring

    In production, this should use DynamoDB or another persistent store
    """

    def __init__(self):
        self.states: Dict[str, SagaState] = {}

    def save_state(self, state: SagaState):
        """Save saga state"""
        self.states[state.saga_id] = state
        logger.debug(f"Saved saga state: {state.saga_id}")

    def get_state(self, saga_id: str) -> Optional[SagaState]:
        """Get saga state by ID"""
        return self.states.get(saga_id)

    def list_states(
        self,
        status: Optional[SagaStatus] = None,
        limit: int = 100
    ) -> List[SagaState]:
        """List saga states with optional filtering"""
        states = list(self.states.values())

        if status:
            states = [s for s in states if s.status == status]

        # Sort by created_at descending
        states.sort(key=lambda s: s.created_at, reverse=True)

        return states[:limit]


# Global state store
_saga_state_store: Optional[SagaStateStore] = None


def get_saga_state_store() -> SagaStateStore:
    """Get global saga state store"""
    global _saga_state_store
    if _saga_state_store is None:
        _saga_state_store = SagaStateStore()
    return _saga_state_store


# Example Saga: Quiz Submission

def create_quiz_submission_saga() -> SagaOrchestrator:
    """
    Example: Quiz submission saga

    Steps:
    1. Validate quiz
    2. Save submission
    3. Grade quiz
    4. Send notification
    """
    saga = SagaOrchestrator("quiz-submission-saga", get_saga_state_store())

    # Step 1: Validate quiz
    def validate_quiz(ctx: Dict[str, Any]) -> bool:
        quiz_id = ctx.get("quiz_id")
        user_id = ctx.get("user_id")

        logger.info(f"Validating quiz {quiz_id} for user {user_id}")

        # TODO: Actual validation logic
        # from backend.services.quiz_service import validate_quiz_submission
        # return validate_quiz_submission(quiz_id, user_id)

        return True

    saga.add_step(
        name="validate_quiz",
        action=validate_quiz,
        compensation=lambda ctx: None  # No compensation needed for validation
    )

    # Step 2: Save submission
    def save_submission(ctx: Dict[str, Any]) -> str:
        submission_id = str(uuid.uuid4())

        logger.info(f"Saving quiz submission: {submission_id}")

        # TODO: Save to database
        # from backend.services.quiz_service import save_quiz_submission
        # save_quiz_submission(submission_id, ctx)

        return submission_id

    def delete_submission(ctx: Dict[str, Any]):
        submission_id = ctx.get("save_submission_result")
        logger.info(f"Deleting quiz submission: {submission_id}")

        # TODO: Delete from database
        # from backend.services.quiz_service import delete_quiz_submission
        # delete_quiz_submission(submission_id)

    saga.add_step(
        name="save_submission",
        action=save_submission,
        compensation=delete_submission
    )

    # Step 3: Grade quiz
    def grade_quiz(ctx: Dict[str, Any]) -> Dict[str, Any]:
        submission_id = ctx.get("save_submission_result")

        logger.info(f"Grading quiz submission: {submission_id}")

        # TODO: Grade quiz
        # from backend.services.quiz_service import grade_quiz
        # return grade_quiz(submission_id)

        return {
            "score": 85.0,
            "max_score": 100.0,
            "percentage": 85.0,
        }

    def delete_grades(ctx: Dict[str, Any]):
        submission_id = ctx.get("save_submission_result")
        logger.info(f"Deleting grades for submission: {submission_id}")

        # TODO: Delete grades
        # from backend.services.quiz_service import delete_grades
        # delete_grades(submission_id)

    saga.add_step(
        name="grade_quiz",
        action=grade_quiz,
        compensation=delete_grades
    )

    # Step 4: Send notification
    def send_notification(ctx: Dict[str, Any]) -> bool:
        user_id = ctx.get("user_id")
        grade_result = ctx.get("grade_quiz_result")

        logger.info(f"Sending grade notification to user: {user_id}")

        # TODO: Send notification
        # from backend.services.notification_service import send_quiz_result
        # send_quiz_result(user_id, grade_result)

        return True

    saga.add_step(
        name="send_notification",
        action=send_notification,
        compensation=lambda ctx: None  # Can't unsend notification
    )

    return saga


# Example Saga: Document Upload and Processing

def create_document_processing_saga() -> SagaOrchestrator:
    """
    Example: Document processing saga

    Steps:
    1. Upload to S3
    2. Create metadata record
    3. Generate embeddings
    4. Update index
    """
    saga = SagaOrchestrator("document-processing-saga", get_saga_state_store())

    # Step 1: Upload to S3
    def upload_to_s3(ctx: Dict[str, Any]) -> str:
        file_content = ctx.get("file_content")
        filename = ctx.get("filename")
        user_id = ctx.get("user_id")

        s3_key = f"{user_id}/{uuid.uuid4()}_{filename}"

        logger.info(f"Uploading file to S3: {s3_key}")

        # TODO: Upload to S3
        # from backend.services.storage_service import upload_to_s3
        # upload_to_s3(s3_key, file_content)

        return s3_key

    def delete_from_s3(ctx: Dict[str, Any]):
        s3_key = ctx.get("upload_to_s3_result")
        logger.info(f"Deleting file from S3: {s3_key}")

        # TODO: Delete from S3
        # from backend.services.storage_service import delete_from_s3
        # delete_from_s3(s3_key)

    saga.add_step(
        name="upload_to_s3",
        action=upload_to_s3,
        compensation=delete_from_s3
    )

    # Additional steps omitted for brevity...

    return saga
