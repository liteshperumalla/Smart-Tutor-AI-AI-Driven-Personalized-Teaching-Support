from backend.retrieval_tuning import (
    build_rag_recommendations,
    determine_retrieval_limit,
    select_diverse_items,
)


def test_determine_retrieval_limit_increases_for_complex_queries():
    simple = determine_retrieval_limit("Define overfitting.", base_top_k=3, max_top_k=6)
    complex_query = determine_retrieval_limit(
        "Compare precision and recall, explain the tradeoff, and describe when to use each metric.",
        base_top_k=3,
        max_top_k=6,
    )

    assert complex_query > simple
    assert complex_query <= 6


def test_select_diverse_items_prefers_source_diversity_before_duplicates():
    items = [
        {"text_excerpt": "precision measures correct positives", "metadata": {"source_file": "a.pdf"}, "score": 0.92},
        {"text_excerpt": "precision measures correct positives", "metadata": {"source_file": "a.pdf"}, "score": 0.91},
        {"text_excerpt": "recall measures found positives", "metadata": {"source_file": "b.pdf"}, "score": 0.88},
        {"text_excerpt": "f1 balances precision and recall", "metadata": {"source_file": "c.pdf"}, "score": 0.87},
    ]

    selected = select_diverse_items(
        items,
        query="Explain precision recall and f1",
        limit=3,
        max_per_source=2,
    )

    sources = [item["metadata"]["source_file"] for item in selected]
    assert len(selected) == 3
    assert len(set(sources)) == 3


def test_build_rag_recommendations_returns_targeted_actions():
    recommendations = build_rag_recommendations(
        avg_context_recall=0.42,
        avg_context_precision=0.48,
        avg_correctness=0.5,
        avg_topic_coverage=0.61,
        p95_response_time=24.0,
    )

    assert len(recommendations) >= 4
