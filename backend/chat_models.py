"""Models a student can pick in the chat model selector.

The frontend sends one of these IDs as ``model_id``; anything else is
rejected, so a request can't reach an admin-only or arbitrary Bedrock model
by editing the payload. ``available_chat_models`` is what the selector shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional



@dataclass(frozen=True)
class ChatModel:
    model_id: str
    label: str
    admin_only: bool = False


# Bedrock US cross-Region inference profile IDs, from the AWS model cards.
# All of them run on the app's Bedrock credentials (GPT-6 Luna included).
CHAT_MODELS: List[ChatModel] = [
    ChatModel("us.meta.llama3-3-70b-instruct-v1:0", "Llama 3.3 70B"),
    ChatModel("us.anthropic.claude-sonnet-5-5", "Claude Sonnet 5.5"),
    ChatModel("us.anthropic.claude-haiku-5-5", "Claude Haiku 5.5"),
    ChatModel("us.openai.gpt-6-luna", "GPT-6 Luna"),
    ChatModel("us.anthropic.claude-opus-4-20250514-v1:0", "Claude Opus 4", admin_only=True),
]



def _catalog() -> List[ChatModel]:
    """Selectable models for the active LLM provider.

    The Bedrock list above only works on Bedrock. On another provider
    (Groq, Gemini, ...) students get that provider's default model plus the
    routing models, if configured.
    """
    from backend.config import config

    if config.LLM_PROVIDER == "bedrock":
        return CHAT_MODELS
    models: List[ChatModel] = []
    for model_id in (config.LLM_MODEL_ID, config.LLM_ROUTING_COMPLEX_MODEL, config.LLM_ROUTING_SIMPLE_MODEL):
        if model_id and all(m.model_id != model_id for m in models):
            models.append(ChatModel(model_id, model_id))
    return models


def _by_id() -> dict:
    return {m.model_id: m for m in _catalog()}


class ModelChoiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def is_admin_user(user: dict) -> bool:
    return user.get("role") == "Admin" or bool((user.get("metadata") or {}).get("is_admin"))


def available_chat_models(is_admin: bool) -> List[dict]:
    return [
        {"model_id": m.model_id, "label": m.label, "admin_only": m.admin_only}
        for m in _catalog()
        if is_admin or not m.admin_only
    ]


def validate_model_choice(model_id: Optional[str], is_admin: bool) -> None:
    """Raise ModelChoiceError unless ``model_id`` is Auto (None) or selectable."""
    if not model_id:
        return
    model = _by_id().get(model_id)
    if model is None:
        raise ModelChoiceError(400, f"Unknown model '{model_id}'.")
    if model.admin_only and not is_admin:
        raise ModelChoiceError(403, f"{model.label} is only available to admins.")


def model_label(model_id: Optional[str]) -> str:
    if not model_id:
        return "Auto"
    model = _by_id().get(model_id)
    if model:
        return model.label
    return model_id


__all__ = [
    "CHAT_MODELS",
    "ModelChoiceError",
    "available_chat_models",
    "is_admin_user",
    "model_label",
    "validate_model_choice",
]
