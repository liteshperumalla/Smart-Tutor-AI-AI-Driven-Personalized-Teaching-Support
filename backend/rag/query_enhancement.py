"""
Advanced Query Enhancement Pipeline

Enhances user queries before retrieval to improve search quality:
1. Intent Classification - Understand query purpose
2. Entity Extraction - Identify key entities
3. Query Rewriting - Improve clarity and completeness
4. Query Expansion - Generate semantic variations
5. Query Decomposition - Break complex queries into sub-queries
6. Step-Back Prompting - Generate broader context queries

Author: Smart AI Tutor Team
Date: December 28, 2025
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


class QueryIntent(Enum):
    """Types of query intents"""
    FACTUAL = "factual"  # Who, What, When, Where
    PROCEDURAL = "procedural"  # How to
    CAUSAL = "causal"  # Why, Cause
    COMPARISON = "comparison"  # Compare, Difference
    DEFINITIONAL = "definitional"  # Define, Explain
    OPINION = "opinion"  # Should, Best
    COMPUTATIONAL = "computational"  # Calculate, Compute
    NAVIGATIONAL = "navigational"  # Find, Locate
    MULTI_PART = "multi_part"  # Multiple questions
    UNKNOWN = "unknown"


@dataclass
class EnhancedQuery:
    """Represents an enhanced query with metadata"""
    original_query: str
    rewritten_query: Optional[str] = None
    expansions: List[str] = field(default_factory=list)
    sub_queries: List[str] = field(default_factory=list)
    intent: QueryIntent = QueryIntent.UNKNOWN
    entities: List[Dict[str, str]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    complexity: str = "simple"  # simple, medium, complex
    requires_reasoning: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_all_queries(self) -> List[str]:
        """Get all query variations"""
        queries = [self.original_query]
        if self.rewritten_query:
            queries.append(self.rewritten_query)
        queries.extend(self.expansions)
        queries.extend(self.sub_queries)
        return queries


class IntentClassifier:
    """Classifies query intent using rule-based and ML approaches"""

    def __init__(self):
        """Initialize intent classifier"""
        self.patterns = self._init_patterns()
        logger.info("IntentClassifier initialized")

    def _init_patterns(self) -> Dict[QueryIntent, List[str]]:
        """Initialize intent patterns"""
        return {
            QueryIntent.DEFINITIONAL: [
                r'^what (is|are|was|were)',
                r'^define',
                r'^explain',
                r'^describe',
                r'meaning of',
                r'definition'
            ],
            QueryIntent.PROCEDURAL: [
                r'^how (to|do|does|can)',
                r'^steps to',
                r'^way to',
                r'^procedure',
                r'^process of',
                r'method for'
            ],
            QueryIntent.CAUSAL: [
                r'^why',
                r'^what causes',
                r'^reason for',
                r'^cause of',
                r'because',
                r'due to'
            ],
            QueryIntent.COMPARISON: [
                r'compare',
                r'difference between',
                r'versus',
                r'\bvs\b',
                r'better than',
                r'similar to',
                r'rather than'
            ],
            QueryIntent.COMPUTATIONAL: [
                r'calculate',
                r'compute',
                r'solve',
                r'evaluate',
                r'find the value',
                r'\d+\s*[\+\-\*\/]'
            ],
            QueryIntent.FACTUAL: [
                r'^who',
                r'^when',
                r'^where',
                r'^which',
                r'what year',
                r'what time'
            ],
            QueryIntent.OPINION: [
                r'^should',
                r'best',
                r'worst',
                r'recommend',
                r'opinion',
                r'think about'
            ]
        }

    def classify(self, query: str) -> QueryIntent:
        """
        Classify query intent

        Args:
            query: User query

        Returns:
            QueryIntent enum
        """
        query_lower = query.lower().strip()

        # Check for multiple questions (multi-part)
        if self._is_multi_part(query_lower):
            return QueryIntent.MULTI_PART

        # Try pattern matching
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent

        # Default to factual if contains question words
        if any(q in query_lower for q in ['what', 'which', 'how', 'why', 'who', 'when', 'where']):
            return QueryIntent.FACTUAL

        return QueryIntent.UNKNOWN

    def _is_multi_part(self, query: str) -> bool:
        """Check if query contains multiple questions"""
        # Count question marks
        if query.count('?') > 1:
            return True

        # Check for multiple question words
        question_words = ['what', 'how', 'why', 'who', 'when', 'where', 'which']
        count = sum(1 for q in question_words if q in query)
        return count > 2


class EntityExtractor:
    """Extracts named entities from queries"""

    def __init__(self):
        """Initialize entity extractor"""
        self.nlp = None

        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("EntityExtractor initialized with spaCy")
            except OSError:
                logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
        else:
            logger.warning("spaCy not available. Entity extraction will be rule-based.")

    def extract(self, query: str) -> List[Dict[str, str]]:
        """
        Extract entities from query

        Args:
            query: User query

        Returns:
            List of entities with type and text
        """
        if self.nlp:
            return self._extract_with_spacy(query)
        else:
            return self._extract_with_rules(query)

    def _extract_with_spacy(self, query: str) -> List[Dict[str, str]]:
        """Extract entities using spaCy"""
        doc = self.nlp(query)

        entities = []
        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'type': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            })

        return entities

    def _extract_with_rules(self, query: str) -> List[Dict[str, str]]:
        """Extract entities using simple rules"""
        entities = []

        # Capitalized words (potential proper nouns)
        words = query.split()
        for word in words:
            if word[0].isupper() and len(word) > 1:
                entities.append({
                    'text': word,
                    'type': 'PROPER_NOUN',
                    'start': query.index(word),
                    'end': query.index(word) + len(word)
                })

        # Numbers and dates
        numbers = re.findall(r'\b\d+\b', query)
        for num in numbers:
            entities.append({
                'text': num,
                'type': 'NUMBER',
                'start': query.index(num),
                'end': query.index(num) + len(num)
            })

        return entities


class QueryRewriter:
    """Rewrites queries for better clarity and completeness"""

    def __init__(self, llm_provider: Any = None):
        """
        Initialize query rewriter

        Args:
            llm_provider: LLM instance for rewriting
        """
        self.llm = llm_provider
        logger.info("QueryRewriter initialized")

    def rewrite(self, query: str, context: Optional[str] = None) -> str:
        """
        Rewrite query for better retrieval

        Args:
            query: Original query
            context: Optional conversation context

        Returns:
            Rewritten query
        """
        if not self.llm:
            return self._rule_based_rewrite(query)

        return self._llm_based_rewrite(query, context)

    def _rule_based_rewrite(self, query: str) -> str:
        """Simple rule-based query rewriting"""
        rewritten = query

        # Expand contractions
        contractions = {
            "what's": "what is",
            "how's": "how is",
            "that's": "that is",
            "it's": "it is",
            "i'm": "i am",
            "you're": "you are",
            "we're": "we are",
            "they're": "they are",
            "can't": "cannot",
            "won't": "will not",
            "don't": "do not",
            "doesn't": "does not"
        }

        for contraction, expansion in contractions.items():
            rewritten = re.sub(r'\b' + contraction + r'\b', expansion, rewritten, flags=re.IGNORECASE)

        # Remove filler words at start
        filler_words = ['um', 'uh', 'like', 'you know', 'i mean']
        for filler in filler_words:
            rewritten = re.sub(r'^' + filler + r'\s+', '', rewritten, flags=re.IGNORECASE)

        return rewritten.strip()

    def _llm_based_rewrite(self, query: str, context: Optional[str] = None) -> str:
        """LLM-based query rewriting for better clarity"""
        prompt = f"""Rewrite the following question to be clearer and more specific for search.
Make it concise, complete, and include relevant context.
Do not change the meaning or intent.

Original question: {query}"""

        if context:
            prompt += f"\nConversation context: {context}"

        prompt += "\n\nRewritten question:"

        try:
            rewritten = self.llm.generate(prompt, max_tokens=100, temperature=0.3)
            return rewritten.strip()
        except Exception as e:
            logger.error(f"Error in LLM rewriting: {e}")
            return self._rule_based_rewrite(query)


class QueryExpander:
    """Generates semantic variations of queries"""

    def __init__(self, llm_provider: Any = None, num_expansions: int = 3):
        """
        Initialize query expander

        Args:
            llm_provider: LLM for generating expansions
            num_expansions: Number of variations to generate
        """
        self.llm = llm_provider
        self.num_expansions = num_expansions
        logger.info(f"QueryExpander initialized (num_expansions={num_expansions})")

    def expand(self, query: str) -> List[str]:
        """
        Generate query variations

        Args:
            query: Original query

        Returns:
            List of query variations
        """
        if not self.llm:
            return self._rule_based_expansion(query)

        return self._llm_based_expansion(query)

    def _rule_based_expansion(self, query: str) -> List[str]:
        """Simple rule-based query expansion"""
        expansions = []

        # Synonym substitution (basic)
        synonyms = {
            'define': ['explain', 'describe', 'what is'],
            'how': ['method', 'way', 'steps'],
            'why': ['reason', 'cause', 'purpose'],
            'best': ['optimal', 'ideal', 'top']
        }

        query_lower = query.lower()
        for word, syns in synonyms.items():
            if word in query_lower:
                for syn in syns[:2]:  # Use first 2 synonyms
                    expanded = query_lower.replace(word, syn)
                    if expanded != query_lower:
                        expansions.append(expanded.capitalize())

        return expansions[:self.num_expansions]

    def _llm_based_expansion(self, query: str) -> List[str]:
        """LLM-based query expansion"""
        prompt = f"""Generate {self.num_expansions} alternative ways to phrase this question.
Each alternative should have the same meaning but use different words.

Original question: {query}

Alternative phrasings (one per line):"""

        try:
            response = self.llm.generate(prompt, max_tokens=200, temperature=0.7)

            # Parse expansions
            expansions = []
            for line in response.strip().split('\n'):
                line = line.strip()
                # Remove numbering (1., 2., etc.)
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                if line and line != query:
                    expansions.append(line)

            return expansions[:self.num_expansions]

        except Exception as e:
            logger.error(f"Error in LLM expansion: {e}")
            return self._rule_based_expansion(query)


class QueryDecomposer:
    """Decomposes complex queries into simpler sub-queries"""

    def __init__(self, llm_provider: Any = None):
        """
        Initialize query decomposer

        Args:
            llm_provider: LLM for decomposition
        """
        self.llm = llm_provider
        logger.info("QueryDecomposer initialized")

    def decompose(self, query: str) -> List[str]:
        """
        Decompose complex query into sub-queries

        Args:
            query: Complex query

        Returns:
            List of sub-queries
        """
        # Check if decomposition is needed
        if not self._needs_decomposition(query):
            return [query]

        if self.llm:
            return self._llm_based_decomposition(query)
        else:
            return self._rule_based_decomposition(query)

    def _needs_decomposition(self, query: str) -> bool:
        """Check if query needs decomposition"""
        # Check for multiple question marks
        if query.count('?') > 1:
            return True

        # Check for conjunctions indicating multiple parts
        multi_part_words = ['and', 'also', 'additionally', 'furthermore', 'moreover']
        count = sum(1 for word in multi_part_words if f' {word} ' in query.lower())
        return count > 0

    def _rule_based_decomposition(self, query: str) -> List[str]:
        """Simple rule-based decomposition"""
        # Split on question marks
        if '?' in query:
            parts = query.split('?')
            sub_queries = [p.strip() + '?' for p in parts if p.strip()]
            return sub_queries

        # Split on 'and'
        parts = re.split(r'\s+and\s+', query, flags=re.IGNORECASE)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

        return [query]

    def _llm_based_decomposition(self, query: str) -> List[str]:
        """LLM-based query decomposition"""
        prompt = f"""This question contains multiple parts. Break it down into simpler sub-questions.
Each sub-question should be self-contained and answerable independently.

Complex question: {query}

Sub-questions (one per line):"""

        try:
            response = self.llm.generate(prompt, max_tokens=200, temperature=0.3)

            # Parse sub-queries
            sub_queries = []
            for line in response.strip().split('\n'):
                line = line.strip()
                # Remove numbering
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                if line:
                    sub_queries.append(line)

            return sub_queries if sub_queries else [query]

        except Exception as e:
            logger.error(f"Error in LLM decomposition: {e}")
            return self._rule_based_decomposition(query)


class QueryEnhancementPipeline:
    """
    Comprehensive query enhancement pipeline

    Orchestrates all enhancement techniques.
    """

    def __init__(
        self,
        llm_provider: Any = None,
        enable_all: bool = True
    ):
        """
        Initialize enhancement pipeline

        Args:
            llm_provider: LLM for enhancement tasks
            enable_all: Enable all enhancement techniques
        """
        self.llm = llm_provider

        # Initialize components
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.query_rewriter = QueryRewriter(llm_provider)
        self.query_expander = QueryExpander(llm_provider, num_expansions=config.QUERY_EXPANSION_NUM)
        self.query_decomposer = QueryDecomposer(llm_provider)

        self.enable_all = enable_all

        logger.info("QueryEnhancementPipeline initialized")

    def enhance(
        self,
        query: str,
        enable_rewriting: bool = True,
        enable_expansion: bool = True,
        enable_decomposition: bool = True
    ) -> EnhancedQuery:
        """
        Enhance query with all techniques

        Args:
            query: Original query
            enable_rewriting: Enable query rewriting
            enable_expansion: Enable query expansion
            enable_decomposition: Enable query decomposition

        Returns:
            EnhancedQuery object with all enhancements
        """
        # 1. Classify intent
        intent = self.intent_classifier.classify(query)

        # 2. Extract entities
        entities = self.entity_extractor.extract(query)

        # 3. Extract keywords (simple)
        keywords = self._extract_keywords(query)

        # 4. Assess complexity
        complexity = self._assess_complexity(query, intent)

        # 5. Rewrite query if enabled
        rewritten_query = None
        if enable_rewriting and (self.enable_all or config.QUERY_REWRITING_ENABLED):
            rewritten_query = self.query_rewriter.rewrite(query)

        # 6. Expand query if enabled
        expansions = []
        if enable_expansion and (self.enable_all or config.QUERY_EXPANSION_ENABLED):
            expansions = self.query_expander.expand(query)

        # 7. Decompose if needed
        sub_queries = []
        if enable_decomposition and complexity in ['complex', 'medium']:
            sub_queries = self.query_decomposer.decompose(query)
            if len(sub_queries) == 1:
                sub_queries = []  # Not actually decomposed

        # 8. Determine if reasoning required
        requires_reasoning = self._requires_reasoning(query, intent)

        # Build enhanced query
        enhanced = EnhancedQuery(
            original_query=query,
            rewritten_query=rewritten_query,
            expansions=expansions,
            sub_queries=sub_queries,
            intent=intent,
            entities=entities,
            keywords=keywords,
            complexity=complexity,
            requires_reasoning=requires_reasoning,
            metadata={
                'num_entities': len(entities),
                'num_keywords': len(keywords),
                'num_expansions': len(expansions),
                'num_sub_queries': len(sub_queries)
            }
        )

        logger.info(
            f"Enhanced query: intent={intent.value}, complexity={complexity}, "
            f"sub_queries={len(sub_queries)}"
        )

        return enhanced

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query"""
        # Remove stop words and punctuation
        stop_words = {'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
                     'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
                     'to', 'was', 'will', 'with'}

        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def _assess_complexity(self, query: str, intent: QueryIntent) -> str:
        """Assess query complexity"""
        # Simple heuristics
        word_count = len(query.split())

        if word_count < 5:
            return "simple"
        elif word_count > 15 or intent == QueryIntent.MULTI_PART:
            return "complex"
        else:
            return "medium"

    def _requires_reasoning(self, query: str, intent: QueryIntent) -> bool:
        """Check if query requires multi-step reasoning"""
        reasoning_intents = [QueryIntent.CAUSAL, QueryIntent.COMPARISON, QueryIntent.MULTI_PART]

        if intent in reasoning_intents:
            return True

        reasoning_keywords = ['compare', 'analyze', 'evaluate', 'relationship', 'impact']
        query_lower = query.lower()

        return any(keyword in query_lower for keyword in reasoning_keywords)


# Factory function
def create_query_enhancement_pipeline(llm_provider: Any = None) -> QueryEnhancementPipeline:
    """
    Create query enhancement pipeline

    Args:
        llm_provider: LLM instance

    Returns:
        QueryEnhancementPipeline
    """
    return QueryEnhancementPipeline(llm_provider=llm_provider)


# Example usage
if __name__ == "__main__":
    # Test query enhancement
    pipeline = create_query_enhancement_pipeline()

    queries = [
        "What is machine learning?",
        "How do neural networks work and why are they effective?",
        "Compare supervised learning versus unsupervised learning",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Original: {query}")
        enhanced = pipeline.enhance(query)
        print(f"Intent: {enhanced.intent.value}")
        print(f"Complexity: {enhanced.complexity}")
        print(f"Entities: {[e['text'] for e in enhanced.entities]}")
        print(f"Keywords: {enhanced.keywords}")
        if enhanced.rewritten_query:
            print(f"Rewritten: {enhanced.rewritten_query}")
        if enhanced.expansions:
            print(f"Expansions: {enhanced.expansions}")
        if enhanced.sub_queries:
            print(f"Sub-queries: {enhanced.sub_queries}")
