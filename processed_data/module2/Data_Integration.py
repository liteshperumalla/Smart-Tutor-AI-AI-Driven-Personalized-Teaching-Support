import os
import torch
import re
import unicodedata
import pdfplumber
from pptx import Presentation
from transformers import AutoModel, AutoTokenizer
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, get_response_synthesizer, PromptTemplate
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
from llama_index.core import PromptTemplate

# Set embedding model
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

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

# Set LLM with formatted prompt template
Settings.llm = Ollama(
    model="llama3.1:latest",
    request_timeout=120.0,
)

# Set persist directory path
persist_dir = "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/persisted_index"  # Replace with the actual path

# Rebuild storage context
storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

# Load index
index = load_index_from_storage(storage_context)


class RAGQueryEngine(CustomQueryEngine):
    """RAG Query Engine for custom retrieval and response synthesis."""

    retriever: BaseRetriever
    response_synthesizer: BaseSynthesizer

    def custom_query(self, query_str: str):
        nodes = self.retriever.retrieve(query_str)
        
        # Ensure we only use TextNode objects to get text
        context_str = "\n".join([node.get_text() for node in nodes if isinstance(node, Document) and node.get_text()])
        
        # Format the prompt with retrieved context
        formatted_prompt = qa_template.format(context_str=context_str, query_str=query_str)
        
        # Generate response
        response_obj = self.response_synthesizer.synthesize(query=formatted_prompt, nodes=nodes)
        return response_obj

# Create retriever and synthesizer
retriever = index.as_retriever()
synthesizer = get_response_synthesizer(response_mode="compact")

# Initialize RAG Query Engine
query_engine = RAGQueryEngine(retriever=retriever, response_synthesizer=synthesizer)

# Run query with custom prompt template
response = query_engine.query("What is python Indentation?")
print(response)
