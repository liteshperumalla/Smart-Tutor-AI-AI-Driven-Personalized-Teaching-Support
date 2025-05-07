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
from llama_index.core.schema import Document
from llama_index.core import VectorStoreIndex
# Define the argument parsing function
def parse_args():
    parser = argparse.ArgumentParser(description="Smart AI Tutor CLI")

    # Subcommands
    subparsers = parser.add_subparsers(dest='command')

    # Ingestion command
    ingestion_parser = subparsers.add_parser('ingest', help="Ingest data into the index")
    ingestion_parser.add_argument('data_path', type=str, help="Path to the data to ingest")

    # Query command
    query_parser = subparsers.add_parser('query', help="Query the RAG model")
    query_parser.add_argument('query_text', type=str, help="Query text for the RAG model")

    # Chat command (interactive mode)
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
    "Given the context information and not prior knowledge,"
    "You are a Teaching Assistant designed to assist users in answering queries."
    "Explain concepts, solving coding doubts, and providing relevant resources from course modules."
    "And also give a simple example to make student understand the concept.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this information, please answer the question: {query_str}\n"
)
qa_template = PromptTemplate(template)

QUESTION_TEMPLATE = PromptTemplate(
    " Given the context information and not prior knowledge"
    "Generate a multiple-choice quiz question (A/B/C/D) with only one correct answer."
"--------------------\n{context_str}\n--------------------"
)

ANSWER_TEMPLATE = PromptTemplate(
    "Here is a quiz question:{question} What is the correct answer to this question? Provide only the correct option (A/B/C/D) with the answer text."
)

MODULE_TEMPLATE = PromptTemplate(
    "Given this incorrect quiz answer: Question: {question} Return a short paragraph from the context that can help a student understand the correct concept."
)
UPLOADED_DOCS_TEMPLATE = PromptTemplate(
    "You are an AI tutor. Using only the information from the uploaded documents below, answer the user's question in a helpful and concise way.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Question: {query_str}\n"
)


class RAGQueryEngine:
    def __init__(self, retriever, response_synthesizer, mode="chat"):
        """
        mode: 'chat' for chat mode, 'quiz' for quiz mode.
        """
        self.retriever = retriever
        self.response_synthesizer = response_synthesizer
        self.mode = mode

    def custom_query(self, query_str: str, doc: Document = None) -> str:
        """
        Handles the query based on the mode:
        - 'chat': For chat-based queries
        - 'quiz': For quiz-based queries
        - 'uploaded_doc': For queries based on uploaded documents
        """
        nodes = self.retriever.retrieve(query_str)

        # Handle different modes
        if self.mode == "chat":
            context_str = "\n".join([node.get_text() for node in nodes if isinstance(node, Document)])
            formatted_prompt = qa_template.format(context_str=context_str, query_str=query_str)
        
        elif self.mode == "quiz":
            context_str = "\n".join([node.get_text() for node in nodes if isinstance(node, Document)])
            formatted_prompt = QUESTION_TEMPLATE.format(context_str=context_str, query_str=query_str)
        
        elif self.mode == "uploaded_doc" and doc:
            # For uploaded documents, create a new index and retriever
            index = VectorStoreIndex.from_documents([doc])
            retriever = index.as_retriever()
            nodes = retriever.retrieve(query_str)
            
            if not nodes or all(not node.get_text().strip() for node in nodes):
                return "I'm sorry, I couldn't find an answer based on the uploaded document."

            context_str = "\n".join([node.get_text() for node in nodes])
            formatted_prompt = UPLOADED_DOCS_TEMPLATE.format(context_str=context_str, query_str=query_str)

        # Synthesize the response
        response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=nodes)
        return str(response_obj).strip()
    
    def get_correct_answer(self, question: str) -> str:
        nodes = self.retriever.retrieve(question)
        formatted_prompt = ANSWER_TEMPLATE.format(question=question)
        response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=nodes)
        return str(response_obj).strip()

    def get_related_module(self, question: str) -> str:
        nodes = self.retriever.retrieve(question)
        formatted_prompt = MODULE_TEMPLATE.format(question=question)
        response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=nodes)
        return str(response_obj).strip()
    
    def query_uploaded_docs(self, query_str: str, doc: Document) -> str:
        """
        Query method specifically for uploaded documents, independent of 'chat' or 'quiz' mode.
        """
        index = VectorStoreIndex.from_documents([doc])
        retriever = index.as_retriever()
        nodes = retriever.retrieve(query_str)

        if not nodes or all(not node.get_text().strip() for node in nodes):
            return "I'm sorry, I couldn't find an answer based on the uploaded document."

        context_str = "\n".join([node.get_text() for node in nodes])
        
        formatted_prompt = UPLOADED_DOCS_TEMPLATE.format(context_str=context_str, query_str=query_str)
        synthesizer = get_response_synthesizer(response_mode="compact")
        return str(synthesizer.synthesize(query=formatted_prompt, nodes=nodes)).strip()



# Function to handle the interactive chat
def chat():
    print("Welcome to Smart AI Tutor! Type 'exit' to quit the chat.")
    while True:
        # Get user input
        user_input = input("You: ")
        
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        
        # Query the RAG model and return a response
        print(f"Running query: {user_input}")
        
        # Load index
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

# Main function to control CLI behavior
def main():
    args = parse_args()

    if args.command == 'ingest':
        run_ingestion(args.data_path)
    elif args.command == 'query':
        run_query(args.query_text)
    elif args.command == 'chat':
        chat()  # Start interactive chat mode
    else:
        print("Invalid command. Use -h for help.")

if __name__ == '__main__':
    main()