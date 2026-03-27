"""
Quiz Tests
Tests for quiz generation, folder listing, and result retrieval.
"""

import pytest
from backend.services.models import QuizResult

from backend.services.quiz_service import QuizService


class TestQuizEndpoints:
    """Test quiz API endpoints"""

    def test_quiz_generate_requires_auth(self, test_client):
        """Quiz generate endpoint without auth must return 401"""
        response = test_client.post("/quiz/generate", json={
            "folders": ["Module 1"],
            "num_questions": 5
        })
        assert response.status_code == 401

    def test_generate_quiz_with_auth(self, test_client, auth_headers):
        """Authenticated user can request quiz generation"""
        response = test_client.post("/quiz/generate", headers=auth_headers, json={
            "folders": ["Module 1"],
            "num_questions": 3
        })
        # Accept 200 (generated), 400/422 (folders not found / validation),
        # or 500 (AWS credentials unavailable in CI)
        assert response.status_code in (200, 400, 422, 500)

    def test_quiz_history_requires_auth(self, test_client):
        """Quiz history without auth must return 401"""
        response = test_client.get("/quiz/history")
        assert response.status_code == 401

    def test_quiz_history_with_auth(self, test_client, auth_headers):
        """Authenticated user can retrieve their quiz history"""
        response = test_client.get("/quiz/history", headers=auth_headers)
        assert response.status_code in (200, 404)

    def test_quiz_folders_requires_auth(self, test_client):
        """Folder listing without auth must return 401"""
        response = test_client.get("/quiz/folders")
        assert response.status_code == 401

    def test_quiz_folders_with_auth(self, test_client, auth_headers):
        """Authenticated user can list available quiz folders"""
        response = test_client.get("/quiz/folders", headers=auth_headers)
        # Returns list of folders (may be empty if no content uploaded),
        # or 500 when AWS credentials are unavailable in CI
        assert response.status_code in (200, 404, 500)


class TestQuizServiceParsing:
    def test_extract_completion_text_prefers_text_attribute(self):
        service = object.__new__(QuizService)

        class FakeResponse:
            text = '{"question":"What is RAG?","options":["A","B","C","D"],"correct_answer_letter":"A"}'

            def __str__(self):
                return "FakeResponse(text omitted)"

        assert service._extract_completion_text(FakeResponse()).startswith('{"question"')

    def test_is_valid_question_normalizes_answer_and_options(self):
        service = object.__new__(QuizService)
        payload = {
            "question": "  What is retrieval-augmented generation?  ",
            "options": [
                "A. It combines search with generation",
                "B. It only summarizes documents",
                "C. It removes retrieval entirely",
                "D. It fine-tunes the model every request",
            ],
            "correct_answer_letter": "Option A. It combines search with generation",
        }

        assert service._is_valid_question(payload) is True
        assert payload["question"] == "What is retrieval-augmented generation?"
        assert payload["options"][0] == "It combines search with generation"
        assert payload["correct_answer_letter"] == "A"

    def test_get_context_uses_s3_chunk_fallback_when_retrieval_fails(self):
        service = object.__new__(QuizService)

        class BrokenRetriever:
            def retrieve(self, _query):
                raise RuntimeError("index unavailable")

        service.s3_retriever = BrokenRetriever()
        service._fetch_s3_chunk_context = lambda file_paths: "Chunk text fallback"

        context = service._get_context_for_query(
            "Explain embeddings", ["modules/Module 6/embeddings.pdf"]
        )

        assert context == "Chunk text fallback"

    def test_get_context_uses_s3_chunk_fallback_for_placeholder_only_results(self):
        service = object.__new__(QuizService)

        class FakeNode:
            def __init__(self, text, source_file):
                self.node = type(
                    "Node",
                    (),
                    {
                        "text": text,
                        "metadata": {"source_file": source_file},
                    },
                )()

        class PlaceholderRetriever:
            def retrieve(self, _query):
                return [
                    FakeNode(
                        "[Content from Module 5/data_cleaning.pdf]",
                        "Module 5/data_cleaning.pdf",
                    )
                ]

        service.s3_retriever = PlaceholderRetriever()
        service._fetch_s3_chunk_context = lambda file_paths: "Actual chunk text"

        context = service._get_context_for_query(
            "Explain data cleaning",
            ["modules/Module 5/data_cleaning.pdf"],
        )

        assert context == "Actual chunk text"

    def test_get_context_uses_source_document_fallback_when_chunks_missing(self):
        service = object.__new__(QuizService)

        class EmptyRetriever:
            def retrieve(self, _query):
                return []

        service.s3_retriever = EmptyRetriever()
        service._fetch_s3_chunk_context = lambda file_paths: ""
        service._fetch_source_file_context = lambda file_paths: "Extracted source file text"

        context = service._get_context_for_query(
            "Explain data cleaning",
            ["modules/Module 5/data_cleaning.pdf"],
        )

        assert context == "Extracted source file text"

    def test_extract_quiz_payload_accepts_single_quoted_python_dict(self):
        payload = QuizService._extract_quiz_payload(
            """```python
{'question': 'What is RAG?', 'options': ['A', 'B', 'C', 'D'], 'correct_answer_letter': 'A'}
```"""
        )

        assert isinstance(payload, dict)
        assert payload["question"] == "What is RAG?"

    def test_is_similar_question_rejects_rephrased_duplicates(self):
        existing_questions = [
            {
                "question": "What is the primary reason for normalizing text in the Tweet Text column?",
                "options": [
                    "To remove duplicate tweets",
                    "To handle missing values",
                    "To ensure consistency in text representation",
                    "To remove special characters and links",
                ],
                "correct_answer_letter": "C",
            }
        ]
        payload = {
            "question": "What is the primary purpose of normalizing the Tweet Text column during data cleaning?",
            "options": [
                "To remove special characters and links",
                "To handle missing values",
                "To ensure consistency and improve readability",
                "To remove duplicates",
            ],
            "correct_answer_letter": "C",
        }

        assert QuizService._is_similar_question(payload, existing_questions) is True

    def test_shuffle_question_options_updates_correct_answer_letter(self):
        service = object.__new__(QuizService)

        class FakeRandom:
            @staticmethod
            def shuffle(items):
                items[:] = [items[2], items[0], items[3], items[1]]

        service._random = FakeRandom()
        payload = {
            "question": "What is RAG?",
            "options": ["Search", "Summarization", "Retrieval and generation", "Translation"],
            "correct_answer_letter": "C",
        }

        service._shuffle_question_options(payload)

        assert payload["options"] == [
            "Retrieval and generation",
            "Search",
            "Translation",
            "Summarization",
        ]
        assert payload["correct_answer_letter"] == "A"

    def test_save_result_normalizes_lowercase_and_option_text_answers(self):
        service = object.__new__(QuizService)

        class FakeRedis:
            def __init__(self):
                self.data = {
                    "quiz:test-quiz": {
                        "questions": [
                            {
                                "id": "q1",
                                "question": "What is RAG?",
                                "options": [
                                    "It combines retrieval with generation",
                                    "It removes retrieval entirely",
                                    "It only summarizes documents",
                                    "It trains the model every request",
                                ],
                                "correct_answer_letter": "A",
                                "explanation": "RAG augments generation with retrieved context.",
                            },
                            {
                                "id": "q2",
                                "question": "What does preprocessing improve?",
                                "options": [
                                    "Only styling",
                                    "Data quality",
                                    "GPU temperature",
                                    "Database sharding",
                                ],
                                "correct_answer_letter": "B",
                                "explanation": "Preprocessing improves data quality before modeling.",
                            },
                        ],
                        "selected_folders": ["Module 5"],
                    }
                }

            def get(self, key):
                return self.data.get(key)

            def delete(self, key):
                self.data.pop(key, None)

        class FakeStorage:
            def __init__(self):
                self.saved = None

            def save_quiz_result(self, result: QuizResult) -> None:
                self.saved = result

        service._redis = FakeRedis()
        service.storage = FakeStorage()

        result = service.save_result(
            user_id="alice",
            quiz_id="test-quiz",
            answers={
                "q1": "a",
                "q2": "Data quality",
            },
        )

        assert result.score == 2
        assert result.total_questions == 2
        responses = result.metadata["responses"]
        assert responses[0]["user_answer"] == "A"
        assert responses[1]["user_answer"] == "B"
        assert responses[1]["user_answer_text"] == "Data quality"
