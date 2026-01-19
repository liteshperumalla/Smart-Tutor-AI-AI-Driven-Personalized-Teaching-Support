"""
Advanced RAG Modules for Smart AI Tutor

This package contains state-of-the-art RAG enhancement modules:
- Semantic Chunking: Structure-aware document chunking
- Hybrid Search: BM25 + Semantic search with RRF
- Reranking: Cross-encoder + MMR diversity
- HyDE: Hypothetical Document Embeddings
- Query Enhancement: Intent, entities, rewriting, expansion, decomposition

Author: Smart AI Tutor Team
Date: December 28, 2025
"""

# Version
__version__ = "1.0.0"

# Semantic Chunking
from .semantic_chunker import (
    SemanticChunker,
    Chunk,
    ChunkType,
    create_semantic_chunker
)

# Hybrid Search
from .hybrid_search import (
    BM25Retriever,
    HybridSearcher,
    SearchResult,
    create_bm25_retriever,
    create_hybrid_searcher
)

# Reranking
from .reranker import (
    CrossEncoderReranker,
    LLMReranker,
    MMRReranker,
    RankedResult,
    create_cross_encoder_reranker,
    create_mmr_reranker
)

# HyDE
from .hyde import (
    HyDEGenerator,
    HyDERetriever,
    HyDEResult,
    create_hyde_generator,
    create_hyde_retriever
)

# Query Enhancement
from .query_enhancement import (
    QueryEnhancementPipeline,
    EnhancedQuery,
    QueryIntent,
    IntentClassifier,
    EntityExtractor,
    QueryRewriter,
    QueryExpander,
    QueryDecomposer,
    create_query_enhancement_pipeline
)

__all__ = [
    # Version
    "__version__",

    # Semantic Chunking
    "SemanticChunker",
    "Chunk",
    "ChunkType",
    "create_semantic_chunker",

    # Hybrid Search
    "BM25Retriever",
    "HybridSearcher",
    "SearchResult",
    "create_bm25_retriever",
    "create_hybrid_searcher",

    # Reranking
    "CrossEncoderReranker",
    "LLMReranker",
    "MMRReranker",
    "RankedResult",
    "create_cross_encoder_reranker",
    "create_mmr_reranker",

    # HyDE
    "HyDEGenerator",
    "HyDERetriever",
    "HyDEResult",
    "create_hyde_generator",
    "create_hyde_retriever",

    # Query Enhancement
    "QueryEnhancementPipeline",
    "EnhancedQuery",
    "QueryIntent",
    "IntentClassifier",
    "EntityExtractor",
    "QueryRewriter",
    "QueryExpander",
    "QueryDecomposer",
    "create_query_enhancement_pipeline",
]


def get_version() -> str:
    """Get package version"""
    return __version__


def get_available_modules() -> dict:
    """Get list of available modules and their status"""
    modules = {
        "semantic_chunker": {
            "available": True,
            "description": "Structure-aware semantic chunking with context enrichment"
        },
        "hybrid_search": {
            "available": True,
            "description": "BM25 keyword + semantic embedding search with RRF"
        },
        "reranker": {
            "available": True,
            "description": "Cross-encoder + MMR + LLM reranking"
        },
        "hyde": {
            "available": True,
            "description": "Hypothetical Document Embeddings for improved retrieval"
        },
        "query_enhancement": {
            "available": True,
            "description": "Query intent, entities, rewriting, expansion, decomposition"
        }
    }
    return modules


# Convenience function for quick setup
def create_enhanced_rag_pipeline(
    llm_provider=None,
    embeddings_model=None,
    semantic_retriever=None,
    enable_hybrid_search: bool = True,
    enable_reranking: bool = True,
    enable_hyde: bool = False,
    enable_query_enhancement: bool = True
):
    """
    Create a complete enhanced RAG pipeline with all components

    Args:
        llm_provider: LLM instance (for query enhancement, HyDE)
        embeddings_model: Embeddings model
        semantic_retriever: Base semantic retriever
        enable_hybrid_search: Enable BM25 + semantic hybrid search
        enable_reranking: Enable cross-encoder reranking
        enable_hyde: Enable HyDE (more expensive, better for definitional queries)
        enable_query_enhancement: Enable query enhancement pipeline

    Returns:
        Dictionary with initialized components

    Example:
        >>> from backend.rag import create_enhanced_rag_pipeline
        >>> pipeline = create_enhanced_rag_pipeline(
        ...     llm_provider=bedrock_llm,
        ...     embeddings_model=titan_embeddings,
        ...     semantic_retriever=s3_retriever,
        ...     enable_hybrid_search=True,
        ...     enable_reranking=True
        ... )
        >>> # Use components
        >>> enhanced_query = pipeline['query_enhancer'].enhance(query)
        >>> results = pipeline['hybrid_searcher'].search(enhanced_query.rewritten_query)
        >>> reranked = pipeline['reranker'].rerank(query, results)
    """
    components = {}

    # Query Enhancement
    if enable_query_enhancement:
        components['query_enhancer'] = create_query_enhancement_pipeline(llm_provider)

    # Hybrid Search
    if enable_hybrid_search and semantic_retriever:
        components['hybrid_searcher'] = create_hybrid_searcher(
            semantic_retriever=semantic_retriever,
            alpha=0.5
        )

    # Reranking
    if enable_reranking:
        components['cross_encoder_reranker'] = create_cross_encoder_reranker()
        components['mmr_reranker'] = create_mmr_reranker(lambda_param=0.5)

    # HyDE (optional)
    if enable_hyde and llm_provider and embeddings_model:
        components['hyde_generator'] = create_hyde_generator(
            llm_provider=llm_provider,
            embeddings_model=embeddings_model
        )

    return components


# Example usage
if __name__ == "__main__":
    print(f"Smart AI Tutor RAG Modules v{__version__}")
    print("\nAvailable Modules:")
    for name, info in get_available_modules().items():
        status = "✓" if info['available'] else "✗"
        print(f"  {status} {name}: {info['description']}")
