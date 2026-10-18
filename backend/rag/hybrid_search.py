"""
Hybrid Search Module - BM25 + Semantic Search with Reciprocal Rank Fusion

Combines keyword-based search (BM25) with semantic search for optimal retrieval.

Features:
- BM25 keyword search (sparse retrieval)
- Semantic search with embeddings (dense retrieval)
- Reciprocal Rank Fusion (RRF) for score combination
- Configurable weighting between semantic and keyword
- Query preprocessing and optimization

Author: Smart AI Tutor Team
Date: December 28, 2025
"""

import math
import re
from typing import List, Dict, Any, Optional, Protocol, Tuple, Set
from dataclasses import dataclass
from collections import Counter, defaultdict
import numpy as np

try:
    import bm25s
    BM25S_AVAILABLE = True
except ImportError:
    BM25S_AVAILABLE = False

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Represents a search result with score and metadata"""
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    retrieval_method: str  # 'semantic', 'keyword', or 'hybrid'
    semantic_score: Optional[float] = None
    keyword_score: Optional[float] = None
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'score': self.score,
            'metadata': self.metadata,
            'retrieval_method': self.retrieval_method,
            'semantic_score': self.semantic_score,
            'keyword_score': self.keyword_score,
            'rank': self.rank
        }


class SemanticRetriever(Protocol):
    """Interface required by :class:`HybridSearcher` for dense retrieval.

    The concrete retriever is supplied by the active vector-store integration.
    Keeping this lightweight structural contract here prevents the RAG service
    from depending on a particular vector-store implementation.
    """

    def retrieve(self, query_bundle: Any) -> List[Any]:
        """Return scored semantic nodes for a LlamaIndex query bundle."""


class BM25Retriever:
    """
    BM25 (Best Match 25) keyword-based retriever

    BM25 is a probabilistic ranking function used in information retrieval.
    It scores documents based on query term frequency and inverse document frequency.

    Parameters:
    - k1 (1.2-2.0): Term frequency saturation parameter
    - b (0.75): Length normalization parameter
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        use_bm25s: bool = BM25S_AVAILABLE
    ):
        """
        Initialize BM25 retriever

        Args:
            k1: Term frequency saturation (1.2-2.0, default 1.5)
            b: Length normalization (0.0-1.0, default 0.75)
            use_bm25s: Use optimized bm25s library if available
        """
        self.k1 = k1
        self.b = b
        self.use_bm25s = use_bm25s and BM25S_AVAILABLE

        # Document collection
        self.documents: List[str] = []
        self.chunk_ids: List[str] = []
        self.metadata: Dict[str, Dict[str, Any]] = {}

        # BM25 statistics
        self.doc_freqs: Dict[str, int] = {}  # Term -> number of docs containing term
        self.doc_lens: List[int] = []  # Length of each document
        self.avg_doc_len: float = 0.0
        self.num_docs: int = 0
        self.idf: Dict[str, float] = {}  # Term -> IDF score

        # bm25s index (if using library)
        self.bm25s_index = None

        logger.info(f"BM25Retriever initialized (k1={k1}, b={b}, use_bm25s={self.use_bm25s})")

    def index_documents(
        self,
        chunk_ids: List[str],
        texts: List[str],
        metadata: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        """
        Index documents for BM25 search

        Args:
            chunk_ids: List of chunk IDs
            texts: List of document texts
            metadata: Optional metadata for each chunk
        """
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids and texts must have same length")

        self.chunk_ids = chunk_ids
        self.documents = texts
        self.metadata = metadata or {}
        self.num_docs = len(texts)

        if self.use_bm25s:
            # Use optimized bm25s library
            self._index_with_bm25s()
        else:
            # Use custom BM25 implementation
            self._index_with_custom()

        logger.info(f"Indexed {self.num_docs} documents for BM25 search")

    def _index_with_bm25s(self):
        """Index using bm25s library (faster)"""
        try:
            import bm25s
            from bm25s.tokenization import Tokenizer

            # Tokenize documents
            tokenizer = Tokenizer(stopwords="en", stemmer="english")
            corpus_tokens = tokenizer.tokenize(self.documents, return_as="tuple")

            # Create and index
            self.bm25s_index = bm25s.BM25(
                k1=self.k1,
                b=self.b,
                method="lucene"  # Use Lucene's BM25 variant
            )
            self.bm25s_index.index(corpus_tokens)

            logger.info("BM25 indexing completed using bm25s library")

        except Exception as e:
            logger.error(f"Error indexing with bm25s: {e}. Falling back to custom implementation.")
            self.use_bm25s = False
            self._index_with_custom()

    def _index_with_custom(self):
        """Index using custom BM25 implementation"""
        # Tokenize and compute statistics
        self.doc_lens = []
        term_doc_freq = defaultdict(set)  # term -> set of doc indices

        for doc_idx, text in enumerate(self.documents):
            tokens = self._tokenize(text)
            self.doc_lens.append(len(tokens))

            # Track which documents contain each term
            for token in set(tokens):
                term_doc_freq[token].add(doc_idx)

        # Compute average document length
        self.avg_doc_len = sum(self.doc_lens) / max(self.num_docs, 1)

        # Compute IDF for each term
        self.doc_freqs = {term: len(docs) for term, docs in term_doc_freq.items()}
        self.idf = {}

        for term, df in self.doc_freqs.items():
            # IDF formula: log((N - df + 0.5) / (df + 0.5) + 1)
            # This is the BM25 IDF variant
            self.idf[term] = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1)

        logger.info(f"BM25 indexing completed (custom): {len(self.idf)} unique terms")

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Search using BM25

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of SearchResult objects
        """
        if self.use_bm25s:
            return self._search_with_bm25s(query, top_k)
        else:
            return self._search_with_custom(query, top_k)

    def _search_with_bm25s(self, query: str, top_k: int) -> List[SearchResult]:
        """Search using bm25s library"""
        try:
            import bm25s
            from bm25s.tokenization import Tokenizer

            # Tokenize query
            tokenizer = Tokenizer(stopwords="en", stemmer="english")
            query_tokens = tokenizer.tokenize([query], return_as="tuple")[0]

            # Search
            scores, indices = self.bm25s_index.retrieve(
                query_tokens,
                k=top_k,
                return_as="tuple"
            )

            # Convert to SearchResult
            results = []
            for rank, (doc_idx, score) in enumerate(zip(indices[0], scores[0])):
                if doc_idx >= len(self.chunk_ids):
                    continue

                chunk_id = self.chunk_ids[doc_idx]
                text = self.documents[doc_idx]
                metadata = self.metadata.get(chunk_id, {})

                result = SearchResult(
                    chunk_id=chunk_id,
                    text=text,
                    score=float(score),
                    metadata=metadata,
                    retrieval_method='keyword',
                    keyword_score=float(score),
                    rank=rank + 1
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error searching with bm25s: {e}. Falling back to custom.")
            return self._search_with_custom(query, top_k)

    def _search_with_custom(self, query: str, top_k: int) -> List[SearchResult]:
        """Search using custom BM25 implementation"""
        query_tokens = self._tokenize(query)

        # Compute BM25 scores for each document
        scores = []

        for doc_idx, doc in enumerate(self.documents):
            doc_tokens = self._tokenize(doc)
            doc_len = self.doc_lens[doc_idx]

            # Count query term frequencies in document
            doc_term_freqs = Counter(doc_tokens)

            # BM25 score
            score = 0.0

            for query_term in query_tokens:
                if query_term not in self.idf:
                    continue  # Term not in corpus

                tf = doc_term_freqs.get(query_term, 0)
                idf = self.idf[query_term]

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)

                score += idf * (numerator / denominator)

            scores.append((doc_idx, score))

        # Sort by score and get top-k
        scores.sort(key=lambda x: x[1], reverse=True)
        top_scores = scores[:top_k]

        # Convert to SearchResult
        results = []
        for rank, (doc_idx, score) in enumerate(top_scores):
            chunk_id = self.chunk_ids[doc_idx]
            text = self.documents[doc_idx]
            metadata = self.metadata.get(chunk_id, {})

            result = SearchResult(
                chunk_id=chunk_id,
                text=text,
                score=score,
                metadata=metadata,
                retrieval_method='keyword',
                keyword_score=score,
                rank=rank + 1
            )
            results.append(result)

        return results

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25

        Args:
            text: Input text

        Returns:
            List of tokens (lowercased, no stopwords, stemmed)
        """
        # Lowercase
        text = text.lower()

        # Remove punctuation and split
        tokens = re.findall(r'\b\w+\b', text)

        # Remove common stopwords (basic list)
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'this', 'but', 'they', 'have', 'had',
            'what', 'when', 'where', 'who', 'which', 'why', 'how'
        }

        tokens = [t for t in tokens if t not in stopwords and len(t) > 2]

        # Simple stemming (remove common suffixes)
        def simple_stem(word):
            for suffix in ['ing', 'ed', 'ly', 's', 'es']:
                if word.endswith(suffix):
                    return word[:-len(suffix)]
            return word

        tokens = [simple_stem(t) for t in tokens]

        return tokens

    def get_stats(self) -> Dict[str, Any]:
        """Get BM25 index statistics"""
        return {
            'num_documents': self.num_docs,
            'avg_doc_length': self.avg_doc_len,
            'num_unique_terms': len(self.idf),
            'k1': self.k1,
            'b': self.b,
            'using_bm25s': self.use_bm25s
        }


class HybridSearcher:
    """
    Hybrid search combining BM25 and semantic search

    Uses Reciprocal Rank Fusion (RRF) to combine rankings:
    - Semantic search: Dense retrieval with embeddings
    - BM25 search: Sparse retrieval with keyword matching
    - RRF: score(d) = Σ 1 / (k + rank_i(d))
    """

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        semantic_retriever: Any,  # S3Retriever or similar
        alpha: float = 0.5,
        rrf_k: int = 60,
        top_k: int = 10
    ):
        """
        Initialize hybrid searcher

        Args:
            bm25_retriever: BM25 keyword retriever
            semantic_retriever: Semantic embedding retriever
            alpha: Weight for semantic vs keyword (0=keyword only, 1=semantic only)
            rrf_k: RRF parameter (usually 60)
            top_k: Number of results to return
        """
        self.bm25 = bm25_retriever
        self.semantic = semantic_retriever
        self.alpha = alpha
        self.rrf_k = rrf_k
        self.top_k = top_k

        logger.info(f"HybridSearcher initialized (alpha={alpha}, rrf_k={rrf_k})")

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        retrieval_mode: str = "hybrid"
    ) -> List[SearchResult]:
        """
        Perform hybrid search

        Args:
            query: Search query
            top_k: Number of results (overrides default)
            retrieval_mode: 'hybrid', 'semantic', or 'keyword'

        Returns:
            List of SearchResult objects ranked by hybrid score
        """
        top_k = top_k or self.top_k

        if retrieval_mode == "semantic":
            return self._semantic_only(query, top_k)
        elif retrieval_mode == "keyword":
            return self._keyword_only(query, top_k)
        else:
            return self._hybrid_search(query, top_k)

    def _semantic_only(self, query: str, top_k: int) -> List[SearchResult]:
        """Semantic search only"""
        from llama_index.core.schema import QueryBundle

        query_bundle = QueryBundle(query_str=query)
        nodes = self.semantic.retrieve(query_bundle)

        results = []
        for rank, node_with_score in enumerate(nodes[:top_k], 1):
            node = node_with_score.node
            score = node_with_score.score

            result = SearchResult(
                chunk_id=node.id_ or node.node_id,
                text=node.get_content(),
                score=score,
                metadata=node.metadata or {},
                retrieval_method='semantic',
                semantic_score=score,
                rank=rank
            )
            results.append(result)

        logger.info(f"Semantic search returned {len(results)} results")
        return results

    def _keyword_only(self, query: str, top_k: int) -> List[SearchResult]:
        """BM25 keyword search only"""
        results = self.bm25.search(query, top_k=top_k)
        logger.info(f"Keyword search returned {len(results)} results")
        return results

    def _hybrid_search(self, query: str, top_k: int) -> List[SearchResult]:
        """
        Hybrid search using Reciprocal Rank Fusion (RRF)

        RRF Score: score(d) = Σ 1 / (k + rank_i(d))
        where rank_i(d) is the rank of document d in retrieval method i
        """
        # Retrieve from both methods (get more candidates for RRF)
        fetch_k = top_k * 3  # Fetch more candidates

        # Semantic search
        semantic_results = self._semantic_only(query, fetch_k)

        # Keyword search
        keyword_results = self._keyword_only(query, fetch_k)

        # Build result maps
        semantic_map = {r.chunk_id: (r, rank + 1) for rank, r in enumerate(semantic_results)}
        keyword_map = {r.chunk_id: (r, rank + 1) for rank, r in enumerate(keyword_results)}

        # Get all unique chunk IDs
        all_chunk_ids = set(semantic_map.keys()) | set(keyword_map.keys())

        # Compute RRF scores
        rrf_scores = {}

        for chunk_id in all_chunk_ids:
            rrf_score = 0.0

            # Semantic component
            if chunk_id in semantic_map:
                _, rank = semantic_map[chunk_id]
                rrf_score += self.alpha / (self.rrf_k + rank)

            # Keyword component
            if chunk_id in keyword_map:
                _, rank = keyword_map[chunk_id]
                rrf_score += (1 - self.alpha) / (self.rrf_k + rank)

            rrf_scores[chunk_id] = rrf_score

        # Sort by RRF score
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Create hybrid results
        hybrid_results = []

        for rank, (chunk_id, rrf_score) in enumerate(sorted_chunks[:top_k], 1):
            # Get result from either semantic or keyword (prefer semantic)
            if chunk_id in semantic_map:
                base_result, _ = semantic_map[chunk_id]
            else:
                base_result, _ = keyword_map[chunk_id]

            # Create hybrid result
            semantic_score = semantic_map[chunk_id][0].score if chunk_id in semantic_map else None
            keyword_score = keyword_map[chunk_id][0].score if chunk_id in keyword_map else None

            result = SearchResult(
                chunk_id=chunk_id,
                text=base_result.text,
                score=rrf_score,
                metadata=base_result.metadata,
                retrieval_method='hybrid',
                semantic_score=semantic_score,
                keyword_score=keyword_score,
                rank=rank
            )
            hybrid_results.append(result)

        logger.info(
            f"Hybrid search: {len(semantic_results)} semantic + {len(keyword_results)} keyword "
            f"→ {len(hybrid_results)} fused results"
        )

        return hybrid_results

    def get_stats(self) -> Dict[str, Any]:
        """Get hybrid search statistics"""
        return {
            'alpha': self.alpha,
            'rrf_k': self.rrf_k,
            'top_k': self.top_k,
            'bm25_stats': self.bm25.get_stats()
        }


# Factory functions
def create_bm25_retriever() -> BM25Retriever:
    """Create BM25 retriever with default config"""
    return BM25Retriever(k1=1.5, b=0.75)


def create_hybrid_searcher(
    semantic_retriever: Any,
    alpha: float = 0.5
) -> HybridSearcher:
    """
    Create hybrid searcher

    Args:
        semantic_retriever: Existing semantic retriever (S3Retriever, etc.)
        alpha: Weight for semantic vs keyword (0.5 = balanced)

    Returns:
        HybridSearcher instance
    """
    bm25 = create_bm25_retriever()
    return HybridSearcher(
        bm25_retriever=bm25,
        semantic_retriever=semantic_retriever,
        alpha=alpha,
        top_k=config.SIMILARITY_TOP_K
    )


# Example usage
if __name__ == "__main__":
    # Test BM25
    chunk_ids = ["doc1", "doc2", "doc3"]
    texts = [
        "Machine learning is a subset of artificial intelligence",
        "Deep learning uses neural networks for pattern recognition",
        "Artificial intelligence enables machines to think like humans"
    ]

    bm25 = create_bm25_retriever()
    bm25.index_documents(chunk_ids, texts)

    results = bm25.search("machine learning", top_k=2)

    print("BM25 Search Results:")
    for r in results:
        print(f"  Rank {r.rank}: {r.text[:50]}... (score: {r.score:.3f})")
