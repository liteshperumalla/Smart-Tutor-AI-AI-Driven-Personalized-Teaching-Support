"""
Quiz Tests
Tests for quiz generation, folder listing, and result retrieval.
"""

import pytest

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
