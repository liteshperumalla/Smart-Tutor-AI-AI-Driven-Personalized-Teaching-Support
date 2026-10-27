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
from datetime import datetime, timezone
from dataclasses import dataclass, field
import uuid
from backend.log_redaction import user_ref

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
            self.started_at = datetime.now(timezone.utc)

            logger.info(f"Executing saga step: {self.name}")
            self.result = self.action(context)

            self.status = StepStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)

            logger.info(f"Saga step completed: {self.name}")
            return self.result

        except Exception as e:
            self.status = StepStatus.FAILED
            self.error = str(e)
            self.completed_at = datetime.now(timezone.utc)

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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
                state.updated_at = datetime.now(timezone.utc)

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
            state.completed_at = datetime.now(timezone.utc)

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
            state.updated_at = datetime.now(timezone.utc)

            if self.state_store:
                self.state_store.save_state(state)

            # Compensate completed steps in reverse order
            self._compensate(completed_steps, context, state)

            state.status = SagaStatus.COMPENSATED
            state.completed_at = datetime.now(timezone.utc)

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

    # Step 1: Validate quiz — check the quiz_id exists
    def validate_quiz(ctx: Dict[str, Any]) -> bool:
        quiz_id = ctx.get("quiz_id")
        user_id = ctx.get("user_id")
        logger.info("Validating quiz %s for user %s", quiz_id, user_ref(user_id))
        if not quiz_id:
            raise ValueError("quiz_id is required")
        return True

    saga.add_step(
        name="validate_quiz",
        action=validate_quiz,
        compensation=lambda ctx: None  # No compensation needed for validation
    )

    # Step 2: Save submission via quiz_service.save_result
    def save_submission(ctx: Dict[str, Any]) -> str:
        quiz_id = ctx.get("quiz_id")
        user_id = ctx.get("user_id")
        answers = ctx.get("answers", {})
        submission_id = str(uuid.uuid4())
        logger.info("Saving quiz submission: %s", submission_id)
        try:
            from backend.services.quiz_service import get_quiz_service
            svc = ctx.get("quiz_service") or get_quiz_service()
            result = svc.save_result(user_id=user_id, quiz_id=quiz_id, answers=answers)
            ctx["quiz_result"] = result
            return result.quiz_id if hasattr(result, "quiz_id") else submission_id
        except Exception as exc:
            logger.error("save_submission failed: %s", exc, exc_info=True)
            raise

    def delete_submission(ctx: Dict[str, Any]):
        submission_id = ctx.get("save_submission_result")
        logger.info("Compensation: removing quiz submission %s", submission_id)
        # Quiz results are immutable once stored; log the intent for auditing

    saga.add_step(
        name="save_submission",
        action=save_submission,
        compensation=delete_submission
    )

    # Step 3: Grade quiz — derive score from saved result metadata
    def grade_quiz(ctx: Dict[str, Any]) -> Dict[str, Any]:
        result = ctx.get("quiz_result")
        if result:
            d = result.to_dict()
            total = d.get("total_questions", 1) or 1
            score = d.get("score", 0)
            return {"score": score, "max_score": total, "percentage": round(score / total * 100, 1)}
        return {"score": 0, "max_score": 1, "percentage": 0.0}

    def delete_grades(ctx: Dict[str, Any]):
        submission_id = ctx.get("save_submission_result")
        logger.info("Compensation: marking grades void for submission %s", submission_id)

    saga.add_step(
        name="grade_quiz",
        action=grade_quiz,
        compensation=delete_grades
    )

    # Step 4: Record learning assessment (best-effort)
    def record_assessment(ctx: Dict[str, Any]) -> bool:
        result = ctx.get("quiz_result")
        metadata = (result.metadata if result else {}) or {}
        course_id = metadata.get("course_id") or ctx.get("course_id")
        user_id = ctx.get("user_id")
        if course_id:
            try:
                from backend.services.learning_service import get_learning_service
                get_learning_service().record_assessment(
                    user_id, course_id, metadata.get("responses", []), metadata.get("difficulty", "medium")
                )
            except Exception as exc:
                logger.warning("record_assessment failed (best-effort): %s", exc)
        return True

    saga.add_step(
        name="record_assessment",
        action=record_assessment,
        compensation=lambda ctx: None
    )

    # Step 5: Send notification (best-effort — cannot unsend)
    def send_notification(ctx: Dict[str, Any]) -> bool:
        user_id = ctx.get("user_id")
        grade_result = ctx.get("grade_quiz_result", {})
        result = ctx.get("quiz_result")
        metadata = (result.metadata if result else {}) or {}
        logger.info("Sending grade notification to user: %s", user_ref(user_id))
        try:
            from backend.events.event_schemas import QuizGradedEvent
            from backend.events.event_bus import publish_event
            event = QuizGradedEvent(
                user_id=user_id,
                quiz_id=ctx.get("quiz_id", ""),
                score=grade_result.get("score", 0),
                max_score=grade_result.get("max_score", 0),
                percentage=grade_result.get("percentage", 0),
                course_id=metadata.get("course_id") or ctx.get("course_id"),
                responses=metadata.get("responses", []),
                difficulty=metadata.get("difficulty", "medium"),
            )
            publish_event(event)
        except Exception as exc:
            logger.warning("send_notification best-effort failed: %s", exc)
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

    # Step 1: Upload to S3 via resource_service
    def upload_to_s3(ctx: Dict[str, Any]) -> str:
        file_content = ctx.get("file_content")
        filename = ctx.get("filename")
        user_id = ctx.get("user_id")
        s3_key = f"{user_id}/{uuid.uuid4()}_{filename}"
        logger.info("Uploading file to S3: %s", s3_key)
        try:
            from backend.services.resource_service import get_resource_service
            svc = get_resource_service()
            if hasattr(svc, 'upload_to_s3'):
                svc.upload_to_s3(s3_key, file_content)
            else:
                from backend.services import get_storage_backend
                storage = get_storage_backend()
                if hasattr(storage, 'put_object'):
                    storage.put_object(s3_key, file_content)
                else:
                    logger.warning("No S3 upload method available; saga step skipped")
        except Exception as exc:
            logger.error("S3 upload failed for %s: %s", s3_key, exc, exc_info=True)
            raise
        return s3_key

    def delete_from_s3(ctx: Dict[str, Any]):
        s3_key = ctx.get("upload_to_s3_result")
        logger.info("Compensation: deleting S3 object %s", s3_key)
        try:
            from backend.services.resource_service import get_resource_service
            svc = get_resource_service()
            if hasattr(svc, 'delete_s3_object'):
                svc.delete_s3_object(s3_key)
            elif hasattr(svc, 'storage') and hasattr(svc.storage, 'delete_object'):
                svc.storage.delete_object(s3_key)
        except Exception as exc:
            logger.warning("Compensation S3 delete failed for %s: %s", s3_key, exc)

    saga.add_step(
        name="upload_to_s3",
        action=upload_to_s3,
        compensation=delete_from_s3
    )

    # Additional steps omitted for brevity...

    return saga
