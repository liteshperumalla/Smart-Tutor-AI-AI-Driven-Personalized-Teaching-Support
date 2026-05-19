"""
Advanced Reranking Module

Implements multiple reranking strategies to improve retrieval quality:
1. Cross-Encoder Reranking - Deep learning model for query-document relevance
2. LLM-based Reranking - Use LLM to score relevance
3. MMR (Maximal Marginal Relevance) - Diversity-based reranking
4. Score Fusion - Combine multiple signals

Author: Smart AI Tutor Team
Date: December 28, 2025
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RankedResult:
    """Represents a reranked search result"""
    chunk_id: str
    text: str
    score: float
    original_rank: int
    reranked_rank: int
    metadata: Dict[str, Any]
    reranking_method: str
    original_score: Optional[float] = None
    cross_encoder_score: Optional[float] = None
    llm_score: Optional[float] = None
    diversity_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'score': self.score,
            'original_rank': self.original_rank,
            'reranked_rank': self.reranked_rank,
            'metadata': self.metadata,
            'reranking_method': self.reranking_method,
            'scores': {
                'original': self.original_score,
                'cross_encoder': self.cross_encoder_score,
                'llm': self.llm_score,
                'diversity': self.diversity_score
            }
        }


class CrossEncoderReranker:
    """
    Cross-Encoder based reranking

    Uses a transformer model trained to score query-document pairs.
    More accurate than bi-encoder (embedding similarity) but slower.

    Recommended models:
    - ms-marco-MiniLM-L-12-v2 (fast, good quality)
    - ms-marco-electra-base (better quality, slower)
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        device: str = "cpu",
        max_length: int = 512
    ):
        """
        Initialize cross-encoder reranker

        Args:
            model_name: HuggingFace model name
            device: Device to run on ('cpu', 'cuda', 'mps')
            max_length: Maximum sequence length
        """
        if not CROSS_ENCODER_AVAILABLE:
            logger.error("sentence-transformers not installed. Cross-encoder reranking unavailable.")
            self.model = None
            return

        try:
            self.model = CrossEncoder(model_name, max_length=max_length, device=device)
            logger.info(f"CrossEncoderReranker initialized: {model_name} on {device}")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            self.model = None

        self.model_name = model_name
        self.device = device

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[RankedResult]:
        """
        Rerank results using cross-encoder

        Args:
            query: Search query
            results: List of search results (dicts with 'text', 'chunk_id', 'score', etc.)
            top_k: Number of results to return (None = return all)

        Returns:
            List of RankedResult objects, sorted by cross-encoder score
        """
        if not self.model:
            logger.warning("Cross-encoder model not available. Returning original ranking.")
            return self._convert_to_ranked_results(results, "none")

        if not results:
            return []

        # Prepare query-document pairs
        pairs = [[query, r.get('text', '')] for r in results]

        # Score with cross-encoder
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.error(f"Cross-encoder prediction failed: {e}")
            return self._convert_to_ranked_results(results, "none")

        # Combine scores with results
        scored_results = []
        for idx, (result, ce_score) in enumerate(zip(results, scores)):
            ranked = RankedResult(
                chunk_id=result.get('chunk_id', f'chunk_{idx}'),
                text=result.get('text', ''),
                score=float(ce_score),
                original_rank=idx + 1,
                reranked_rank=0,  # Will be set after sorting
                metadata=result.get('metadata', {}),
                reranking_method='cross_encoder',
                original_score=result.get('score'),
                cross_encoder_score=float(ce_score)
            )
            scored_results.append(ranked)

        # Sort by cross-encoder score
        scored_results.sort(key=lambda x: x.score, reverse=True)

        # Update reranked ranks
        for rank, result in enumerate(scored_results, 1):
            result.reranked_rank = rank

        # Return top-k
        if top_k:
            scored_results = scored_results[:top_k]

        logger.info(f"Cross-encoder reranked {len(results)} results")
        return scored_results

    def _convert_to_ranked_results(
        self,
        results: List[Dict[str, Any]],
        method: str
    ) -> List[RankedResult]:
        """Convert regular results to RankedResult format"""
        ranked = []
        for idx, result in enumerate(results):
            ranked_result = RankedResult(
                chunk_id=result.get('chunk_id', f'chunk_{idx}'),
                text=result.get('text', ''),
                score=result.get('score', 0.0),
                original_rank=idx + 1,
                reranked_rank=idx + 1,
                metadata=result.get('metadata', {}),
                reranking_method=method,
                original_score=result.get('score')
            )
            ranked.append(ranked_result)
        return ranked


class LLMReranker:
    """
    LLM-based reranking

    Uses an LLM to score query-document relevance.
    More expensive but can handle nuanced relevance judgments.
    """

    def __init__(
        self,
        llm_provider: Any = None,
        score_threshold: float = 0.5
    ):
        """
        Initialize LLM reranker

        Args:
            llm_provider: LLM instance (BedrockLLM or similar)
            score_threshold: Minimum relevance score
        """
        self.llm = llm_provider
        self.score_threshold = score_threshold

        if self.llm:
            logger.info("LLMReranker initialized")
        else:
            logger.warning("No LLM provided. LLM reranking unavailable.")

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[RankedResult]:
        """
        Rerank using LLM to score relevance

        Args:
            query: Search query
            results: List of search results
            top_k: Number of results to return

        Returns:
            List of RankedResult objects
        """
        if not self.llm:
            logger.warning("LLM not available. Skipping LLM reranking.")
            return self._convert_to_ranked_results(results, "none")

        if not results:
            return []

        # Score each result with LLM
        scored_results = []

        for idx, result in enumerate(results):
            # Construct prompt
            prompt = self._create_relevance_prompt(query, result.get('text', ''))

            # Get LLM judgment
            try:
                response = self.llm.generate(prompt, max_tokens=50, temperature=0.0)
                score = self._parse_relevance_score(response)
            except Exception as e:
                logger.error(f"LLM scoring failed for result {idx}: {e}")
                score = 0.5  # Default to neutral

            ranked = RankedResult(
                chunk_id=result.get('chunk_id', f'chunk_{idx}'),
                text=result.get('text', ''),
                score=score,
                original_rank=idx + 1,
                reranked_rank=0,
                metadata=result.get('metadata', {}),
                reranking_method='llm',
                original_score=result.get('score'),
                llm_score=score
            )
            scored_results.append(ranked)

        # Sort by LLM score
        scored_results.sort(key=lambda x: x.score, reverse=True)

        # Update ranks
        for rank, result in enumerate(scored_results, 1):
            result.reranked_rank = rank

        # Filter by threshold and return top-k
        scored_results = [r for r in scored_results if r.score >= self.score_threshold]

        if top_k:
            scored_results = scored_results[:top_k]

        logger.info(f"LLM reranked {len(results)} results → {len(scored_results)} above threshold")
        return scored_results

    def _create_relevance_prompt(self, query: str, document: str) -> str:
        """Create prompt for LLM relevance judgment"""
        prompt = f"""Rate the relevance of the following document to the query on a scale of 0.0 to 1.0.
Only respond with a number between 0.0 and 1.0, where:
- 0.0 = Completely irrelevant
- 0.5 = Somewhat relevant
- 1.0 = Highly relevant

Query: {query}

Document: {document[:500]}...

Relevance Score:"""
        return prompt

    def _parse_relevance_score(self, response: str) -> float:
        """Parse relevance score from LLM response"""
        import re

        # Extract first number between 0.0 and 1.0
        match = re.search(r'0?\.\d+|[01]\.0', response)
        if match:
            try:
                score = float(match.group())
                return max(0.0, min(1.0, score))  # Clamp to [0, 1]
            except ValueError:
                pass

        # Default to 0.5 if parsing fails
        logger.warning(f"Failed to parse LLM score from: {response}")
        return 0.5

    def _convert_to_ranked_results(
        self,
        results: List[Dict[str, Any]],
        method: str
    ) -> List[RankedResult]:
        """Convert regular results to RankedResult format"""
        ranked = []
        for idx, result in enumerate(results):
            ranked_result = RankedResult(
                chunk_id=result.get('chunk_id', f'chunk_{idx}'),
                text=result.get('text', ''),
                score=result.get('score', 0.0),
                original_rank=idx + 1,
                reranked_rank=idx + 1,
                metadata=result.get('metadata', {}),
                reranking_method=method,
                original_score=result.get('score')
            )
            ranked.append(ranked_result)
        return ranked


class MMRReranker:
    """
    Maximal Marginal Relevance (MMR) Reranker

    Balances relevance and diversity to reduce redundancy.

    MMR(Di) = λ * Sim(Di, Q) - (1-λ) * max_j[Sim(Di, Dj)]
    where:
    - Sim(Di, Q) is relevance to query
    - Sim(Di, Dj) is similarity to already selected documents
    - λ balances relevance vs diversity (0.5 = balanced)
    """

    def __init__(
        self,
        lambda_param: float = 0.5,
        embeddings_model: Any = None
    ):
        """
        Initialize MMR reranker

        Args:
            lambda_param: Trade-off between relevance and diversity (0-1)
                         0 = max diversity, 1 = max relevance
            embeddings_model: Model to compute embeddings for similarity
        """
        self.lambda_param = lambda_param
        self.embeddings_model = embeddings_model

        logger.info(f"MMRReranker initialized (λ={lambda_param})")

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        embeddings: Optional[np.ndarray] = None,
        top_k: Optional[int] = None
    ) -> List[RankedResult]:
        """
        Rerank using MMR for diversity

        Args:
            query: Search query
            results: List of search results
            embeddings: Pre-computed embeddings for results (optional)
            top_k: Number of diverse results to select

        Returns:
            List of RankedResult objects (diverse set)
        """
        if not results:
            return []

        # If no embeddings provided, use original scores as proxy
        if embeddings is None:
            logger.warning("No embeddings provided. Using score-based MMR.")
            return self._score_based_mmr(query, results, top_k)

        # Full MMR with embeddings
        return self._embedding_based_mmr(query, results, embeddings, top_k)

    def _score_based_mmr(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int]
    ) -> List[RankedResult]:
        """MMR using only scores (simplified version)"""
        top_k = top_k or len(results)

        selected = []
        remaining = list(results)

        # Select first result (highest relevance)
        if remaining:
            best = max(remaining, key=lambda r: r.get('score', 0))
            selected.append(best)
            remaining.remove(best)

        # Select remaining results balancing relevance and diversity
        while len(selected) < top_k and remaining:
            best_score = -float('inf')
            best_result = None

            for candidate in remaining:
                # Relevance score
                relevance = candidate.get('score', 0)

                # Diversity score (penalize similarity to selected)
                # Use simple text overlap as proxy
                max_similarity = max(
                    self._text_overlap(candidate.get('text', ''), sel.get('text', ''))
                    for sel in selected
                ) if selected else 0

                # MMR score
                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * max_similarity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_result = candidate

            if best_result:
                selected.append(best_result)
                remaining.remove(best_result)

        # Convert to RankedResult
        ranked_results = []
        for rank, result in enumerate(selected, 1):
            ranked = RankedResult(
                chunk_id=result.get('chunk_id', f'chunk_{rank}'),
                text=result.get('text', ''),
                score=result.get('score', 0.0),
                original_rank=results.index(result) + 1,
                reranked_rank=rank,
                metadata=result.get('metadata', {}),
                reranking_method='mmr',
                original_score=result.get('score')
            )
            ranked_results.append(ranked)

        logger.info(f"MMR selected {len(ranked_results)} diverse results from {len(results)}")
        return ranked_results

    def _embedding_based_mmr(
        self,
        query: str,
        results: List[Dict[str, Any]],
        embeddings: np.ndarray,
        top_k: Optional[int]
    ) -> List[RankedResult]:
        """MMR using embeddings for accurate similarity"""
        top_k = top_k or len(results)

        if len(embeddings) != len(results):
            logger.error("Embeddings count mismatch with results. Falling back to score-based MMR.")
            return self._score_based_mmr(query, results, top_k)

        # Normalize embeddings
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        selected_indices = []
        remaining_indices = list(range(len(results)))

        # Select first (most relevant)
        best_idx = max(remaining_indices, key=lambda i: results[i].get('score', 0))
        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)

        # Select remaining with MMR
        while len(selected_indices) < top_k and remaining_indices:
            best_score = -float('inf')
            best_idx = None

            for candidate_idx in remaining_indices:
                # Relevance (original score)
                relevance = results[candidate_idx].get('score', 0)

                # Diversity (max cosine similarity to selected)
                if selected_indices:
                    similarities = np.dot(
                        embeddings[candidate_idx],
                        embeddings[selected_indices].T
                    )
                    max_similarity = np.max(similarities)
                else:
                    max_similarity = 0

                # MMR formula
                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * max_similarity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = candidate_idx

            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)

        # Convert to RankedResult
        ranked_results = []
        for rank, idx in enumerate(selected_indices, 1):
            result = results[idx]
            ranked = RankedResult(
                chunk_id=result.get('chunk_id', f'chunk_{idx}'),
                text=result.get('text', ''),
                score=result.get('score', 0.0),
                original_rank=idx + 1,
                reranked_rank=rank,
                metadata=result.get('metadata', {}),
                reranking_method='mmr_embedding',
                original_score=result.get('score'),
                diversity_score=1.0 / (rank + 1)  # Higher rank = more diverse
            )
            ranked_results.append(ranked)

        logger.info(f"Embedding-based MMR selected {len(ranked_results)} diverse results")
        return ranked_results

    def _text_overlap(self, text1: str, text2: str) -> float:
        """Compute simple text overlap as similarity proxy"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0


class AdvancedReranker:
    """
    Backward-compatible reranker facade used by RAGService.

    It accepts plain document strings or search-result dictionaries and returns
    dictionaries so downstream answer generation can consume a stable shape.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        use_mmr: bool = True,
        lambda_diversity: float = 0.7,
        device: str = "cpu",
        # Adaptive skip: when the top retrieval score is comfortably above this
        # bar AND the gap to the 2nd result is wide, we trust the initial
        # ranking and skip the (CPU-heavy) cross-encoder. Set to None to always
        # run the reranker.
        confidence_skip_threshold: Optional[float] = 0.75,
        confidence_skip_gap: float = 0.10,
        **_: Any,
    ):
        self.cross_encoder = CrossEncoderReranker(
            model_name=model_name,
            device=device,
        )
        self.mmr = MMRReranker(lambda_param=lambda_diversity)
        self.use_mmr = use_mmr
        self.confidence_skip_threshold = confidence_skip_threshold
        self.confidence_skip_gap = confidence_skip_gap

    def _should_skip_cross_encoder(self, documents: List[Dict[str, Any]]) -> bool:
        """Cross-encoders cost ~50–200ms on CPU for a top-k of 10. If the
        retrieval already returned an unambiguous winner, the rerank rarely
        changes the top-1 and the cost is wasted. Skip when top-1 is high
        AND the gap to top-2 is wide."""
        if self.confidence_skip_threshold is None or len(documents) < 2:
            return False
        scores = sorted(
            (float(d.get("score") or 0.0) for d in documents),
            reverse=True,
        )
        return (
            scores[0] >= self.confidence_skip_threshold
            and (scores[0] - scores[1]) >= self.confidence_skip_gap
        )

    def rerank(
        self,
        query: str,
        documents: List[Any],
        top_k: Optional[int] = None,
        method: str = "combined",
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        normalized = [self._normalize_document(doc, idx) for idx, doc in enumerate(documents)]

        if method in {"cross_encoder", "combined"}:
            if self._should_skip_cross_encoder(normalized):
                logger.info(
                    "Adaptive rerank: skipping cross-encoder (top score %.3f, gap %.3f)",
                    float(normalized[0].get("score") or 0.0),
                    float(normalized[0].get("score") or 0.0) - float(normalized[1].get("score") or 0.0),
                )
                ranked_docs = normalized
            else:
                ranked = self.cross_encoder.rerank(query, normalized, top_k=None)
                ranked_docs = [item.to_dict() for item in ranked]
        else:
            ranked_docs = normalized

        if method in {"mmr", "combined"} and self.use_mmr:
            mmr_input = [self._normalize_document(doc, idx) for idx, doc in enumerate(ranked_docs)]
            ranked = self.mmr.rerank(query, mmr_input, top_k=top_k)
            return [item.to_dict() for item in ranked]

        return ranked_docs[:top_k] if top_k else ranked_docs

    def _normalize_document(self, document: Any, idx: int) -> Dict[str, Any]:
        if isinstance(document, RankedResult):
            return document.to_dict()

        if isinstance(document, dict):
            text = document.get("text") or document.get("document") or ""
            score = document.get("score")
            if score is None:
                score = document.get("original_score", 0.0)
            return {
                "chunk_id": document.get("chunk_id") or document.get("id") or f"chunk_{idx}",
                "text": text,
                "score": float(score or 0.0),
                "metadata": document.get("metadata", {}),
            }

        return {
            "chunk_id": f"chunk_{idx}",
            "text": str(document),
            "score": 0.0,
            "metadata": {},
        }


# Factory functions
def create_cross_encoder_reranker(model_name: Optional[str] = None) -> CrossEncoderReranker:
    """Create cross-encoder reranker with config defaults"""
    model_name = model_name or "cross-encoder/ms-marco-MiniLM-L-12-v2"
    return CrossEncoderReranker(model_name=model_name)


def create_mmr_reranker(lambda_param: Optional[float] = None) -> MMRReranker:
    """Create MMR reranker with config defaults"""
    lambda_param = lambda_param or config.MMR_DIVERSITY_LAMBDA
    return MMRReranker(lambda_param=lambda_param)


# Example usage
if __name__ == "__main__":
    # Test cross-encoder reranking
    sample_results = [
        {'chunk_id': '1', 'text': 'Machine learning is a field of artificial intelligence', 'score': 0.8},
        {'chunk_id': '2', 'text': 'Deep learning uses neural networks', 'score': 0.7},
        {'chunk_id': '3', 'text': 'Python is a programming language', 'score': 0.6},
    ]

    query = "What is machine learning?"

    # Cross-encoder
    ce_reranker = create_cross_encoder_reranker()
    reranked = ce_reranker.rerank(query, sample_results, top_k=2)

    print("\nCross-Encoder Reranking:")
    for r in reranked:
        print(f"  Rank {r.reranked_rank} (was {r.original_rank}): {r.text[:50]}... (score: {r.score:.3f})")

    # MMR
    mmr_reranker = create_mmr_reranker(lambda_param=0.5)
    diverse = mmr_reranker.rerank(query, sample_results, top_k=2)

    print("\nMMR Diverse Reranking:")
    for r in diverse:
        print(f"  Rank {r.reranked_rank} (was {r.original_rank}): {r.text[:50]}...")
