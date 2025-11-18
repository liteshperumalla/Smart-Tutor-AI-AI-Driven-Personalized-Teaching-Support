import os
import json
import argparse
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings, get_response_synthesizer, PromptTemplate
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.response_synthesizers import BaseSynthesizer
from llama_index.llms.ollama import Ollama
from llama_index.core import StorageContext, load_index_from_storage
from sentence_transformers import SentenceTransformer, util, CrossEncoder
from llama_index.core.schema import Document, TextNode, NodeWithScore
from llama_index.core import VectorStoreIndex
from llama_index.retrievers.bm25 import BM25Retriever
from langfuse import Langfuse
from llama_index.core.callbacks import CallbackManager
from llama_index.callbacks.langfuse import langfuse_callback_handler as create_langfuse_handler
# from llama_index.agent.openai import OpenAIAgent  # Commented out due to version incompatibility
from dotenv import load_dotenv
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
import time

# SerpAPI integration
try:
    from serpapi import GoogleSearch
    SERPAPI_AVAILABLE = True
except ImportError:
    SERPAPI_AVAILABLE = False
    logging.warning("SerpAPI not available. Web search will use fallback method.")

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("Requests/BeautifulSoup not available. Web search disabled.")
    
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))
MAX_WEB_RESULTS = int(os.getenv("MAX_WEB_RESULTS", "3"))


# --- Langfuse Setup ---
# Load configuration from environment variables
try:
    from backend.config import config as app_config
    LANGFUSE_ENABLED = app_config.LANGFUSE_ENABLED
    LANGFUSE_PUBLIC_KEY = app_config.LANGFUSE_PUBLIC_KEY
    LANGFUSE_SECRET_KEY = app_config.LANGFUSE_SECRET_KEY
    LANGFUSE_HOST = app_config.LANGFUSE_HOST
except ImportError:
    logging.warning("Backend config not available, using environment variables directly")
    LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

langfuse_callback_handler = None
langfuse_client = None

if LANGFUSE_ENABLED and LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        handler = create_langfuse_handler(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST
        )
        Settings.callback_manager = CallbackManager([handler])
        logging.info("Langfuse callback handler initialized successfully.")
    except ImportError:
        logging.error("Failed to import langfuse callback handler. Please check Langfuse SDK version.")
        handler = None
    except Exception as e:
        logging.error(f"Failed to initialize Langfuse callback handler: {e}")
        langfuse_callback_handler = None

    try:
        langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST
        )
        logging.info("Langfuse client initialized.")
    except Exception as e:
        logging.error(f"Failed to initialize Langfuse client: {e}. Tracing might be partially or fully disabled.")
        langfuse_client = None
else:
    logging.info("Langfuse monitoring is disabled. Enable it by setting LANGFUSE_ENABLED=true and providing API keys.")

# --- Evaluation Framework ---
try:
    from backend.rag_evaluation import get_evaluator, RAGEvaluationContext
    EVALUATION_ENABLED = True
    logging.info("RAG evaluation framework enabled")
except ImportError:
    EVALUATION_ENABLED = False
    logging.info("RAG evaluation framework not available")

# --- Argument Parser ---
def parse_args():
    parser = argparse.ArgumentParser(description="Smart AI Tutor CLI")
    subparsers = parser.add_subparsers(dest='command')
    ingestion_parser = subparsers.add_parser('ingest', help="Ingest data into the index")
    ingestion_parser.add_argument('data_path', type=str, help="Path to the data to ingest")
    query_parser = subparsers.add_parser('query', help="Query the RAG model")
    query_parser.add_argument('query_text', type=str, help="Query text for the RAG model")
    subparsers.add_parser('chat', help="Interactive chat with the AI tutor")
    return parser.parse_args()

# --- Model Settings ---
# Phase 1 improvement: Upgraded to BAAI/bge-small-en-v1.5 for better retrieval accuracy
# Previous: sentence-transformers/all-MiniLM-L6-v2
# Expected improvement: +12-30% retrieval performance
try:
    embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
    logging.info("✅ Loaded embedding model: BAAI/bge-small-en-v1.5")
except Exception as e:
    logging.warning(f"⚠️ Failed to load BAAI/bge-small-en-v1.5, falling back to all-MiniLM-L6-v2: {e}")
    embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

Settings.llm = Ollama(model="llama3.2:latest", request_timeout=120.0)

# --- Directories ---
persist_dir = "./persisted_index"
os.makedirs(persist_dir, exist_ok=True)

# --- Prompt Templates ---
qa_template = PromptTemplate(
    "You are an expert Teaching Assistant for a university course. "
    "Your goal is to help students understand concepts clearly and accurately. "
    "Based ONLY on the context provided below, and no other outside knowledge, answer the user's question. "
    "Do not use any information that is not present in the context. "
    "If the context does not contain enough information to answer the question, say: "
    "\"Based on the provided context, I do not have enough information to answer this question.\" "
    "Your explanation should be clear, concise, and aimed at a university student. "
    "After your explanation, provide one simple, illustrative example to solidify the concept, if possible.\n\n"
    "CONTEXT:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "USER'S QUESTION: {query_str}\n\n"
    "YOUR ASSISTANT RESPONSE:"
)
web_search_template = PromptTemplate(
    "You are an expert Teaching Assistant for a university course. "
    "You are providing information from web search results since the information was not available in the course materials. "
    "Based ONLY on the web search results provided below, answer the user's question. "
    "IMPORTANT: Always start your response with: '🌐 **Information from web search** (not found in course materials)\\n\\n' "
    "Your explanation should be clear, concise, and aimed at a university student. "
    "Please find the most accurate and up-to-date web information about the following"
    "Provide accurate information based on the search results and include relevant examples if available.\n\n"
    "WEB SEARCH RESULTS:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "USER'S QUESTION: {query_str}\n\n"
    "YOUR ASSISTANT RESPONSE:"
)
agent_decision_template = PromptTemplate(
    "You are a smart routing agent that decides whether to search the web based on the quality of retrieved context. "
    "Analyze the context below and determine if it adequately answers the user's question. "
    "If the context is insufficient, incomplete, or doesn't contain relevant information, respond with 'SEARCH_WEB'. "
    "If the context is adequate to answer the question, respond with 'USE_CONTEXT'.\n\n"
    "CONTEXT:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "USER'S QUESTION: {query_str}\n\n"
    "DECISION (SEARCH_WEB or USE_CONTEXT):"
)
QUESTION_TEMPLATE = PromptTemplate(
    "You are a precise and reliable quiz generation engine. Your task is to create a single, valid multiple-choice question based ONLY on the provided context. "
    "You MUST return the output in a single, valid JSON object. Do not add any text before or after the JSON object. "
    "The JSON object must have these exact keys: 'question', 'options' (a list of 4 strings), and 'correct_answer_letter' (a string: 'A', 'B', 'C', or 'D').\n\n"
    "CONTEXT:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "Here is an example of the required output format:\n"
    "{\"question\": \"What is the primary function of a constructor in Python?\", \"options\": [\"To destroy an object\", \"To initialize the state of an object\", \"To perform a calculation\", \"To return a value\"], \"correct_answer_letter\": \"B\"}\n\n"
    "Now, generate a new, unique question based on the context provided.\n\n"
    "JSON OUTPUT:"
)
ANSWER_TEMPLATE = PromptTemplate(
    "Review the following quiz question and provide the letter of the correct option (A, B, C, or D).\nQuestion: {question}"
)
MODULE_TEMPLATE = PromptTemplate(
    "A student answered the following question incorrectly. Provide a brief, helpful explanation based on the provided context to clarify the concept.\n"
    "Question: {question}\n"
    "Context: {context_str}\n\n"
    "Explanation:"
)
UPLOADED_DOCS_TEMPLATE = PromptTemplate(
    "You are an AI assistant. Using ONLY the information from the documents provided in the context below, answer the user's question. "
    "Do not use any external knowledge. If the answer is not in the context, state that clearly.\n"
    "---------------------\n"
    "Context from Uploaded Documents:\n{context_str}\n"
    "---------------------\n"
    "Question: {query_str}\n"
    "Answer:"
)
RESEARCH_TEMPLATE = PromptTemplate(
    "You are a meticulous academic research assistant. Your task is to synthesize the provided context into a comprehensive and formal answer.\n"
    "Do not use any information outside of the context provided below.\n\n"
    "Context:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "Query: {query_str}\n\n"
    "Task: Based exclusively on the provided context, compose a detailed answer. Structure your response as follows:\n"
    "1.  Start with a concise definition or summary of the main topic.\n"
    "2.  Elaborate with key points, facts, and explanations from the text. Use bullet points for lists if appropriate.\n"
    "3.  If the context includes examples, incorporate one to illustrate your points.\n"
    "4.  Conclude with a final summary sentence.\n"
    "Maintain a formal and academic tone throughout.\n"
    "Answer:"
)

# --- Web Search Implementation ---
class WebSearchAgent:
    def __init__(self):
        self.serpapi_available = SERPAPI_AVAILABLE and SERPAPI_API_KEY
        self.requests_available = REQUESTS_AVAILABLE
        
    def search_web(self, query: str, max_results: int = MAX_WEB_RESULTS) -> List[Dict[str, Any]]:
        """Search the web using available methods"""
        if self.serpapi_available:
            return self._search_with_serpapi(query, max_results)
        elif self.requests_available:
            return self._search_with_requests(query, max_results)
        else:
            logging.error("No web search method available")
            return []
    
    def _search_with_serpapi(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using SerpAPI Google Search"""
        try:
            if not SERPAPI_API_KEY:
                logging.error("SerpAPI API key is missing")
                return []
            
            # Configure SerpAPI search parameters
            search_params = {
                "q": query,
                "engine": "google",
                "api_key": SERPAPI_API_KEY,
                "num": max_results,
                "start": 0,
                "safe": "active",
                "hl": "en",
                "gl": "us"
            }
            
            # Perform the search
            search = GoogleSearch(search_params)
            results = search.get_dict()
            
            formatted_results = []
            
            # Process organic results
            if "organic_results" in results:
                for i, result in enumerate(results["organic_results"][:max_results]):
                    formatted_results.append({
                        'title': result.get('title', 'No title'),
                        'content': result.get('snippet', 'No content'),
                        'url': result.get('link', ''),
                        'score': 1.0 - (i * 0.1),  # Decreasing score based on position
                        'published_date': result.get('date', ''),
                        'source': 'Google Search'
                    })
            
            # Also check for featured snippet or answer box
            if "answer_box" in results:
                answer_box = results["answer_box"]
                formatted_results.insert(0, {
                    'title': answer_box.get('title', 'Featured Answer'),
                    'content': answer_box.get('answer', answer_box.get('snippet', 'No content')),
                    'url': answer_box.get('link', ''),
                    'score': 1.0,
                    'published_date': '',
                    'source': 'Google Featured Answer'
                })
            
            # Check for knowledge graph information
            if "knowledge_graph" in results:
                kg = results["knowledge_graph"]
                if "description" in kg:
                    formatted_results.insert(0, {
                        'title': kg.get('title', 'Knowledge Graph'),
                        'content': kg.get('description', 'No content'),
                        'url': kg.get('website', ''),
                        'score': 0.95,
                        'published_date': '',
                        'source': 'Google Knowledge Graph'
                    })
            
            return formatted_results
            
        except Exception as e:
            logging.error(f"SerpAPI search error: {e}")
            return []
    
    def _search_with_requests(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Enhanced fallback search with multiple sources"""
        try:
            results = []
            
            # Try multiple search engines for better coverage
            search_engines = [
                {
                    'name': 'DuckDuckGo',
                    'url': 'https://html.duckduckgo.com/html/',
                    'params': {'q': query}
                },
                {
                    'name': 'Bing',
                    'url': 'https://www.bing.com/search',
                    'params': {'q': query}
                }
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            for engine in search_engines[:1]:  # Use first available engine
                try:
                    response = requests.get(
                        engine['url'], 
                        params=engine['params'], 
                        headers=headers, 
                        timeout=10
                    )
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract results based on search engine
                    if 'duckduckgo' in engine['url']:
                        search_results = soup.find_all('div', class_='result')[:max_results]
                        for result in search_results:
                            title_elem = result.find('a', class_='result__a')
                            snippet_elem = result.find('a', class_='result__snippet')
                            
                            if title_elem and snippet_elem:
                                results.append({
                                    'title': title_elem.get_text(strip=True),
                                    'content': snippet_elem.get_text(strip=True),
                                    'url': title_elem.get('href', ''),
                                    'score': 0.8,
                                    'source': engine['name']
                                })
                    
                    if results:
                        break  # Stop if we got results from first engine
                        
                except Exception as e:
                    logging.warning(f"Error with {engine['name']}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logging.error(f"Enhanced requests search error: {e}")
            return []

        
# --- CrossEncoder for Reranking ---
re_ranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_nodes(query, nodes: List[NodeWithScore], top_k=6):
    query_embedding = embedding_model.encode(query, convert_to_tensor=True)
    scored_nodes = []
    for node_obj in nodes:
        node_text = node_obj.node.get_text()
        node_text_embedding = embedding_model.encode(node_text, convert_to_tensor=True)
        score = util.cos_sim(query_embedding, node_text_embedding).item()
        scored_nodes.append((score, node_obj.node))
    ranked_nodes_with_scores = sorted(scored_nodes, key=lambda x: x[0], reverse=True)
    return [node for _, node in ranked_nodes_with_scores[:top_k]]

# --- Phase 3: MMR (Maximal Marginal Relevance) for Response Diversity ---
def mmr_rerank(query: str, nodes: List[NodeWithScore], lambda_param: float = 0.5, top_k: int = 5) -> List[NodeWithScore]:
    """
    Phase 3: Maximal Marginal Relevance reranking for response diversity

    Balances relevance and diversity to reduce redundant information in retrieved documents.
    Expected improvement: -30-40% redundant answers, better information coverage

    Args:
        query: The search query
        nodes: Retrieved nodes with scores
        lambda_param: Balance between relevance (1.0) and diversity (0.0). Default 0.5 is balanced.
        top_k: Number of nodes to return

    Returns:
        Reranked nodes with diversity consideration
    """
    if not nodes or len(nodes) <= 1:
        return nodes

    try:
        # Encode query
        query_embedding = embedding_model.encode(query, convert_to_tensor=True)

        # Encode all node texts
        node_texts = [extract_node_text(node) for node in nodes]
        node_embeddings = embedding_model.encode(node_texts, convert_to_tensor=True)

        # Calculate relevance scores (similarity to query)
        relevance_scores = util.cos_sim(query_embedding, node_embeddings)[0]

        # Initialize selected indices and remaining indices
        selected_indices = []
        remaining_indices = list(range(len(nodes)))

        # Select first document (most relevant)
        first_idx = relevance_scores.argmax().item()
        selected_indices.append(first_idx)
        remaining_indices.remove(first_idx)

        # Iteratively select documents balancing relevance and diversity
        while len(selected_indices) < min(top_k, len(nodes)) and remaining_indices:
            mmr_scores = []

            for idx in remaining_indices:
                # Relevance component
                relevance = relevance_scores[idx].item()

                # Diversity component (max similarity to already selected documents)
                if selected_indices:
                    similarities_to_selected = util.cos_sim(
                        node_embeddings[idx].unsqueeze(0),
                        node_embeddings[[s for s in selected_indices]]
                    )[0]
                    max_similarity = similarities_to_selected.max().item()
                else:
                    max_similarity = 0

                # MMR score: balance relevance and diversity
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                mmr_scores.append((idx, mmr_score))

            # Select document with highest MMR score
            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        # Return reranked nodes
        reranked_nodes = [nodes[idx] for idx in selected_indices]

        logging.info(f"MMR reranking: Selected {len(reranked_nodes)} diverse nodes from {len(nodes)} candidates")
        return reranked_nodes

    except Exception as e:
        logging.error(f"Error in MMR reranking: {e}, returning original nodes")
        return nodes[:top_k]

# --- Phase 3: Parent Context Retrieval ---
def get_parent_context(node: NodeWithScore) -> str:
    """
    Phase 3: Retrieve parent context for child chunks

    If node has parent_text metadata (from recursive chunking), return the full parent
    context instead of just the child chunk. This provides broader context to the LLM.

    Expected improvement: +10-20% answer completeness
    """
    try:
        if hasattr(node, 'metadata') and 'parent_text' in node.metadata:
            parent_text = node.metadata['parent_text']
            logging.debug(f"Using parent context ({len(parent_text)} chars) instead of child ({len(node.text)} chars)")
            return parent_text
        elif hasattr(node, 'node') and hasattr(node.node, 'metadata') and 'parent_text' in node.node.metadata:
            parent_text = node.node.metadata['parent_text']
            logging.debug(f"Using parent context ({len(parent_text)} chars) instead of child ({len(node.node.text)} chars)")
            return parent_text
        else:
            # No parent context available, use node text directly
            return extract_node_text(node)
    except Exception as e:
        logging.error(f"Error retrieving parent context: {e}")
        return extract_node_text(node)

def get_hybrid_retriever(index, documents: List[Document], similarity_top_k=6, rerank_top_k=5):
    dense_retriever = index.as_retriever(similarity_top_k=similarity_top_k)
    sparse_retriever = BM25Retriever.from_defaults(index, similarity_top_k=similarity_top_k)
    MIN_SCORE = 0.20

    class HybridRetriever(BaseRetriever):
        def _retrieve(self, query_str: str) -> List[NodeWithScore]:
            dense_results_with_scores = dense_retriever.retrieve(query_str)
            sparse_results_with_scores = sparse_retriever.retrieve(query_str)
            combined_nodes_map = {}
            for r_node_ws in dense_results_with_scores + sparse_results_with_scores:
                node = r_node_ws.node
                if node.node_id not in combined_nodes_map:
                    combined_nodes_map[node.node_id] = node
            combined_unique_nodes = list(combined_nodes_map.values())
            if not combined_unique_nodes:
                return []
            query_text = query_str.query_str if hasattr(query_str, "query_str") else query_str
            pairs = [(query_text, extract_node_text(node)) for node in combined_unique_nodes]
            if not pairs:
                return [NodeWithScore(node=n, score=0.0) for n in combined_unique_nodes[:1]]
            try:
                cross_scores = re_ranker.predict(pairs)
                scored_nodes_for_final_ranking = [
                    NodeWithScore(node=node, score=float(score))
                    for node, score in zip(combined_unique_nodes, cross_scores)
                ]
                reranked_final_nodes_with_scores = sorted(
                    scored_nodes_for_final_ranking,
                    key=lambda x: x.score if x.score is not None else -1.0,
                    reverse=True,
                )
                # Filter by minimum score
                final_nodes = [x for x in reranked_final_nodes_with_scores if x.score >= MIN_SCORE]
                if not final_nodes:
                    final_nodes = reranked_final_nodes_with_scores[:1]  # fallback: best one
                return final_nodes
            except Exception as e:
                logging.error(f"Error in cross-encoder reranking: {e}")
                return [NodeWithScore(node=n, score=0.0) for n in combined_unique_nodes[:1]]
    return HybridRetriever()


def extract_node_text(node_or_item):
    try:
        if hasattr(node_or_item, 'node'):
            actual_node = node_or_item.node
        else:
            actual_node = node_or_item
        if hasattr(actual_node, 'get_content'):
            return actual_node.get_content()
        elif hasattr(actual_node, 'get_text'):
            return actual_node.get_text()
        elif hasattr(actual_node, 'text'):
            return actual_node.text
        elif isinstance(actual_node, str):
            return actual_node
        else:
            logging.warning(f"Unknown node type: {type(actual_node)}")
            return str(actual_node)
    except Exception as e:
        logging.error(f"Error extracting text from node: {e}")
        return ""
    
class RAGQueryEngine(CustomQueryEngine):
    retriever: BaseRetriever
    response_synthesizer: BaseSynthesizer
    mode: str = "chat"
    web_search_agent: Optional[WebSearchAgent] = None

    def __init__(self, retriever: BaseRetriever, response_synthesizer: BaseSynthesizer, mode: str = "chat", **kwargs):
        init_data = {
            "retriever": retriever,
            "response_synthesizer": response_synthesizer,
            "mode": mode,
            **kwargs
        }
        super().__init__(**init_data)
        self.retriever = retriever
        self.response_synthesizer = response_synthesizer
        self.mode = mode
        self.web_search_agent = WebSearchAgent() if WEB_SEARCH_ENABLED else None

    def _rewrite_query(self, query_str: str) -> str:
        """
        Phase 2 improvement: Query rewriting for optimization
        Rewrites ambiguous or poorly-formed queries into clearer versions
        Expected improvement: +22 points NDCG@3 (Microsoft Azure AI 2025)
        """
        try:
            # Try to load config settings
            try:
                from backend.config import config
                rewriting_enabled = config.QUERY_REWRITING_ENABLED
            except:
                rewriting_enabled = True

            if not rewriting_enabled:
                return query_str

            # Skip rewriting for very short queries (likely already clear)
            if len(query_str.split()) <= 3:
                return query_str

            rewrite_prompt = (
                "You are an expert at optimizing search queries for educational content retrieval. "
                "Your task is to rewrite the user's query to make it more effective for semantic search.\n\n"
                "Guidelines:\n"
                "1. Expand acronyms and abbreviations if context allows\n"
                "2. Make implicit questions explicit (e.g., 'Python loops' -> 'What are loops in Python?')\n"
                "3. Clarify ambiguous terms\n"
                "4. Keep technical terminology intact\n"
                "5. Maintain the original intent\n"
                "6. Make it a complete, well-formed question if possible\n\n"
                f"Original query: {query_str}\n\n"
                "Return ONLY the rewritten query, nothing else.\n"
                "Rewritten query:"
            )

            response = Settings.llm.complete(rewrite_prompt)
            rewritten = str(response).strip()

            # Sanity check: don't use rewrite if it's too different or too long
            if len(rewritten) > len(query_str) * 3 or len(rewritten) < 3:
                logging.warning(f"Query rewrite rejected (length check failed): '{rewritten}'")
                return query_str

            logging.info(f"Query rewritten: '{query_str}' -> '{rewritten}'")
            return rewritten

        except Exception as e:
            logging.warning(f"Query rewriting failed: {e}, using original query")
            return query_str

    def _expand_query(self, query_str: str, num_variations: int = 3) -> List[str]:
        """
        Phase 1 improvement: Query expansion to improve retrieval recall
        Generates multiple query variations to capture different phrasings
        Expected improvement: +8-15% recall
        """
        try:
            # Try to load config settings, fallback to defaults
            try:
                from backend.config import config
                expansion_enabled = config.QUERY_EXPANSION_ENABLED
                num_variations = config.QUERY_EXPANSION_NUM
            except:
                expansion_enabled = True
                num_variations = 3

            if not expansion_enabled:
                return [query_str]

            expansion_prompt = (
                f"Given the following question, generate {num_variations} alternative phrasings "
                f"that preserve the original meaning but use different words or sentence structures. "
                f"This is for improving search recall in an educational context.\n\n"
                f"Original question: {query_str}\n\n"
                f"Return ONLY the {num_variations} alternative questions, one per line, without numbering or extra text.\n"
                f"Alternative questions:"
            )

            response = Settings.llm.complete(expansion_prompt)
            variations = str(response).strip().split('\n')

            # Clean up variations and add original query
            variations = [v.strip() for v in variations if v.strip()]
            variations = [v.lstrip('0123456789.-) ') for v in variations]  # Remove numbering if any

            # Limit to requested number and add original
            all_queries = [query_str] + variations[:num_variations-1]

            logging.info(f"Query expansion generated {len(all_queries)} variations")
            return all_queries

        except Exception as e:
            logging.warning(f"Query expansion failed: {e}, using original query only")
            return [query_str]

    def _retrieve_with_expanded_queries(self, query_str: str) -> List[NodeWithScore]:
        """
        Retrieve using query rewriting + expansion and deduplicate results
        Phase 2: Added query rewriting before expansion
        Phase 3: Added MMR reranking for diversity
        """
        # Phase 2: First rewrite the query for optimization
        rewritten_query = self._rewrite_query(query_str)

        # Then expand the rewritten query into variations
        query_variations = self._expand_query(rewritten_query)

        all_nodes = []
        seen_node_ids = set()

        for query_variant in query_variations:
            try:
                retrieved_items = self.retriever.retrieve(query_variant)
                for item in retrieved_items:
                    # Deduplicate by node ID
                    node_id = item.node.node_id if hasattr(item.node, 'node_id') else id(item.node)
                    if node_id not in seen_node_ids:
                        all_nodes.append(item)
                        seen_node_ids.add(node_id)
            except Exception as e:
                logging.warning(f"Retrieval failed for query variant '{query_variant}': {e}")
                continue

        # Sort by score (higher is better) and take top results
        all_nodes.sort(key=lambda x: x.score if hasattr(x, 'score') and x.score is not None else 0, reverse=True)

        # Phase 3: Apply MMR reranking for diversity if enabled
        try:
            from backend.config import config
            mmr_enabled = config.MMR_ENABLED
            mmr_lambda = config.MMR_DIVERSITY_LAMBDA
            mmr_fetch_k = config.MMR_FETCH_K
            final_top_k = config.SIMILARITY_TOP_K
        except:
            mmr_enabled = True
            mmr_lambda = 0.5
            mmr_fetch_k = 10
            final_top_k = 5

        if mmr_enabled and len(all_nodes) > 1:
            # Fetch more candidates for MMR to choose from
            candidate_nodes = all_nodes[:mmr_fetch_k]
            # Apply MMR reranking to balance relevance and diversity
            all_nodes = mmr_rerank(rewritten_query, candidate_nodes, lambda_param=mmr_lambda, top_k=final_top_k)
            logging.info(f"Applied MMR reranking with lambda={mmr_lambda}")
        else:
            # Limit to reasonable number of results without MMR
            max_results = 10  # Configurable
            all_nodes = all_nodes[:max_results]

        return all_nodes

    def _self_rag_reflection(self, query_str: str, retrieved_nodes: List[NodeWithScore]) -> Dict[str, Any]:
        """
        Phase 2: Self-RAG reflection mechanism
        Evaluates retrieval quality and provides confidence scores
        Expected improvement: -52% hallucinations (2025 research)
        """
        try:
            # Try to load config
            try:
                from backend.config import config
                self_rag_enabled = config.SELF_RAG_ENABLED
            except:
                self_rag_enabled = True

            if not self_rag_enabled or not retrieved_nodes:
                return {
                    "should_retrieve": True,
                    "relevance_score": 0.5,
                    "should_continue": True,
                    "confidence": "medium"
                }

            # Extract context from nodes
            context_parts = [extract_node_text(node) for node in retrieved_nodes[:3]]
            context_str = "\n\n".join(filter(None, context_parts))

            # Self-RAG reflection prompt
            reflection_prompt = (
                "You are a quality assessor for information retrieval. Evaluate the retrieved context for the given query.\n\n"
                f"Query: {query_str}\n\n"
                f"Retrieved Context:\n{context_str[:1000]}...\n\n"  # Limit context length
                "Evaluate the following:\n"
                "1. RELEVANCE: Is this context relevant to answering the query? (YES/NO)\n"
                "2. COMPLETENESS: Does it contain enough information to answer? (YES/NO)\n"
                "3. CONFIDENCE: How confident are you that this context can answer the query? (HIGH/MEDIUM/LOW)\n\n"
                "Respond ONLY in this exact format:\n"
                "RELEVANCE: [YES/NO]\n"
                "COMPLETENESS: [YES/NO]\n"
                "CONFIDENCE: [HIGH/MEDIUM/LOW]"
            )

            response = Settings.llm.complete(reflection_prompt)
            response_text = str(response).strip().upper()

            # Parse reflection response
            relevance = "YES" in response_text and "RELEVANCE: YES" in response_text
            completeness = "YES" in response_text and "COMPLETENESS: YES" in response_text

            # Determine confidence level
            if "CONFIDENCE: HIGH" in response_text:
                confidence = "high"
                confidence_score = 0.9
            elif "CONFIDENCE: LOW" in response_text:
                confidence = "low"
                confidence_score = 0.3
            else:
                confidence = "medium"
                confidence_score = 0.6

            # Calculate average retrieval score
            avg_retrieval_score = sum(
                getattr(node, 'score', 0) for node in retrieved_nodes
            ) / max(len(retrieved_nodes), 1)

            # Final relevance score combines LLM assessment and retrieval scores
            final_relevance = (
                (0.4 * (1.0 if relevance else 0.0)) +
                (0.3 * (1.0 if completeness else 0.0)) +
                (0.3 * avg_retrieval_score)
            )

            result = {
                "should_retrieve": relevance,
                "relevance_score": round(final_relevance, 3),
                "completeness": completeness,
                "confidence": confidence,
                "confidence_score": round(confidence_score, 3),
                "should_continue": relevance and completeness,
                "avg_retrieval_score": round(avg_retrieval_score, 3)
            }

            logging.info(f"Self-RAG reflection: {result}")
            return result

        except Exception as e:
            logging.warning(f"Self-RAG reflection failed: {e}, using default scores")
            return {
                "should_retrieve": True,
                "relevance_score": 0.5,
                "should_continue": True,
                "confidence": "medium"
            }

    def _should_search_web(self, query_str: str, context_str: str, reflection_result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Phase 2 Enhanced CRAG: Corrective RAG with formal quality scoring
        Determines if web search is needed based on retrieval quality assessment
        """
        if not self.web_search_agent or not WEB_SEARCH_ENABLED:
            return False

        # Try to load config
        try:
            from backend.config import config
            crag_threshold = config.CRAG_QUALITY_THRESHOLD
        except:
            crag_threshold = 0.5  # Default threshold

        # Phase 2: Use Self-RAG reflection results if available
        if reflection_result:
            relevance_score = reflection_result.get("relevance_score", 0.5)
            confidence = reflection_result.get("confidence", "medium")
            completeness = reflection_result.get("completeness", True)

            # Trigger web search if quality is below threshold
            if relevance_score < crag_threshold:
                logging.info(f"CRAG: Triggering web search (relevance={relevance_score:.3f} < {crag_threshold})")
                return True

            if confidence == "low":
                logging.info("CRAG: Triggering web search (low confidence)")
                return True

            if not completeness:
                logging.info("CRAG: Triggering web search (incomplete context)")
                return True

            logging.info(f"CRAG: Using local context (relevance={relevance_score:.3f}, confidence={confidence})")
            return False

        # Fallback to original heuristics if no reflection
        if not context_str or len(context_str.strip()) < 50:
            return True

        # Use LLM to make decision (legacy path)
        try:
            decision_prompt = agent_decision_template.format(
                context_str=context_str,
                query_str=query_str
            )
            decision_response = Settings.llm.complete(decision_prompt)
            decision = str(decision_response).strip().upper()
            return "SEARCH_WEB" in decision
        except Exception as e:
            logging.error(f"Error in web search decision: {e}")
            return len(context_str.strip()) < 100  # Fallback heuristic

    def _search_and_format_web_results(self, query_str: str) -> str:
        """Search web and format results for LLM"""
        if not self.web_search_agent:
            return ""
        
        try:
            search_results = self.web_search_agent.search_web(query_str, MAX_WEB_RESULTS)
            if not search_results:
                return ""
            
            formatted_context = []
            for i, result in enumerate(search_results, 1):
                formatted_context.append(
                    f"Source {i}: {result['title']}\n"
                    f"URL: {result['url']}\n"
                    f"Content: {result['content']}\n"
                    f"Source Type: {result.get('source', 'Web Search')}\n"
                )
            
            return "\n\n".join(formatted_context)
        except Exception as e:
            logging.error(f"Error in web search: {e}")
            return ""

    def custom_query(self, query_str: str, doc: Optional[Document] = None, forced_context_str: Optional[str] = None) -> str:
        # Phase 1: Track metrics for evaluation
        retrieval_start = time.time()
        generation_start = None

        current_template = None
        if self.mode == "quiz":
            current_template = QUESTION_TEMPLATE
        elif self.mode == "research":
            current_template = RESEARCH_TEMPLATE
        elif self.mode == "uploaded_doc" and doc:
            current_template = UPLOADED_DOCS_TEMPLATE
        else:
            current_template = qa_template

        nodes_for_synthesis = []
        context_str_for_prompt = ""
        used_web_search = False
        reflection_result = None  # Phase 2: Store reflection results

        try:
            if forced_context_str is not None:
                context_str_for_prompt = forced_context_str
            elif self.mode == "uploaded_doc" and doc:
                temp_index = VectorStoreIndex.from_documents([doc])
                doc_retriever = temp_index.as_retriever(similarity_top_k=3)
                retrieved_items = doc_retriever.retrieve(query_str)
                if not retrieved_items:
                    return "I'm sorry, I couldn't find relevant information in the uploaded document for your query."
                context_parts = [extract_node_text(item) for item in retrieved_items]
                context_str_for_prompt = "\n\n".join(filter(None, context_parts))
                nodes_for_synthesis = retrieved_items 
            else:
                # Phase 1 & 2 & 3: Use query rewriting + expansion + MMR for improved retrieval
                retrieved_items = self._retrieve_with_expanded_queries(query_str)

                # Phase 3: Use parent context if available (from recursive chunking)
                context_parts = [get_parent_context(item) for item in retrieved_items]
                context_str_for_prompt = "\n\n".join(filter(None, context_parts))
                nodes_for_synthesis = retrieved_items

                # Phase 2: Self-RAG reflection to assess retrieval quality
                reflection_result = self._self_rag_reflection(query_str, retrieved_items)

                # Phase 2 Enhanced CRAG: Check if we should search the web using reflection results
                if self._should_search_web(query_str, context_str_for_prompt, reflection_result):
                    logging.info(f"Searching web for query: {query_str}")
                    web_context = self._search_and_format_web_results(query_str)
                    if web_context:
                        context_str_for_prompt = web_context
                        current_template = web_search_template
                        used_web_search = True
                        logging.info("Using web search results")
                    else:
                        logging.warning("Web search failed, using local context")

            # Track retrieval time
            retrieval_time = time.time() - retrieval_start

            print("--------CONTEXT PASSED TO LLM--------")
            print(f"Web search used: {used_web_search}")
            print(context_str_for_prompt)
            print("--------------------------------------")

            if self.mode == "quiz" and (not context_str_for_prompt or len(context_str_for_prompt) < 30):
                if not forced_context_str:
                    logging.warning(f"Warning: Context for quiz question generation is short or empty. Query: '{query_str}'")
                if not context_str_for_prompt.strip() and self.mode == "quiz":
                    logging.error("Cannot generate quiz question: Context is empty.")
                    return json.dumps({"error": "Context is empty, cannot generate question."})

            # Track generation time
            generation_start = time.time()
            final_prompt_for_llm = current_template.format(context_str=context_str_for_prompt, query_str=query_str)
            response_obj = self.response_synthesizer.synthesize(query=final_prompt_for_llm, nodes=nodes_for_synthesis)
            generation_time = time.time() - generation_start

            response_text = str(response_obj).strip()

            # Add metadata about source
            if used_web_search and not response_text.startswith("🌐"):
                response_text = f"🌐 **Information from web search** (not found in course materials)\n\n{response_text}"

            # Phase 1: Log evaluation metrics
            if EVALUATION_ENABLED:
                try:
                    evaluator = get_evaluator()
                    evaluator.log_query(
                        query=query_str,
                        retrieved_docs=nodes_for_synthesis,
                        response=response_text,
                        retrieval_time=retrieval_time,
                        generation_time=generation_time,
                        metadata={
                            "mode": self.mode,
                            "web_search_used": used_web_search,
                            "num_context_chars": len(context_str_for_prompt),
                            # Phase 2: Include reflection results
                            "reflection": reflection_result if reflection_result else {}
                        }
                    )
                except Exception as e:
                    logging.warning(f"Failed to log evaluation metrics: {e}")

            return response_text
            
        except Exception as e:
            logging.error(f"Error in custom_query: {e}")
            if self.mode == "quiz":
                return json.dumps({"error": f"Failed to generate question: {str(e)}"})
            return f"Error processing query: {str(e)}"

    def get_correct_answer(self, question: str) -> str:
        try:
            retrieved_items = self.retriever.retrieve(question)
            formatted_prompt = ANSWER_TEMPLATE.format(question=question)
            response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=retrieved_items)
            return str(response_obj).strip()
        except Exception as e:
            logging.error(f"Error in get_correct_answer: {e}")
            return f"Error: {str(e)}"

    def get_related_module(self, question: str) -> str:
        try:
            retrieved_items = self.retriever.retrieve(question)
            context_parts = [extract_node_text(item) for item in retrieved_items]
            context_str = "\n\n".join(filter(None, context_parts))
            formatted_prompt = MODULE_TEMPLATE.format(question=question, context_str=context_str)
            response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=retrieved_items)
            return str(response_obj).strip()
        except Exception as e:
            logging.error(f"Error in get_related_module: {e}")
            return f"Error: {str(e)}"

    def query_uploaded_docs(self, query_str: str, doc: Document) -> str:
        try:
            index = VectorStoreIndex.from_documents([doc])
            retriever = index.as_retriever(similarity_top_k=3)
            nodes = retriever.retrieve(query_str)
            if not nodes:
                return "I'm sorry, I couldn't find an answer based on the uploaded document."
            context_parts = [extract_node_text(node) for node in nodes]
            context_str = "\n".join(filter(None, context_parts))
            if not context_str.strip():
                return "I'm sorry, I couldn't extract meaningful content from the uploaded document."
            formatted_prompt = UPLOADED_DOCS_TEMPLATE.format(context_str=context_str, query_str=query_str)
            synthesizer_for_upload = get_response_synthesizer(response_mode="compact")
            return str(synthesizer_for_upload.synthesize(query=formatted_prompt, nodes=nodes)).strip()
        except Exception as e:
            logging.error(f"Error in query_uploaded_docs: {e}")
            return f"Error processing uploaded document: {str(e)}"

def chat():
    print("Welcome to Smart AI Tutor with Web Search! Type 'exit' to quit the chat.")
    if WEB_SEARCH_ENABLED:
        print("🌐 Web search is enabled - I'll search the internet when information isn't available locally.")
    else:
        print(" Using local knowledge base only.")
    
    try:
        cli_storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        index = load_index_from_storage(cli_storage_context)
        print("Index loaded successfully for CLI chat.")
        documents_from_index = list(index.docstore.docs.values()) 
    except Exception as e:
        print(f"Error loading index for CLI chat: {e}")
        return
    
    retriever = get_hybrid_retriever(index, documents_from_index) 
    synthesizer = get_response_synthesizer(response_mode="compact")
    query_engine = RAGQueryEngine(retriever=retriever, response_synthesizer=synthesizer, mode="chat")
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        if not user_input.strip(): 
            continue
        print("AI Tutor is thinking...")
        try:
            response = query_engine.custom_query(user_input)
            print("Assistant:", response)
        except Exception as e:
            print(f"Error: {e}")

def main():
    args = parse_args()
    def run_ingestion(data_path): 
        print(f"CLI: Ingestion called for data at: {data_path}. (Not implemented)")
    def run_query(query_text): 
        print(f"CLI: Query called with: '{query_text}'. (Not implemented)")
    if args.command == 'ingest': 
        run_ingestion(args.data_path)
    elif args.command == 'query': 
        run_query(args.query_text)
    elif args.command == 'chat': 
        chat()
    else: 
        print("Invalid command. Use -h or --help for available commands.")

if __name__ == '__main__':
    main()