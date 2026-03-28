import json

from backend.services import rag_quality_evaluator as evaluator


def test_evaluate_quality_uses_explicit_correctness_from_judge(monkeypatch):
    class FakeLLM:
        def __init__(self, model_id=None):
            self.model_id = model_id

        def generate(self, prompt, max_tokens=300, temperature=0.0):
            assert "Reference Answer:" in prompt
            assert "Machine learning is a subset of AI." in prompt
            return json.dumps(
                {
                    "faithfulness": 0.6,
                    "answer_relevance": 0.8,
                    "context_recall": 0.7,
                    "correctness": 0.9,
                    "reasoning": "Reference answer alignment is strong.",
                }
            )

    monkeypatch.setattr(evaluator, "BedrockLLM", FakeLLM)

    scores = evaluator.evaluate_quality(
        question="What is machine learning?",
        context_passages=["Machine learning is a subset of AI."],
        answer="It is a subset of AI that learns from data.",
        reference_answer="Machine learning is a subset of AI.",
    )

    assert scores["faithfulness"] == 0.6
    assert scores["answer_relevance"] == 0.8
    assert scores["context_recall"] == 0.7
    assert scores["correctness"] == 0.9


def test_evaluate_quality_falls_back_when_judge_omits_correctness(monkeypatch):
    class FakeLLM:
        def __init__(self, model_id=None):
            self.model_id = model_id

        def generate(self, prompt, max_tokens=300, temperature=0.0):
            return json.dumps(
                {
                    "faithfulness": 1.0,
                    "answer_relevance": 0.5,
                    "context_recall": 0.25,
                    "reasoning": "Fallback case.",
                }
            )

    monkeypatch.setattr(evaluator, "BedrockLLM", FakeLLM)

    scores = evaluator.evaluate_quality(
        question="What is chunking?",
        context_passages=["Chunking splits documents."],
        answer="Chunking splits documents into smaller pieces.",
    )

    assert scores["correctness"] == round((1.0 * 0.5 * 0.25) ** (1 / 3), 4)
