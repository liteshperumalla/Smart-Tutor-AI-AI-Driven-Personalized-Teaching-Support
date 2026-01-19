from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config import config
from backend.services import get_storage_backend
from backend.services.models import QuizResult
from backend.s3_retriever import S3Retriever
from backend.bedrock_llm import BedrockLLM
from backend.bedrock_embeddings import BedrockEmbeddings

logger = logging.getLogger(__name__)

QUESTION_TEMPLATE = """Based on the following context, generate a unique multiple-choice question with four options (A, B, C, D).

Context:
{context_str}

Generate a question that tests understanding of key concepts from this material. Return ONLY a JSON object in this format:
{{
  "question": "Your question here?",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_answer_letter": "A"
}}

Do not include any other text or formatting. The correct answer should be clearly indicated."""


class QuizGenerationError(RuntimeError):
    """Raised when the quiz generator cannot produce valid questions."""


class QuizService:
    def __init__(self) -> None:
        self.storage = get_storage_backend()
        self.s3_retriever = S3Retriever(similarity_top_k=5)
        self.llm = BedrockLLM()
        self._folder_cache: Optional[Dict[str, List[str]]] = None

    def _get_folder_structure(self) -> Dict[str, List[str]]:
        if self._folder_cache is not None:
            return self._folder_cache

        import boto3

        s3 = boto3.client("s3", region_name="us-east-1")
        structure: Dict[str, List[str]] = {}

        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket="smart-ai-tutor-docs", Prefix="modules/"):
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

    def _get_context_for_query(self, query: str, file_paths: List[str]) -> str:
        """Get context from S3 for a specific query and files"""
        try:
            nodes = self.s3_retriever.retrieve(query)
            context_parts = []
            for node in nodes[:3]:
                text = node.node.text if hasattr(node.node, "text") else str(node.node)
                context_parts.append(text)
            return "\n\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return ""

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

            # Create a query for quiz generation
            query = "Generate a multiple-choice question about key concepts"
            context_str = self._get_context_for_query(query, files)

            if not context_str:
                logger.warning(
                    f"Quiz generation attempt {attempts}: no context retrieved"
                )
                continue

            try:
                prompt = QUESTION_TEMPLATE.format(context_str=context_str[:3000])
                llm_response = self.llm.complete(prompt)
                response_text = str(llm_response).strip()

                # Extract JSON from response
                match = re.search(r"\{[\s\S]*\}", response_text)
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

            # Get explanation using the context
            explanation = (
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
