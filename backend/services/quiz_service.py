from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.redis_cache import get_redis_cache
from backend.services import get_storage_backend
from backend.services.models import QuizResult
from backend.s3_retriever import S3Retriever
from backend.bedrock_embeddings import BedrockEmbeddings

logger = logging.getLogger(__name__)

_MODULE_TOPIC_LABELS = {
    1: "Orientation & Core Concepts",
    2: "Python Basics",
    3: "Python Basics (Part 2)",
    4: "Web Scraping",
    5: "Data Cleaning & Preprocessing",
    6: "Feature Extraction & Word Embeddings",
    8: "Information Extraction & Knowledge Graphs",
    10: "Topic Modeling",
    12: "Sentiment Analysis",
    13: "Text Classification & Clustering",
    14: "LLM Overview & RAG",
}


def _extract_module_number(value: str) -> Optional[int]:
    match = re.search(r"module\s*(\d+)", value, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _resolve_topic_label(folder: str) -> str:
    module_number = _extract_module_number(folder)
    if module_number and module_number in _MODULE_TOPIC_LABELS:
        return _MODULE_TOPIC_LABELS[module_number]
    return folder


def _normalize_source_path(path: str) -> str:
    normalized = (path or "").strip().lstrip("/")
    if normalized.startswith("modules/"):
        return normalized[len("modules/") :]
    return normalized

# Diverse query angles to get varied RAG context per attempt
_QUERY_VARIANTS = [
    "Explain the key definitions and terminology from this topic",
    "What are the main differences and comparisons between concepts",
    "Describe a real-world application or use case of these ideas",
    "What are the advantages and disadvantages discussed in the material",
    "Summarize the step-by-step process or methodology described",
    "What are the common pitfalls or misconceptions about this subject",
    "How do the components or layers of this system interact",
    "What are the security or performance considerations mentioned",
]

QUESTION_TEMPLATE = """You are an expert quiz question writer. Based on the following context, generate ONE high-quality multiple-choice question with four options (A, B, C, D).

Context:
{context_str}

Requirements:
- The question should test UNDERSTANDING, not just memorization of facts.
- All four options must be plausible — avoid obviously wrong distractors.
- Include a 2-3 sentence explanation of why the correct answer is right.

Return ONLY a JSON object in this exact format:
{{
  "question": "Your question here?",
  "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
  "correct_answer_letter": "A",
  "explanation": "2-3 sentence explanation of why this answer is correct."
}}

Do not include any text outside the JSON object."""

# TTL for quiz store entries (1 hour)
_QUIZ_STORE_TTL_SECONDS = 3600


class QuizGenerationError(RuntimeError):
    """Raised when the quiz generator cannot produce valid questions."""


class QuizService:
    _QUIZ_KEY_PREFIX = "quiz:"

    def __init__(self) -> None:
        self.storage = get_storage_backend()
        self.s3_retriever = S3Retriever(similarity_top_k=5)
        from backend.llm_provider import get_llm
        self.llm = get_llm()
        self._folder_cache: Optional[Dict[str, List[str]]] = None
        # Redis-backed quiz store shared across all workers
        self._redis = get_redis_cache()

    @staticmethod
    def _extract_completion_text(llm_response: object) -> str:
        text = getattr(llm_response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        return str(llm_response).strip()

    @staticmethod
    def _normalize_correct_answer_letter(payload: Dict[str, object]) -> Optional[str]:
        raw_value = payload.get("correct_answer_letter")
        if isinstance(raw_value, str):
            candidate = raw_value.strip().upper()
            candidate = re.sub(
                r"^(?:OPTION|ANSWER|CORRECT ANSWER)\s*[:\-]?\s*",
                "",
                candidate,
            )
            match = re.match(r"^([A-D])(?:[\W_].*)?$", candidate)
            if match:
                return match.group(1)

            options = payload.get("options")
            if isinstance(options, list):
                normalized_options = [
                    str(opt).strip()
                    for opt in options
                    if isinstance(opt, str) and opt.strip()
                ]
                for index, option in enumerate(normalized_options[:4]):
                    if candidate == option.upper():
                        return chr(ord("A") + index)

        raw_answer = payload.get("correct_answer")
        if isinstance(raw_answer, str):
            payload["correct_answer_letter"] = raw_answer
            return QuizService._normalize_correct_answer_letter(payload)

        return None

    def _fetch_s3_chunk_context(
        self, file_paths: List[str], max_chunks: int = 8, chars_per_chunk: int = 1200
    ) -> str:
        if not file_paths:
            return ""

        try:
            from backend.cloud.aws_helpers import get_boto3_client

            s3 = get_boto3_client("s3")
            context_parts: List[str] = []
            seen_keys: set[str] = set()

            for file_path in file_paths:
                normalized_path = _normalize_source_path(file_path)
                if not normalized_path:
                    continue
                chunk_prefix = f"chunks/{normalized_path}/"
                paginator = s3.get_paginator("list_objects_v2")
                chunk_count = 0

                for page in paginator.paginate(
                    Bucket=config.S3_DOCUMENTS_BUCKET,
                    Prefix=chunk_prefix,
                    PaginationConfig={"MaxItems": max_chunks},
                ):
                    for obj in page.get("Contents", []):
                        key = obj.get("Key", "")
                        if not key.endswith(".txt") or key in seen_keys:
                            continue
                        try:
                            response = s3.get_object(
                                Bucket=config.S3_DOCUMENTS_BUCKET, Key=key
                            )
                            text = response["Body"].read().decode(
                                "utf-8", errors="ignore"
                            ).strip()
                        except Exception as exc:
                            logger.warning(
                                "Failed to read quiz chunk context %s: %s", key, exc
                            )
                            continue

                        if not text:
                            continue

                        context_parts.append(text[:chars_per_chunk])
                        seen_keys.add(key)
                        chunk_count += 1

                        if len(context_parts) >= max_chunks or chunk_count >= 2:
                            break

                    if len(context_parts) >= max_chunks or chunk_count >= 2:
                        break

                if len(context_parts) >= max_chunks:
                    break

            return "\n\n".join(context_parts)
        except Exception as exc:
            logger.warning("Failed to load quiz fallback chunk context: %s", exc)
            return ""

    def _get_folder_structure(self) -> Dict[str, List[str]]:
        if self._folder_cache is not None:
            return self._folder_cache

        from backend.cloud.aws_helpers import get_boto3_client

        s3 = get_boto3_client("s3")
        structure: Dict[str, List[str]] = {}

        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=config.S3_DOCUMENTS_BUCKET, Prefix="modules/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith((".pdf", ".pptx", ".ppt", ".docx", ".ipynb")):
                    folder = str(key.rsplit("/", 1)[0]).replace("modules/", "")
                    structure.setdefault(folder, []).append(key)

        self._folder_cache = structure
        return structure

    def list_folders(self) -> List[Dict[str, str]]:
        structure = self._get_folder_structure()
        buckets: Dict[str, Dict[str, str]] = {}
        for folder, files in structure.items():
            label = folder.split("/")[-1] or folder
            label = _resolve_topic_label(label)
            key = re.sub(r"[^a-z0-9]", "", label.lower())
            entry = buckets.get(key)
            candidate = {
                "path": folder,
                "label": label,
                "file_count": len(files),
            }
            if entry is None or candidate["file_count"] > entry["file_count"]:
                buckets[key] = candidate
        folders = list(buckets.values())
        folders.sort(
            key=lambda item: (
                _extract_module_number(item["path"]) is None,
                _extract_module_number(item["path"]) or 0,
                item["label"].lower(),
            )
        )
        return folders

    def _get_context_for_query(self, query: str, file_paths: List[str]) -> str:
        """Get context from S3 for a specific query, filtered to selected folders."""
        try:
            nodes = self.s3_retriever.retrieve(query)

            # Post-retrieval filtering: keep only nodes from selected folders
            filtered_nodes = []
            normalized_file_paths = [_normalize_source_path(path) for path in file_paths]
            for node in nodes:
                metadata = getattr(node.node, "metadata", {}) or {}
                source = _normalize_source_path(
                    metadata.get("source_file") or metadata.get("s3_key") or ""
                )
                # Check if this node's source matches any of the selected file paths
                if file_paths and source:
                    if any(
                        fp and (source.endswith(fp) or fp in source)
                        for fp in normalized_file_paths
                    ):
                        filtered_nodes.append(node)
                else:
                    # If no metadata to filter on, include all nodes
                    filtered_nodes.append(node)

            # Use filtered nodes if any matched, otherwise fall back to all nodes
            nodes_to_use = filtered_nodes if filtered_nodes else nodes

            context_parts = []
            for node in nodes_to_use:
                text = node.node.text if hasattr(node.node, "text") else str(node.node)
                context_parts.append(text)
            context = "\n\n".join(context_parts).strip()
            if context:
                return context
        except Exception as e:
            logger.error(f"Error getting context: {e}")

        fallback_context = self._fetch_s3_chunk_context(file_paths)
        if fallback_context:
            logger.info(
                "Using direct S3 chunk fallback context for quiz generation (%s files)",
                len(file_paths),
            )
        return fallback_context

    def generate_quiz(
        self, user_id: str, selected_folders: List[str], num_questions: int
    ) -> Dict[str, object]:
        if not selected_folders:
            raise ValueError("At least one folder must be selected")

        structure = self._get_folder_structure()
        files = []
        for folder in selected_folders:
            files.extend(structure.get(folder, []))

        if not files:
            raise ValueError("Selected folders do not contain indexed files")

        questions: List[Dict[str, object]] = []
        generated_questions = set()
        attempts = 0
        max_attempts = num_questions * 5

        # Generate quiz questions
        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1

            # Rotate through diverse query variants for varied context
            query = _QUERY_VARIANTS[(attempts - 1) % len(_QUERY_VARIANTS)]
            logger.info(f"Quiz generation attempt {attempts} using query: {query[:60]}...")
            context_str = self._get_context_for_query(query, files)

            if not context_str:
                logger.warning(
                    f"Quiz generation attempt {attempts}: no context retrieved"
                )
                continue

            try:
                prompt = QUESTION_TEMPLATE.format(context_str=context_str[:4000])
                llm_response = self.llm.complete(prompt, temperature=0.5)
                response_text = self._extract_completion_text(llm_response)

                # Extract JSON from response
                cleaned_response = response_text.replace("```json", "```").strip()
                match = re.search(r"\{[\s\S]*\}", cleaned_response)
                if not match:
                    logger.warning(f"Quiz generation attempt {attempts}: no JSON found")
                    continue

                payload = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                logger.warning(
                    f"Quiz generation attempt {attempts}: invalid JSON - {exc}"
                )
                continue

            if not self._is_valid_question(payload):
                continue

            question_text = payload["question"].strip()
            if question_text in generated_questions:
                continue

            # Use LLM-generated explanation, fall back to context snippet
            explanation = payload.get("explanation") or (
                context_str[:500] + "..." if len(context_str) > 500 else context_str
            )

            question_id = uuid.uuid4().hex
            questions.append(
                {
                    "id": question_id,
                    "question": question_text,
                    "options": payload["options"],
                    "correct_answer_letter": payload["correct_answer_letter"],
                    "explanation": explanation,
                }
            )
            generated_questions.add(question_text)
            logger.info(f"Generated question {len(questions)}/{num_questions}")

        if not questions:
            raise QuizGenerationError(
                "Unable to generate quiz questions from the selected folders"
            )

        quiz_id = uuid.uuid4().hex

        # Store full questions in Redis (shared across all workers, auto-expires)
        self._redis.set(
            f"{self._QUIZ_KEY_PREFIX}{quiz_id}",
            {"questions": questions, "selected_folders": selected_folders},
            ttl=_QUIZ_STORE_TTL_SECONDS,
        )

        # Strip correct answers and explanations from the response sent to frontend
        safe_questions = []
        for q in questions:
            safe_questions.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "options": q["options"],
                }
            )

        return {
            "quiz_id": quiz_id,
            "generated_at": datetime.utcnow().isoformat(),
            "questions": safe_questions,
            "selected_folders": selected_folders,
        }

    def _is_valid_question(self, payload: Dict[str, object]) -> bool:
        if not isinstance(payload, dict):
            return False
        options = payload.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return False
        normalized_options = []
        for index, opt in enumerate(options):
            if not isinstance(opt, str) or not opt.strip():
                return False
            text = opt.strip()
            text = re.sub(rf"^[{chr(ord('A') + index)}][\.)\-\]:]\s*", "", text, flags=re.IGNORECASE)
            normalized_options.append(text)
        payload["options"] = normalized_options

        correct_letter = self._normalize_correct_answer_letter(payload)
        if correct_letter not in {"A", "B", "C", "D"}:
            return False
        payload["correct_answer_letter"] = correct_letter
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            return False
        payload["question"] = question.strip()
        return True

    def save_result(
        self,
        user_id: str,
        quiz_id: str,
        answers: Dict[str, str],
    ) -> QuizResult:
        # Look up correct answers from Redis (shared across all workers)
        redis_key = f"{self._QUIZ_KEY_PREFIX}{quiz_id}"
        quiz_data = self._redis.get(redis_key)
        if quiz_data is None:
            raise ValueError(
                "Quiz not found or already submitted. Please generate a new quiz."
            )
        # One-time use: delete after retrieval so quiz can't be re-submitted
        self._redis.delete(redis_key)

        questions = quiz_data["questions"]
        selected_folders = quiz_data["selected_folders"]

        score = 0
        total_questions = len(questions)
        detailed_results = []

        for question in questions:
            qid = question["id"]
            correct = question["correct_answer_letter"]
            user_answer = answers.get(qid)
            is_correct = user_answer == correct
            if is_correct:
                score += 1
            detailed_results.append(
                {
                    "question_id": qid,
                    "question": question["question"],
                    "correct_answer": correct,
                    "user_answer": user_answer,
                    "is_correct": is_correct,
                    "explanation": question.get("explanation", ""),
                }
            )

        percentage = (score / total_questions * 100) if total_questions else 0.0
        result = QuizResult(
            id=quiz_id,
            user_id=user_id,
            score=score,
            total_questions=total_questions,
            percentage=percentage,
            metadata={
                "selected_folders": selected_folders,
                "responses": detailed_results,
            },
        )
        self.storage.save_quiz_result(result)
        return result

    def list_results(self, user_id: str) -> List[Dict[str, object]]:
        results = self.storage.list_quiz_results(user_id)
        return [r.to_dict() for r in results]


_quiz_service: Optional[QuizService] = None


def get_quiz_service() -> QuizService:
    global _quiz_service
    if _quiz_service is None:
        _quiz_service = QuizService()
    return _quiz_service
