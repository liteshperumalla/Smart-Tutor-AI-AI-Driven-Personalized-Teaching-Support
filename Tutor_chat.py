import os
import json
import argparse
import logging
from typing import Optional, List

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
from langfuse.llama_index import LlamaIndexCallbackHandler

# --- Langfuse Setup ---
langfuse_callback_handler = None
langfuse_client = None

try:
    # Attempt to load Langfuse keys from environment variables
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com") # Default host if not set

    if langfuse_public_key and langfuse_secret_key:
        langfuse_callback_handler = LlamaIndexCallbackHandler(
            public_key=langfuse_public_key,
            secret_key=langfuse_secret_key,
            host=langfuse_host
        )
        Settings.callback_manager = CallbackManager([langfuse_callback_handler])
        logging.info("Langfuse callback handler initialized successfully using environment variables.")
    else:
        logging.warning("Langfuse environment variables (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY) not fully set. Langfuse LlamaIndex callback handler will not be initialized.")
        langfuse_callback_handler = None
except ImportError:
    logging.error("Failed to import LlamaIndexCallbackHandler. Please check Langfuse SDK version. Langfuse integration disabled.")
    langfuse_callback_handler = None
except Exception as e:
    logging.error(f"Failed to initialize Langfuse callback handler using environment variables: {e}. Langfuse integration disabled.")
    logging.error(f"Failed to initialize Langfuse callback handler using environment variables: {e}. Langfuse integration disabled.")
    langfuse_callback_handler = None

try:
    # Langfuse client will also use environment variables if public_key/secret_key are not explicitly passed
    langfuse_client = Langfuse() 
    logging.info("Langfuse client initialized (will use environment variables if LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST are set).")
except Exception as e:
    logging.error(f"Failed to initialize Langfuse client: {e}. Tracing might be partially or fully disabled. Ensure environment variables are set if not passing keys directly.")
    langfuse_client = None 

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
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
# --- Constants ---
DEFAULT_MIN_SCORE_FOR_HYBRID_RETRIEVAL = 0.20
Settings.llm = Ollama(model="llama3.2:latest", request_timeout=120.0)

# --- Directories ---
persist_dir = os.getenv("PERSIST_DIR", "./persisted_index")
os.makedirs(persist_dir, exist_ok=True)

# --- Prompt Templates ---
QUESTION_TEMPLATE = PromptTemplate(
    "You are a precise quiz question generation engine. Based ONLY on the provided context, "
    "generate a single, clear, and concise question that can be answered from the context. "
    "Do NOT generate options or the answer. Only the question text itself.\n\n"
    "CONTEXT:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "QUESTION:"
)

OPTIONS_GENERATION_TEMPLATE = PromptTemplate(
    "You are a helpful assistant. For the following question, generate exactly four plausible multiple-choice options (A, B, C, D). "
    "Ensure one option is clearly correct based on typical knowledge or the provided context (if any). "
    "Return the options as a JSON list of four strings. For example: "
    "[\"Option A text\", \"Option B text\", \"Option C text\", \"Option D text\"]\n\n"
    "CONTEXT (Optional, use if provided to ensure relevance):\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "QUESTION:\n{question_str}\n\n"
    "JSON LIST OF FOUR OPTIONS:"
)

CORRECT_ANSWER_IDENTIFICATION_TEMPLATE = PromptTemplate(
    "You are an expert validator. Given the following question and its four multiple-choice options (A, B, C, D), "
    "identify which single option is the correct answer. Respond with only the letter of the correct option (e.g., 'A', 'B', 'C', or 'D').\n\n"
    "CONTEXT (Optional, use if provided to help validate):\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "QUESTION:\n{question_str}\n\n"
    "OPTIONS:\n"
    "A) {option_a}\n"
    "B) {option_b}\n"
    "C) {option_c}\n"
    "D) {option_d}\n\n"
    "CORRECT OPTION LETTER (A, B, C, or D):"
)

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
# The duplicated/old QUESTION_TEMPLATE that was here has been removed.
# The correct QUESTION_TEMPLATE (for generating only question text) is defined earlier.
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

# --- CrossEncoder for Reranking ---
re_ranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# Restored rerank_nodes function
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

def get_hybrid_retriever(index, similarity_top_k=6):
    dense_retriever = index.as_retriever(similarity_top_k=similarity_top_k)
    sparse_retriever = BM25Retriever.from_defaults(index, similarity_top_k=similarity_top_k)

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
                final_nodes = [x for x in reranked_final_nodes_with_scores if x.score >= DEFAULT_MIN_SCORE_FOR_HYBRID_RETRIEVAL]
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

    def custom_query(self, query_str: str, doc: Optional[Document] = None, forced_context_str: Optional[str] = None): # Return type changed for quiz mode
        current_template = None # Will be set based on mode

        if self.mode == "quiz":
            # 0. Initial query_str for quiz mode is generic, e.g., "Generate a quiz question"
            #    It's mainly used here to retrieve relevant context.

            # 1. Retrieve and Rerank Nodes
            # query_str here is the generic prompt for fetching context (e.g. "some topic for a quiz")
            retrieved_items_for_context = self.retriever.retrieve(query_str)
            # rerank_nodes returns List[TextNode], not NodeWithScore
            reranked_nodes_for_context = rerank_nodes(query_str, retrieved_items_for_context)

            context_str_for_prompt = "\n\n".join(
                # extract_node_text can handle TextNode directly
                [extract_node_text(node) for node in reranked_nodes_for_context]
            )

            if not context_str_for_prompt.strip():
                logging.error("Quiz Mode: Context is empty after retrieval and reranking. Cannot generate question.")
                return {"error": "Context is empty, cannot generate question."}

            # 2. Generate Question Text (Step 1)
            question_generation_prompt = QUESTION_TEMPLATE.format(context_str=context_str_for_prompt)
            # Pass reranked_nodes_for_context as nodes for synthesis if the synthesizer uses them
            question_response_obj = self.response_synthesizer.synthesize(query=question_generation_prompt, nodes=reranked_nodes_for_context)
            question_text = str(question_response_obj).strip()

            if not question_text:
                logging.error("Quiz Mode: LLM failed to generate question text.")
                return {"error": "Failed to generate question text."}

            # 3. Generate Options (Step 2)
            options_generation_prompt = OPTIONS_GENERATION_TEMPLATE.format(
                question_str=question_text,
                context_str=context_str_for_prompt
            )
            # Nodes (reranked_nodes_for_context) could be passed again if useful for option generation context
            options_response_obj = self.response_synthesizer.synthesize(query=options_generation_prompt, nodes=reranked_nodes_for_context)
            options_json_str = str(options_response_obj).strip()

            generated_options = []
            try:
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', options_json_str, re.DOTALL)
                if json_match:
                    options_json_str = json_match.group(1).strip()

                if options_json_str.startswith("[") and options_json_str.endswith("]"):
                    generated_options = json.loads(options_json_str)
                    if not (isinstance(generated_options, list) and len(generated_options) == 4 and all(isinstance(opt, str) for opt in generated_options)):
                        logging.error(f"Quiz Mode: LLM generated malformed options list: {generated_options}")
                        return {"error": "LLM generated malformed options list."}
                else:
                    # Sometimes LLM might return options as separate lines without JSON structure,
                    # or just plain text. This is a fallback attempt for simple non-JSON list.
                    # Example: "A) Option 1\nB) Option 2\nC) Option 3\nD) Option 4"
                    # This part is heuristic and might need refinement based on LLM behavior.
                    potential_options = [line.strip() for line in options_json_str.split('\n') if line.strip()]
                    if len(potential_options) == 4: # Check if we got 4 lines
                         # Basic cleaning: remove "A)", "B)" prefixes if they exist
                        cleaned_options = []
                        for opt_line in potential_options:
                            # Regex to remove common prefixes like "A)", "A.", "1." etc.
                            cleaned_opt = re.sub(r"^[A-Da-d1-4][\).\s]+", "", opt_line).strip()
                            cleaned_options.append(cleaned_opt)

                        if all(isinstance(opt, str) and opt for opt in cleaned_options): # Ensure all are non-empty strings
                            generated_options = cleaned_options
                            logging.info(f"Quiz Mode: Parsed options from non-JSON list: {generated_options}")
                        else:
                            logging.error(f"Quiz Mode: LLM response for options was not a valid JSON list or parsable format: {options_json_str}")
                            return {"error": "LLM response for options was not a valid JSON list or parsable format."}
                    else:
                        logging.error(f"Quiz Mode: LLM response for options was not a valid JSON list or parsable format: {options_json_str}")
                        return {"error": "LLM response for options was not a valid JSON list or parsable format."}


            except json.JSONDecodeError as e:
                # This block will be hit if it's not ```json...``` and not a simple list either.
                logging.error(f"Quiz Mode: Failed to parse JSON for options: {e}. Response: {options_json_str}")
                return {"error": f"Failed to parse JSON for options: {options_json_str}"}

            # 4. Return Structure
            return {
                "question_text": question_text,
                "generated_options": generated_options,
                "context_used": context_str_for_prompt
            }

        elif self.mode == "research":
            current_template = RESEARCH_TEMPLATE
        elif self.mode == "uploaded_doc" and doc:
            current_template = UPLOADED_DOCS_TEMPLATE
        else:
            current_template = qa_template

        nodes_for_synthesis = []
        context_str_for_prompt = ""
        try:
            if forced_context_str is not None:
                context_str_for_prompt = forced_context_str
                # No retrieval, so no nodes to rerank or pass, unless forced_context is from nodes.
                # Assuming forced_context_str means no node-based synthesis or very specific nodes passed by caller.
                # If nodes are relevant here, the caller of custom_query with forced_context_str should handle it.
                nodes_for_synthesis = [] # Or caller needs to provide nodes if synthesizer needs them
            elif self.mode == "uploaded_doc" and doc: # Specific handling for a single uploaded document
                temp_index = VectorStoreIndex.from_documents([doc])
                # Increase similarity_top_k to provide more nodes for reranking from the single doc
                doc_retriever = temp_index.as_retriever(similarity_top_k=5)
                initial_retrieved_items = doc_retriever.retrieve(query_str) # These are NodeWithScore

                if not initial_retrieved_items:
                    return "I'm sorry, I couldn't find relevant information in the uploaded document for your query."

                reranked_item_nodes = rerank_nodes(query_str, initial_retrieved_items, top_k=3) # rerank_nodes returns List[Node]

                context_parts = [extract_node_text(item_node) for item_node in reranked_item_nodes]
                context_str_for_prompt = "\n\n".join(filter(None, context_parts))
                nodes_for_synthesis = reranked_item_nodes

                if not context_str_for_prompt.strip() and initial_retrieved_items:
                    logging.warning(f"Mode '{self.mode}': Context is empty after reranking for query: '{query_str}' (uploaded doc). Falling back to initial context.")
                    context_parts = [extract_node_text(item.node) for item in initial_retrieved_items]
                    context_str_for_prompt = "\n\n".join(filter(None, context_parts))
                    nodes_for_synthesis = [item.node for item in initial_retrieved_items[:3]]

            else: # Handles 'chat', 'research', or 'uploaded_doc' if 'doc' object not directly passed and no forced_context
                initial_retrieved_items = self.retriever.retrieve(query_str) # These are NodeWithScore
                if not initial_retrieved_items:
                    logging.warning(f"Mode '{self.mode}': No items retrieved for query: '{query_str}'. Context will be empty.")
                    return "I couldn't find any information relevant to your query at this moment."

                reranked_item_nodes = rerank_nodes(query_str, initial_retrieved_items) # rerank_nodes returns List[Node]

                context_parts = [extract_node_text(item_node) for item_node in reranked_item_nodes]
                context_str_for_prompt = "\n\n".join(filter(None, context_parts))
                nodes_for_synthesis = reranked_item_nodes

            print(f"--------CONTEXT PASSED TO LLM (mode: {self.mode}, after rerank_nodes if applicable)--------")
            print(context_str_for_prompt)
            print("---------------------------------------------------------------------------------------")

            if not context_str_for_prompt.strip() and self.mode != "quiz":
                logging.warning(f"Mode '{self.mode}': Context is empty for query: '{query_str}'. LLM might not be able to answer effectively.")

            final_prompt_for_llm = current_template.format(context_str=context_str_for_prompt, query_str=query_str)
            response_obj = self.response_synthesizer.synthesize(query=final_prompt_for_llm, nodes=nodes_for_synthesis)
            return str(response_obj).strip()
        except Exception as e:
            # Error handling for non-quiz modes, or general errors if quiz mode failed before its own try-excepts
            logging.error(f"Error in custom_query (mode: {self.mode}): {e}", exc_info=True)
            # For quiz mode, errors should ideally be caught and returned as dicts within its specific block.
            # If an error happens outside that for quiz mode, this is a fallback.
            if self.mode == "quiz":
                 return {"error": f"An unexpected error occurred in quiz mode: {str(e)}"}
            return f"Error processing query: {str(e)}"

    def get_correct_answer(self, question_str: str, generated_options: List[str], context_str: str) -> str:
        """
        Identifies the correct answer letter from a list of generated options for a given question,
        using an LLM call.
        """
        if not (isinstance(generated_options, list) and len(generated_options) == 4 and all(isinstance(opt, str) for opt in generated_options)):
            logging.error("get_correct_answer: Must provide a list of 4 string options.")
            return "" # Or raise an error

        # Format options for the prompt
        option_a, option_b, option_c, option_d = generated_options

        identification_prompt = CORRECT_ANSWER_IDENTIFICATION_TEMPLATE.format(
            question_str=question_str,
            context_str=context_str, # Context used for question generation
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d
        )

        # Assuming the prompt is self-contained with all necessary information (question, options, context).
        # Passing an empty list for nodes as the synthesizer might not need explicit nodes if the query prompt is complete.
        try:
            response_obj = self.response_synthesizer.synthesize(query=identification_prompt, nodes=[])
            correct_letter = str(response_obj).strip().upper()

            if correct_letter in ["A", "B", "C", "D"]:
                return correct_letter
            else:
                # Attempt to extract the letter if it's embedded, e.g., "The correct answer is A."
                match = re.search(r'\b([A-D])\b', correct_letter)
                if match:
                    extracted_letter = match.group(1)
                    logging.warning(f"get_correct_answer: LLM returned '{correct_letter}', extracted valid letter '{extracted_letter}'.")
                    return extracted_letter

                logging.warning(f"get_correct_answer: LLM returned an invalid or non-letter response: '{correct_letter}'.")
                return "" # Indicates failure to identify a valid letter
        except Exception as e:
            logging.error(f"get_correct_answer: Error during LLM call for answer identification: {e}", exc_info=True)
            return ""


    def get_related_module(self, question: str) -> str:
        try:
            initial_retrieved_items = self.retriever.retrieve(question) # These are NodeWithScore
            if not initial_retrieved_items:
                logging.warning(f"get_related_module: No items retrieved for question: '{question}'")
                return "Could not retrieve relevant information to generate an explanation for this topic."

            # Rerank the retrieved items. rerank_nodes returns List[Node]
            reranked_item_nodes = rerank_nodes(question, initial_retrieved_items)

            context_parts = [extract_node_text(item_node) for item_node in reranked_item_nodes]
            context_str = "\n\n".join(filter(None, context_parts))

            nodes_for_synthesis = reranked_item_nodes # Use reranked Node objects for synthesis

            if not context_str.strip() and initial_retrieved_items:
                # Fallback to pre-reranked context if reranking resulted in empty context
                logging.warning(f"get_related_module: Context is empty after reranking for question: '{question}'. Falling back to pre-reranked context.")
                # initial_retrieved_items are NodeWithScore, so access .node
                context_parts_initial = [extract_node_text(item.node) for item in initial_retrieved_items]
                context_str = "\n\n".join(filter(None, context_parts_initial))
                nodes_for_synthesis = [item.node for item in initial_retrieved_items] # Use original nodes

                if not context_str.strip(): # Still empty, even with fallback
                    logging.error(f"get_related_module: Fallback context is also empty for question: '{question}'")
                    return "Could not find specific information to generate an explanation for this topic."
            elif not context_str.strip() and not initial_retrieved_items: # Should be caught by earlier check but defensive
                 logging.error(f"get_related_module: No initial items and context empty for question: '{question}'")
                 return "Could not retrieve any information to generate an explanation for this topic."

            # Optional: Debug print
            # print(f"--------CONTEXT FOR EXPLANATION (after rerank_nodes) for question '{question}'--------")
            # print(context_str)
            # print("--------------------------------------")

            formatted_prompt = MODULE_TEMPLATE.format(question=question, context_str=context_str)
            response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=nodes_for_synthesis)
            return str(response_obj).strip()
        except Exception as e:
            logging.error(f"Error in get_related_module for question '{question}': {e}", exc_info=True)
            return f"Error generating explanation: {str(e)}"

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
    print("Welcome to Smart AI Tutor! Type 'exit' to quit the chat.")
    try:
        cli_storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        index = load_index_from_storage(cli_storage_context)
        print("Index loaded successfully for CLI chat.")
    except Exception as e:
        print(f"Error loading index for CLI chat: {e}")
        return
    # Note: The 'documents_from_index' argument was removed from get_hybrid_retriever
    retriever = get_hybrid_retriever(index)
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
