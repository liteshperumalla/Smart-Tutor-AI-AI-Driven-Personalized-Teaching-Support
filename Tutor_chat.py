
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
    langfuse_callback_handler = LlamaIndexCallbackHandler(
        public_key="pk-lf-206a6716-2d0d-490b-8fdc-4057c92234b8",
        secret_key="sk-lf-fbec8985-d86a-4d50-9d1e-96b1ac785bc1",
        host="https://cloud.langfuse.com"
    )
    Settings.callback_manager = CallbackManager([langfuse_callback_handler])
    logging.info("Langfuse callback handler initialized successfully.")
except ImportError:
    logging.error("Failed to import LlamaIndexCallbackHandler. Please check Langfuse SDK version.")
    langfuse_callback_handler = None 
except Exception as e:
    logging.error(f"Failed to initialize Langfuse callback handler: {e}")
    langfuse_callback_handler = None

try:
    langfuse_client = Langfuse() 
    logging.info("Langfuse client initialized (will use env vars if set).")
except Exception as e:
    logging.error(f"Failed to initialize Langfuse client: {e}. Tracing might be partially or fully disabled.")
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

    def custom_query(self, query_str: str, doc: Optional[Document] = None, forced_context_str: Optional[str] = None) -> str:
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
                retrieved_items = self.retriever.retrieve(query_str)
                context_parts = [extract_node_text(item) for item in retrieved_items]
                context_str_for_prompt = "\n\n".join(filter(None, context_parts))
                nodes_for_synthesis = retrieved_items
            print("--------CONTEXT PASSED TO LLM--------")
            print(context_str_for_prompt)
            print("--------------------------------------")
            if self.mode == "quiz" and (not context_str_for_prompt or len(context_str_for_prompt) < 30):
                if not forced_context_str:
                    logging.warning(f"Warning: Context for quiz question generation is short or empty. Query: '{query_str}'")
                if not context_str_for_prompt.strip() and self.mode == "quiz":
                    logging.error("Cannot generate quiz question: Context is empty.")
                    return json.dumps({"error": "Context is empty, cannot generate question."})

            final_prompt_for_llm = current_template.format(context_str=context_str_for_prompt, query_str=query_str)
            response_obj = self.response_synthesizer.synthesize(query=final_prompt_for_llm, nodes=nodes_for_synthesis)
            return str(response_obj).strip()
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
    print("Welcome to Smart AI Tutor! Type 'exit' to quit the chat.")
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
