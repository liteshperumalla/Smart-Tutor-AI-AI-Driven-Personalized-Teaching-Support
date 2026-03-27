from __future__ import annotations

import json
import logging
import random
import re
import uuid
from ast import literal_eval
from dataclasses import asdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
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

_QUESTION_STOPWORDS = {
    "about",
    "after",
    "all",
    "and",
    "are",
    "during",
    "for",
    "from",
    "how",
    "into",
    "its",
    "main",
    "most",
    "primary",
    "purpose",
    "reason",
    "step",
    "that",
    "the",
    "their",
    "these",
    "this",
    "what",
    "when",
    "which",
    "why",
    "with",
}

QUESTION_TEMPLATE = """You are an expert quiz question writer. Based on the following context, generate ONE high-quality multiple-choice question with four options (A, B, C, D).

Topic:
{topic_label}

Question angle:
{question_angle}

Context:
{context_str}

Questions already used in this quiz:
{used_questions}

Requirements:
- The question should test UNDERSTANDING, not just memorization of facts.
- Ask about a concept that is different from the already used questions.
- Do not reuse the same "primary reason/purpose/goal" stem unless the underlying concept is genuinely different.
- All four options must be plausible — avoid obviously wrong distractors.
- Make the correct answer specific to this context, not a generic restatement that could fit multiple questions.
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
    _PLACEHOLDER_PREFIX = "[Content from "

    def __init__(self) -> None:
        self.storage = get_storage_backend()
        self.s3_retriever = S3Retriever(similarity_top_k=5)
        from backend.llm_provider import get_llm
        self.llm = get_llm()
        self._random = random.SystemRandom()
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

    @staticmethod
    def _normalize_similarity_text(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def _tokenize_similarity_text(cls, value: str) -> set[str]:
        normalized = cls._normalize_similarity_text(value)
        return {
            token
            for token in normalized.split()
            if len(token) > 2 and token not in _QUESTION_STOPWORDS
        }

    @staticmethod
    def _jaccard_similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @classmethod
    def _is_similar_question(
        cls,
        payload: Dict[str, object],
        existing_questions: List[Dict[str, object]],
    ) -> bool:
        new_question = str(payload.get("question", ""))
        new_question_normalized = cls._normalize_similarity_text(new_question)
        new_question_tokens = cls._tokenize_similarity_text(new_question)
        new_correct_letter = str(payload.get("correct_answer_letter", "A"))
        new_options = payload.get("options") or []
        new_correct_index = ord(new_correct_letter) - ord("A")
        new_correct_option = (
            str(new_options[new_correct_index])
            if isinstance(new_options, list) and 0 <= new_correct_index < len(new_options)
            else ""
        )
        new_correct_normalized = cls._normalize_similarity_text(new_correct_option)
        new_correct_tokens = cls._tokenize_similarity_text(new_correct_option)

        for existing in existing_questions:
            existing_question = str(existing.get("question", ""))
            existing_question_normalized = cls._normalize_similarity_text(existing_question)
            if new_question_normalized == existing_question_normalized:
                return True

            existing_question_tokens = cls._tokenize_similarity_text(existing_question)
            question_similarity = cls._jaccard_similarity(
                new_question_tokens, existing_question_tokens
            )
            question_sequence_similarity = SequenceMatcher(
                None, new_question_normalized, existing_question_normalized
            ).ratio()
            shared_question_tokens = new_question_tokens & existing_question_tokens

            existing_correct_letter = str(existing.get("correct_answer_letter", "A"))
            existing_options = existing.get("options") or []
            existing_correct_index = ord(existing_correct_letter) - ord("A")
            existing_correct_option = (
                str(existing_options[existing_correct_index])
                if isinstance(existing_options, list)
                and 0 <= existing_correct_index < len(existing_options)
                else ""
            )
            existing_correct_normalized = cls._normalize_similarity_text(
                existing_correct_option
            )
            answer_similarity = cls._jaccard_similarity(
                new_correct_tokens,
                cls._tokenize_similarity_text(existing_correct_option),
            )
            answer_sequence_similarity = SequenceMatcher(
                None, new_correct_normalized, existing_correct_normalized
            ).ratio()

            if question_similarity >= 0.72:
                return True
            if question_sequence_similarity >= 0.74:
                return True
            if len(shared_question_tokens) >= 4 and (
                answer_similarity >= 0.34 or answer_sequence_similarity >= 0.55
            ):
                return True
            if question_similarity >= 0.5 and answer_similarity >= 0.6:
                return True

        return False

    @staticmethod
    def _build_focus_label(file_path: str) -> str:
        stem = Path(_normalize_source_path(file_path)).stem.replace("_", " ").strip()
        return stem or "selected topic"

    @staticmethod
    def _context_sections_from_text(context_str: str) -> List[str]:
        sections = [
            re.sub(r"\s+", " ", part).strip()
            for part in re.split(r"\n\s*\n+", context_str or "")
            if part and part.strip()
        ]
        if len(sections) > 1:
            return sections

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", context_str or "")
            if sentence and sentence.strip()
        ]
        if len(sentences) >= 4:
            return [
                " ".join(sentences[index : index + 3]).strip()
                for index in range(0, len(sentences), 2)
                if " ".join(sentences[index : index + 3]).strip()
            ]

        cleaned = re.sub(r"\s+", " ", context_str or "").strip()
        return [cleaned] if cleaned else []

    @classmethod
    def _select_context_excerpt(cls, context_str: str, attempt_index: int) -> str:
        sections = cls._context_sections_from_text(context_str)
        if not sections:
            return ""
        if len(sections) == 1:
            return sections[0][:4000]

        window_size = min(3, len(sections))
        max_start = max(len(sections) - window_size, 0)
        start = ((attempt_index - 1) * window_size) % (max_start + 1)
        excerpt = "\n\n".join(sections[start : start + window_size]).strip()
        return excerpt[:4000]

    @staticmethod
    def _format_used_questions(existing_questions: List[Dict[str, object]]) -> str:
        if not existing_questions:
            return "None yet."
        recent_questions = [
            f"- {str(question.get('question', '')).strip()}"
            for question in existing_questions[-3:]
            if str(question.get("question", "")).strip()
        ]
        return "\n".join(recent_questions) if recent_questions else "None yet."

    def _shuffle_question_options(self, payload: Dict[str, object]) -> None:
        options = payload.get("options")
        correct_letter = str(payload.get("correct_answer_letter", "A"))
        if not isinstance(options, list) or len(options) != 4:
            return

        correct_index = ord(correct_letter) - ord("A")
        if not 0 <= correct_index < len(options):
            return

        indexed_options = list(enumerate(options))
        self._random.shuffle(indexed_options)
        payload["options"] = [text for _, text in indexed_options]
        for new_index, (original_index, _text) in enumerate(indexed_options):
            if original_index == correct_index:
                payload["correct_answer_letter"] = chr(ord("A") + new_index)
                break

    @classmethod
    def _normalize_submitted_answer(
        cls, raw_answer: Optional[str], options: List[str]
    ) -> Optional[str]:
        if not isinstance(raw_answer, str):
            return None
        candidate = raw_answer.strip()
        if not candidate:
            return None

        payload: Dict[str, object] = {
            "options": list(options or []),
            "correct_answer_letter": candidate,
        }
        normalized_letter = cls._normalize_correct_answer_letter(payload)
        if normalized_letter in {"A", "B", "C", "D"}:
            return normalized_letter

        normalized_candidate = cls._normalize_similarity_text(candidate)
        for index, option in enumerate(options or []):
            if cls._normalize_similarity_text(str(option)) == normalized_candidate:
                return chr(ord("A") + index)

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

    def _fetch_source_file_context(
        self,
        file_paths: List[str],
        max_files: int = 3,
        chars_per_file: int = 2000,
    ) -> str:
        if not file_paths:
            return ""

        try:
            from pathlib import Path

            from backend.cloud.aws_helpers import get_boto3_client
            from backend.services.indexing_service import IndexingService

            s3 = get_boto3_client("s3")
            extractor = IndexingService(redis_cache=None)
            context_parts: List[str] = []
            files_read = 0

            for file_path in file_paths:
                if files_read >= max_files:
                    break

                key = (file_path or "").strip().lstrip("/")
                if not key:
                    continue

                try:
                    response = s3.get_object(Bucket=config.S3_DOCUMENTS_BUCKET, Key=key)
                    file_bytes = response["Body"].read()
                except Exception as exc:
                    logger.warning(
                        "Failed to read quiz source document %s: %s", key, exc
                    )
                    continue

                try:
                    pages = extractor._extract_text(
                        file_bytes,
                        Path(key).name,
                        Path(key).suffix.lower(),
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to extract quiz source document %s: %s", key, exc
                    )
                    continue

                extracted_text = "\n\n".join(
                    text.strip()
                    for text, _metadata in pages
                    if isinstance(text, str) and text.strip()
                ).strip()
                if not extracted_text:
                    continue

                context_parts.append(extracted_text[:chars_per_file])
                files_read += 1

            return "\n\n".join(context_parts)
        except Exception as exc:
            logger.warning("Failed to load quiz source-file context: %s", exc)
            return ""

    @classmethod
    def _has_real_context(cls, context_parts: List[str]) -> bool:
        meaningful_parts = [part.strip() for part in context_parts if part and part.strip()]
        if not meaningful_parts:
            return False
        return any(not part.startswith(cls._PLACEHOLDER_PREFIX) for part in meaningful_parts)

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
            if context and self._has_real_context(context_parts):
                return context
            if context:
                logger.info("Quiz retrieval returned placeholder-only context; using S3 chunk fallback")
        except Exception as e:
            logger.error(f"Error getting context: {e}")

        fallback_context = self._fetch_s3_chunk_context(file_paths)
        if fallback_context:
            logger.info(
                "Using direct S3 chunk fallback context for quiz generation (%s files)",
                len(file_paths),
            )
            return fallback_context

        source_context = self._fetch_source_file_context(file_paths)
        if source_context:
            logger.info(
                "Using direct source-document fallback context for quiz generation (%s files)",
                len(file_paths),
            )
        return source_context

    @staticmethod
    def _extract_quiz_payload(response_text: str) -> Optional[Dict[str, object]]:
        cleaned_response = (response_text or "").replace("```json", "```").strip()

        match = re.search(r"\{[\s\S]*\}", cleaned_response)
        candidate = match.group(0) if match else cleaned_response
        candidate = candidate.strip()
        if not candidate:
            return None

        decoders = (json.loads, literal_eval)
        for decoder in decoders:
            try:
                payload = decoder(candidate)
            except Exception:
                continue
            if isinstance(payload, list) and payload:
                payload = payload[0]
            if isinstance(payload, dict):
                return payload
        return None

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
        attempts = 0
        max_attempts = max(num_questions * 8, len(files) * 3)
        file_rotation = list(files)
        self._random.shuffle(file_rotation)

        # Generate quiz questions
        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1

            # Rotate through diverse query variants for varied context
            target_file = file_rotation[(attempts - 1) % len(file_rotation)]
            topic_label = _resolve_topic_label(selected_folders[(attempts - 1) % len(selected_folders)])
            file_focus = self._build_focus_label(target_file)
            query_angle = _QUERY_VARIANTS[(attempts - 1) % len(_QUERY_VARIANTS)]
            query = f"{topic_label} - {file_focus}: {query_angle}"
            logger.info(
                "Quiz generation attempt %s using file %s and query angle %s",
                attempts,
                target_file,
                query_angle,
            )
            context_str = self._get_context_for_query(query, [target_file])

            if not context_str:
                logger.warning(
                    f"Quiz generation attempt {attempts}: no context retrieved"
                )
                continue

            try:
                prompt = QUESTION_TEMPLATE.format(
                    topic_label=f"{topic_label} ({file_focus})",
                    question_angle=query_angle,
                    context_str=self._select_context_excerpt(context_str, attempts),
                    used_questions=self._format_used_questions(questions),
                )
                llm_response = self.llm.complete(prompt, temperature=0.5)
                response_text = self._extract_completion_text(llm_response)
                payload = self._extract_quiz_payload(response_text)
                if payload is None:
                    logger.warning(
                        "Quiz generation attempt %s: no valid question payload found",
                        attempts,
                    )
                    continue
            except (json.JSONDecodeError, SyntaxError, ValueError) as exc:
                logger.warning(
                    f"Quiz generation attempt {attempts}: invalid payload - {exc}"
                )
                continue

            if not self._is_valid_question(payload):
                continue
            self._shuffle_question_options(payload)

            question_text = payload["question"].strip()
            if self._is_similar_question(payload, questions):
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
            user_answer = self._normalize_submitted_answer(
                answers.get(qid), question.get("options", [])
            )
            is_correct = user_answer == correct
            if is_correct:
                score += 1
            correct_index = ord(correct) - ord("A")
            user_index = ord(user_answer) - ord("A") if user_answer else None
            detailed_results.append(
                {
                    "question_id": qid,
                    "question": question["question"],
                    "correct_answer": correct,
                    "correct_answer_text": question["options"][correct_index]
                    if 0 <= correct_index < len(question["options"])
                    else None,
                    "user_answer": user_answer,
                    "user_answer_text": question["options"][user_index]
                    if user_index is not None and 0 <= user_index < len(question["options"])
                    else None,
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
