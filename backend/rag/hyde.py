"""
HyDE (Hypothetical Document Embeddings) Implementation

HyDE improves retrieval by:
1. Generating a hypothetical answer to the query using an LLM
2. Embedding the hypothetical answer instead of the query
3. Searching with the answer embedding (more similar to actual documents)

This is especially effective for:
- Definitional questions ("What is X?")
- Explanation queries ("How does X work?")
- Questions where the answer format is predictable

Paper: "Precise Zero-Shot Dense Retrieval without Relevance Labels" (Gao et al., 2022)

Author: Smart AI Tutor Team
Date: December 28, 2025
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HyDEResult:
    """Represents a HyDE-enhanced query"""
    original_query: str
    hypothetical_document: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class HyDEGenerator:
    """
    Hypothetical Document Embeddings (HyDE) Generator

    Workflow:
    1. User Query → LLM → Hypothetical Answer
    2. Hypothetical Answer → Embedding Model → Answer Embedding
    3. Answer Embedding → Vector Search → Relevant Documents
    4. Documents → LLM → Final Answer
    """

    def __init__(
        self,
        llm_provider: Any = None,
        embeddings_model: Any = None,
        num_hypothetical_docs: int = 1,
        temperature: float = 0.7
    ):
        """
        Initialize HyDE generator

        Args:
            llm_provider: LLM instance for generating hypothetical documents
            embeddings_model: Embedding model for encoding hypothetical docs
            num_hypothetical_docs: Number of hypothetical documents to generate
            temperature: Temperature for LLM generation (higher = more diverse)
        """
        self.llm = llm_provider
        self.embeddings = embeddings_model
        self.num_hypothetical_docs = num_hypothetical_docs
        self.temperature = temperature

        if not self.llm:
            logger.warning("No LLM provided. HyDE will be disabled.")
        if not self.embeddings:
            logger.warning("No embeddings model provided. HyDE will use regular query embeddings.")

        logger.info(
            f"HyDEGenerator initialized (num_docs={num_hypothetical_docs}, temp={temperature})"
        )

    def generate_hypothetical_document(
        self,
        query: str,
        domain: str = "general",
        max_tokens: int = 300
    ) -> str:
        """
        Generate a hypothetical document that would answer the query

        Args:
            query: User query
            domain: Domain context (e.g., "computer science", "biology")
            max_tokens: Maximum tokens for hypothetical document

        Returns:
            Hypothetical document text
        """
        if not self.llm:
            logger.warning("LLM not available. Returning original query.")
            return query

        # Construct prompt for hypothetical document generation
        prompt = self._create_hyde_prompt(query, domain)

        try:
            hypothetical_doc = self.llm.generate(
                prompt,
                max_tokens=max_tokens,
                temperature=self.temperature
            )

            # Clean up the response
            hypothetical_doc = hypothetical_doc.strip()

            logger.debug(f"Generated hypothetical doc for: {query[:50]}...")
            return hypothetical_doc

        except Exception as e:
            logger.error(f"Error generating hypothetical document: {e}")
            return query  # Fallback to original query

    def generate_multiple_hypothetical_documents(
        self,
        query: str,
        domain: str = "general"
    ) -> List[str]:
        """
        Generate multiple diverse hypothetical documents

        Args:
            query: User query
            domain: Domain context

        Returns:
            List of hypothetical documents
        """
        hypothetical_docs = []

        for i in range(self.num_hypothetical_docs):
            doc = self.generate_hypothetical_document(query, domain)
            hypothetical_docs.append(doc)

        return hypothetical_docs

    def enhance_query(
        self,
        query: str,
        domain: str = "general",
        return_embedding: bool = True
    ) -> HyDEResult:
        """
        Enhance query using HyDE

        Args:
            query: Original user query
            domain: Domain context
            return_embedding: Whether to compute embedding

        Returns:
            HyDEResult with hypothetical document and optional embedding
        """
        # Generate hypothetical document
        hypothetical_doc = self.generate_hypothetical_document(query, domain)

        # Compute embedding if requested
        embedding = None
        if return_embedding and self.embeddings:
            try:
                # Embed the hypothetical document instead of the query
                embedding_result = self.embeddings.encode([hypothetical_doc])
                if embedding_result and len(embedding_result) > 0:
                    embedding = embedding_result[0]
            except Exception as e:
                logger.error(f"Error computing HyDE embedding: {e}")

        result = HyDEResult(
            original_query=query,
            hypothetical_document=hypothetical_doc,
            embedding=embedding,
            metadata={
                'domain': domain,
                'method': 'hyde',
                'num_hypothetical_docs': 1
            }
        )

        return result

    def enhance_query_with_multiple_docs(
        self,
        query: str,
        domain: str = "general",
        return_embeddings: bool = True
    ) -> List[HyDEResult]:
        """
        Enhance query with multiple hypothetical documents

        Useful for ambiguous queries or when diversity is important.

        Args:
            query: Original query
            domain: Domain context
            return_embeddings: Whether to compute embeddings

        Returns:
            List of HyDEResult objects (one per hypothetical document)
        """
        hypothetical_docs = self.generate_multiple_hypothetical_documents(query, domain)

        results = []
        embeddings_to_compute = hypothetical_docs if return_embeddings and self.embeddings else []

        # Batch compute embeddings if needed
        embeddings = []
        if embeddings_to_compute:
            try:
                embeddings = self.embeddings.encode(embeddings_to_compute)
            except Exception as e:
                logger.error(f"Error computing batch embeddings: {e}")
                embeddings = [None] * len(hypothetical_docs)

        # Create results
        for idx, doc in enumerate(hypothetical_docs):
            embedding = embeddings[idx] if idx < len(embeddings) else None

            result = HyDEResult(
                original_query=query,
                hypothetical_document=doc,
                embedding=embedding,
                metadata={
                    'domain': domain,
                    'method': 'hyde_multi',
                    'doc_index': idx,
                    'num_hypothetical_docs': len(hypothetical_docs)
                }
            )
            results.append(result)

        return results

    def _create_hyde_prompt(self, query: str, domain: str) -> str:
        """
        Create prompt for hypothetical document generation

        Different prompts for different types of queries.
        """
        # Detect query type
        query_lower = query.lower()

        if any(q in query_lower for q in ['what is', 'define', 'explain', 'describe']):
            # Definitional query
            prompt = f"""Write a clear, informative paragraph that answers this question: "{query}"

Write as if you are an expert in {domain}. Provide a comprehensive explanation with key details and examples.

Answer:"""

        elif any(q in query_lower for q in ['how to', 'how do', 'steps to']):
            # Procedural query
            prompt = f"""Write a step-by-step guide that answers this question: "{query}"

Provide clear, actionable steps with explanations. Write as an expert in {domain}.

Guide:"""

        elif any(q in query_lower for q in ['why', 'reason', 'cause']):
            # Causal query
            prompt = f"""Explain the reasons and causes related to this question: "{query}"

Provide a detailed explanation of the underlying reasons and mechanisms. Write as an expert in {domain}.

Explanation:"""

        elif any(q in query_lower for q in ['compare', 'difference', 'vs', 'versus']):
            # Comparison query
            prompt = f"""Write a comparison that addresses this question: "{query}"

Clearly explain the key similarities and differences. Write as an expert in {domain}.

Comparison:"""

        else:
            # General query
            prompt = f"""Write a comprehensive answer to this question: "{query}"

Provide detailed information with examples where relevant. Write as an expert in {domain}.

Answer:"""

        return prompt


class HyDERetriever:
    """
    Retriever that uses HyDE for enhanced retrieval

    Wraps an existing retriever and enhances queries with HyDE.
    """

    def __init__(
        self,
        base_retriever: Any,
        hyde_generator: HyDEGenerator,
        use_hybrid: bool = True,
        hybrid_alpha: float = 0.5
    ):
        """
        Initialize HyDE retriever

        Args:
            base_retriever: Underlying retriever (semantic, hybrid, etc.)
            hyde_generator: HyDE generator instance
            use_hybrid: Combine HyDE with original query
            hybrid_alpha: Weight for HyDE vs original (0=original, 1=HyDE)
        """
        self.base_retriever = base_retriever
        self.hyde_generator = hyde_generator
        self.use_hybrid = use_hybrid
        self.hybrid_alpha = hybrid_alpha

        logger.info(f"HyDERetriever initialized (hybrid={use_hybrid}, alpha={hybrid_alpha})")

    def retrieve(
        self,
        query: str,
        domain: str = "general",
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using HyDE-enhanced query

        Args:
            query: User query
            domain: Domain context
            top_k: Number of results

        Returns:
            List of retrieved results
        """
        # Generate hypothetical document
        hyde_result = self.hyde_generator.enhance_query(
            query,
            domain=domain,
            return_embedding=True
        )

        if not self.use_hybrid:
            # Pure HyDE: use only hypothetical document embedding
            return self._retrieve_with_hyde(hyde_result, top_k)
        else:
            # Hybrid: combine HyDE and original query
            return self._retrieve_hybrid(query, hyde_result, top_k)

    def _retrieve_with_hyde(
        self,
        hyde_result: HyDEResult,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Retrieve using only HyDE embedding"""
        if not hyde_result.embedding:
            # Fallback to text search
            logger.warning("No HyDE embedding available. Using hypothetical document text.")
            return self.base_retriever.retrieve(hyde_result.hypothetical_document, top_k=top_k)

        # Use embedding for retrieval
        # Assuming base_retriever supports embedding-based search
        try:
            results = self.base_retriever.search(
                query_embedding=hyde_result.embedding,
                top_k=top_k
            )
            return results
        except Exception as e:
            logger.error(f"Error in HyDE retrieval: {e}")
            return []

    def _retrieve_hybrid(
        self,
        original_query: str,
        hyde_result: HyDEResult,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Retrieve using combination of original and HyDE"""
        # Retrieve with both original query and HyDE
        try:
            # Original query results
            original_results = self.base_retriever.retrieve(original_query, top_k=top_k * 2)

            # HyDE results
            hyde_results = self._retrieve_with_hyde(hyde_result, top_k=top_k * 2)

            # Merge results using weighted scores
            merged = self._merge_results(original_results, hyde_results, self.hybrid_alpha)

            return merged[:top_k]

        except Exception as e:
            logger.error(f"Error in hybrid HyDE retrieval: {e}")
            return []

    def _merge_results(
        self,
        original_results: List[Dict[str, Any]],
        hyde_results: List[Dict[str, Any]],
        alpha: float
    ) -> List[Dict[str, Any]]:
        """
        Merge original and HyDE results

        Args:
            original_results: Results from original query
            hyde_results: Results from HyDE query
            alpha: Weight for HyDE (1-alpha for original)

        Returns:
            Merged and deduplicated results
        """
        # Build score maps
        original_scores = {r.get('chunk_id'): r.get('score', 0) for r in original_results}
        hyde_scores = {r.get('chunk_id'): r.get('score', 0) for r in hyde_results}

        # Get all unique chunk IDs
        all_chunk_ids = set(original_scores.keys()) | set(hyde_scores.keys())

        # Compute weighted scores
        merged_scores = {}
        for chunk_id in all_chunk_ids:
            orig_score = original_scores.get(chunk_id, 0)
            hyde_score = hyde_scores.get(chunk_id, 0)

            # Weighted combination
            merged_score = (1 - alpha) * orig_score + alpha * hyde_score

            merged_scores[chunk_id] = merged_score

        # Sort by merged score
        sorted_chunk_ids = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)

        # Build final results
        result_map = {}
        for r in original_results + hyde_results:
            chunk_id = r.get('chunk_id')
            if chunk_id not in result_map:
                result_map[chunk_id] = r

        merged_results = []
        for chunk_id, score in sorted_chunk_ids:
            if chunk_id in result_map:
                result = result_map[chunk_id].copy()
                result['score'] = score
                result['hyde_enhanced'] = True
                merged_results.append(result)

        return merged_results


# Factory function
def create_hyde_generator(
    llm_provider: Any = None,
    embeddings_model: Any = None,
    num_docs: int = 1
) -> HyDEGenerator:
    """
    Create HyDE generator

    Args:
        llm_provider: LLM instance
        embeddings_model: Embeddings model
        num_docs: Number of hypothetical documents to generate

    Returns:
        HyDEGenerator instance
    """
    return HyDEGenerator(
        llm_provider=llm_provider,
        embeddings_model=embeddings_model,
        num_hypothetical_docs=num_docs,
        temperature=0.7
    )


def create_hyde_retriever(
    base_retriever: Any,
    llm_provider: Any,
    embeddings_model: Any,
    use_hybrid: bool = True
) -> HyDERetriever:
    """
    Create HyDE retriever

    Args:
        base_retriever: Base retriever to wrap
        llm_provider: LLM for generating hypothetical documents
        embeddings_model: Embeddings model
        use_hybrid: Combine HyDE with original query

    Returns:
        HyDERetriever instance
    """
    hyde_gen = create_hyde_generator(llm_provider, embeddings_model)
    return HyDERetriever(
        base_retriever=base_retriever,
        hyde_generator=hyde_gen,
        use_hybrid=use_hybrid,
        hybrid_alpha=0.5
    )


# Example usage
if __name__ == "__main__":
    # Mock LLM for testing
    class MockLLM:
        def generate(self, prompt, **kwargs):
            # Mock hypothetical answer
            return "Machine learning is a branch of artificial intelligence that enables systems to learn from data and improve automatically without explicit programming. It uses algorithms to identify patterns in data and make predictions or decisions."

    # Mock embeddings
    class MockEmbeddings:
        def encode(self, texts):
            import random
            return [[random.random() for _ in range(384)] for _ in texts]

    # Test HyDE
    llm = MockLLM()
    embeddings = MockEmbeddings()

    hyde_gen = create_hyde_generator(llm, embeddings, num_docs=1)

    query = "What is machine learning?"
    result = hyde_gen.enhance_query(query, domain="computer science")

    print(f"\nOriginal Query: {result.original_query}")
    print(f"\nHypothetical Document:\n{result.hypothetical_document}")
    print(f"\nEmbedding Shape: {len(result.embedding) if result.embedding else 'None'}")
