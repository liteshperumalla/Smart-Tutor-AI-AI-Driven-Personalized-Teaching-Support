import os
import torch
import re
import unicodedata
import pdfplumber
from pptx import Presentation
from transformers import AutoModel, AutoTokenizer
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, get_response_synthesizer
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from chromadb import PersistentClient
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.response_synthesizers import BaseSynthesizer
from llama_index.llms.ollama import Ollama
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document
from llama_index.core import StorageContext, load_index_from_storage
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from llama_index.core import PromptTemplate

# Initialize SentenceTransformer model
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Set LlamaIndex settings
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
Settings.llm = Ollama(model="llama3.1:latest", request_timeout=120.0)

# Set persist directory path
persist_dir = "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/persisted_index"

# Ensure directory exists
os.makedirs(persist_dir, exist_ok=True)

# Connect to ChromaDB for chat history and persisted index
chroma_client = PersistentClient(path=persist_dir)
chat_history_collection = chroma_client.get_or_create_collection(name="chat_history")
persisted_index_collection = chroma_client.get_or_create_collection(name="persisted_index")

# Rebuild storage context and load index
storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
try:
    index = load_index_from_storage(storage_context)
    print("Persisted index loaded successfully!")
except Exception as e:
    print(f"Error loading persisted index: {e}")
# Function to store chat history
def store_chat_history(user_input, model_response):
    """Store chat history in ChromaDB collection."""
    user_embedding = embedding_model.encode([user_input])[0]
    response_embedding = embedding_model.encode([model_response])[0]

    chat_history_collection.add(
        ids=[f"user_{len(chat_history_collection.get()['ids'])}"],
        embeddings=[user_embedding],
        metadatas=[{"role": "user", "content": user_input}]
    )

    chat_history_collection.add(
        ids=[f"assistant_{len(chat_history_collection.get()['ids'])}"],
        embeddings=[response_embedding],
        metadatas=[{"role": "assistant", "content": model_response}]
    )

# Retrieve past chat history
def retrieve_chat_history(query, top_k=5):
    """Retrieve relevant past interactions from chat history."""
    query_embedding = embedding_model.encode([query])[0]
    results = chat_history_collection.query(query_embeddings=query_embedding, n_results=top_k)
    
    metadatas = results.get("metadatas", [])
    history = [metadata["content"] for metadata_list in metadatas for metadata in metadata_list]
    return history if history else ["No relevant chat history found."]

# Retrieve full chat history
def get_full_chat_history():
    """Retrieve all stored chat interactions."""
    data = chat_history_collection.get()
    metadatas = data.get("metadatas", [])
    
    full_history = [(metadata["role"], metadata["content"]) for metadata in metadatas]
    
    return full_history if full_history else ["No chat history found."]

# Print full chat history
full_chat_history = get_full_chat_history()

print("\nFull Chat History:")
for role, content in full_chat_history:
    print(f"{role.capitalize()}: {content}")

'''def get_full_chat_history():
    """Retrieve all stored chat interactions."""
    data = chat_history_collection.get()
    metadatas = data.get("metadatas", [])
    
    full_history = [(metadata["role"], metadata["content"]) for metadata in metadatas]
    
    return full_history if full_history else ["No chat history found."]

# Print full chat history
full_chat_history = get_full_chat_history()

print("\nFull Chat History:")
for role, content in full_chat_history:
    print(f"{role.capitalize()}: {content}")
'''
