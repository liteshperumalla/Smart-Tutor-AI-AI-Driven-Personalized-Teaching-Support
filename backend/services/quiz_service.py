from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional

from llama_index.core import get_response_synthesizer, load_index_from_storage
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

from Tutor_chat import RAGQueryEngine
from utils import get_storage_context

from backend.services import get_storage_backend
from backend.services.models import QuizResult


logger = logging.getLogger(__name__)


class QuizGenerationError(RuntimeError):
    """Raised when the quiz generator cannot produce valid questions."""


class QuizService:
    def __init__(self) -> None:
        self.storage = get_storage_backend()
        self._folder_cache: Optional[Dict[str, List[str]]] = None
        storage_context = get_storage_context()
        if storage_context is None:
            raise RuntimeError("Knowledge base is not initialized")
        self.index = load_index_from_storage(storage_context)

    def _get_folder_structure(self) -> Dict[str, List[str]]:
        if self._folder_cache is not None:
            return self._folder_cache

        structure: Dict[str, List[str]] = {}
        docstore = self.index.docstore
        for doc in docstore.docs.values():
            file_path = doc.metadata.get("file_path")
            if not file_path:
                continue
            folder = str(file_path.rsplit("/", 1)[0])
            structure.setdefault(folder, []).append(file_path)
        self._folder_cache = structure
        return structure

    def list_folders(self) -> List[Dict[str, str]]:
        structure = self._get_folder_structure()
        buckets: Dict[str, Dict[str, str]] = {}
        for folder, files in structure.items():
            label = folder.split("/")[-1] or folder
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
        folders.sort(key=lambda item: item["label"].lower())
        return folders

    def _build_query_engine(self, file_paths: List[str]) -> RAGQueryEngine:
        filters = MetadataFilters(
            filters=[ExactMatchFilter(key="file_path", value=path) for path in file_paths],
            condition="or",
        )
        retriever = self.index.as_retriever(filters=filters, similarity_top_k=3)
        synthesizer = get_response_synthesizer(response_mode="compact")
        return RAGQueryEngine(retriever=retriever, response_synthesizer=synthesizer, mode="quiz")

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

        query_engine = self._build_query_engine(files)
        questions: List[Dict[str, object]] = []
        generated_questions = set()
        attempts = 0
        max_attempts = num_questions * 5

        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1
            llm_response_str = query_engine.custom_query(
                "Generate a unique, high-quality multiple-choice question with four options based on the provided context."
            )
            match = re.search(r"\{[\s\S]*\}", llm_response_str)
            if not match:
                logger.warning("Quiz generation attempt %s returned no JSON", attempts)
                continue

            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                logger.warning("Invalid JSON in quiz generation: %s", exc)
                continue

            if not self._is_valid_question(payload):
                continue

            question_text = payload["question"].strip()
            if question_text in generated_questions:
                continue

            explanation = query_engine.get_related_module(question_text)
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

        if not questions:
            raise QuizGenerationError("Unable to generate quiz questions from the selected folders")

        quiz_id = uuid.uuid4().hex
        return {
            "quiz_id": quiz_id,
            "generated_at": datetime.utcnow().isoformat(),
            "questions": questions,
            "selected_folders": selected_folders,
        }

    def _is_valid_question(self, payload: Dict[str, object]) -> bool:
        if not isinstance(payload, dict):
            return False
        if payload.get("correct_answer_letter") not in {"A", "B", "C", "D"}:
            return False
        options = payload.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return False
        if not all(isinstance(opt, str) and opt.strip() for opt in options):
            return False
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            return False
        return True

    def save_result(
        self,
        user_id: str,
        quiz_id: str,
        selected_folders: List[str],
        questions: List[Dict[str, object]],
        answers: Dict[str, str],
    ) -> QuizResult:
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
