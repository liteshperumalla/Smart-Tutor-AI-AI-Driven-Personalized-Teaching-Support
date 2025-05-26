import os
import argparse
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings, get_response_synthesizer, PromptTemplate
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.response_synthesizers import BaseSynthesizer
from llama_index.llms.ollama import Ollama
from llama_index.core import StorageContext, load_index_from_storage
from sentence_transformers import SentenceTransformer

# Define the argument parsing function
def parse_args():
    parser = argparse.ArgumentParser(description="Smart AI Tutor CLI")
    subparsers = parser.add_subparsers(dest='command')

    ingestion_parser = subparsers.add_parser('ingest', help="Ingest data into the index")
    ingestion_parser.add_argument('data_path', type=str, help="Path to the data to ingest")

    query_parser = subparsers.add_parser('query', help="Query the RAG model")
    query_parser.add_argument('query_text', type=str, help="Query text for the RAG model")

    subparsers.add_parser('chat', help="Interactive chat with the AI tutor")
    return parser.parse_args()

# Set up necessary models and directories
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
Settings.llm = Ollama(model="llama3.1:latest", request_timeout=120.0)

persist_dir = "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/persisted_index"
os.makedirs(persist_dir, exist_ok=True)
storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

# Define the custom prompt template
template = (
    "Given the context information and not prior knowledge, "
    "you are a Teaching Assistant designed to assist users in answering queries. "
    "Explain concepts, solve coding doubts, and provide relevant resources from course modules. "
    "Also, provide a simple example to help the student understand the concept.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this information, please answer the question: {query_str}\n"
)
qa_template = PromptTemplate(template)

# Custom RAG Query Engine class with modifications
class RAGQueryEngine(CustomQueryEngine):
    """RAG Query Engine for custom retrieval and response synthesis."""

    retriever: BaseRetriever
    response_synthesizer: BaseSynthesizer

    def custom_query(self, query_str: str):
        nodes = self.retriever.retrieve(query_str)
        # Collect text from nodes that have a get_text() method and non-empty text
        context_str = "\n".join(
            [node.get_text() for node in nodes if hasattr(node, 'get_text') and node.get_text()]
        )

        # Debug: Print the relevant chunk used by the LLM
        if context_str:
            print("Relevant Chunk:")
            print(context_str)
        else:
            print("No relevant text found in nodes. Debug info:")
            for node in nodes:
                text = node.get_text() if hasattr(node, 'get_text') else "No text attribute"
                print(f"Node type: {type(node)}, Content: {text}")

        formatted_prompt = qa_template.format(context_str=context_str, query_str=query_str)
        response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=nodes)
        return response_obj

    # Override the query method so that custom_query is used
    def query(self, query_str: str):
        return self.custom_query(query_str)

# Function to handle the interactive chat
def chat():
    print("Welcome to Smart AI Tutor! Type 'exit' to quit the chat.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        print(f"Running query: {user_input}")
        try:
            index = load_index_from_storage(storage_context)
            print("Index loaded successfully.")
        except Exception as e:
            print(f"Error loading index: {e}")
            continue

        retriever = index.as_retriever()
        synthesizer = get_response_synthesizer(response_mode="compact")
        query_engine = RAGQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
        response = query_engine.query(user_input)
        print("Assistant:", response)

# Placeholder functions for ingestion and query commands
def run_ingestion(data_path):
    print(f"Ingestion function not implemented. Data path provided: {data_path}")

def run_query(query_text):
    print(f"Query function not implemented. Query text provided: {query_text}")

# Main function to control CLI behavior
def main():
    args = parse_args()
    if args.command == 'ingest':
        run_ingestion(args.data_path)
    elif args.command == 'query':
        run_query(args.query_text)
    elif args.command == 'chat':
        chat()
    else:
        print("Invalid command. Use -h for help.")

if __name__ == '__main__':
    main()
