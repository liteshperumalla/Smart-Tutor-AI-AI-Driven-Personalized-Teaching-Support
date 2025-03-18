import os
import torch
import re 
import torch.multiprocessing
torch.multiprocessing.set_start_method('spawn')
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

try:
    model_name = "sentence-transformers/all-MiniLM-L6-v2"  # Keep it as a string
    Settings.embed_model = HuggingFaceEmbedding(model_name=model_name)  # Pass string
    print(f"✅ Model {model_name} loaded successfully.")
except Exception as e:
    print(f"❌ Error loading embedding model: {e}")
    exit()

#Settings.llm = Ollama(model="llama3.1:latest", request_timeout=120.0)
Settings.llm = None

# ------------------------------
# DEFINE TEXT PREPROCESSING FUNCTION
# ------------------------------
def preprocess_text(file_path, text):
    """
    Preprocesses the text depending on the file type:
    - Removes punctuation for non-code files
    - Leaves code files untouched
    """
    # Define file extensions for code and text
    text_extensions = {".pdf", ".docx", ".pptx", ".txt"}

    # Check the file extension
    ext = os.path.splitext(file_path)[-1].lower()

    # If it's a text file, remove punctuation
    if ext in text_extensions:
        text = re.sub(r'[^A-Za-z0-9\s]', '', text)  # Keep words and spaces only
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
    
    return text

# ------------------------------
# LOAD DOCUMENTS & PREPROCESS
# ------------------------------
doc_path = "/Users/Guest/Downloads/Module 2"

try:
    # Specify file extensions you want to read
    reader = SimpleDirectoryReader(doc_path, required_exts=['.pptx', '.ipynb', '.docx', '.csv', '.jpeg', '.pdf', '.png'])
    docs = reader.load_data()  # Load the documents

    if not docs:
        print("❌ No documents found! Check the path and file extensions.")
        exit()

    print(f"✅ Loaded {len(docs)} docs")

    # Loop through the documents and print metadata
    for idx, doc in enumerate(docs):
        print(f"{idx} - {doc.metadata}")  # Print the metadata of each document

except Exception as e:
    print(f"❌ Error loading documents: {e}")
    exit()

# Apply metadata and preprocess text for documents in `docs`
for doc in docs:
    doc.metadata = {
        "file_name": doc.metadata.get("file_name", ""),
        "file_path": doc.metadata.get("file_path", "")
    }
    processed_text = preprocess_text(doc.metadata["file_path"], doc.get_content())
    doc.set_content(processed_text)

# ------------------------------
# INITIALIZE CHROMADB VECTOR STORE
# ------------------------------
chroma_path = "./chroma_db"
try:
    chroma_client = PersistentClient(path=chroma_path)
    collection = chroma_client.get_or_create_collection("document_chunks")

    vector_store = ChromaVectorStore(chroma_client, collection_name="document_chunks")
    print("✅ ChromaDB initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing ChromaDB: {e}")
    exit()

# ------------------------------
# DOCUMENT PROCESSING PIPELINE
# ------------------------------
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=100, chunk_overlap=10),
        Settings.embed_model
    ],
)

try:
    nodes = pipeline.run(documents=docs)  # Use docs instead of reader
    if not nodes:
        print("❌ No nodes were created. Check document parsing.")
        exit()
    print(f"✅ {len(nodes)} document nodes created and stored in ChromaDB.")
    for i, node in enumerate(nodes):
        collection.add(
            ids=[str(i)],  # Unique ID for each chunk
            documents=[node.text],  # Text content of the chunk
            metadatas=[node.metadata]  # Metadata (e.g., filename)
        )
except Exception as e:
    print(f"❌ Error during ingestion pipeline: {e}")
    exit()

# ------------------------------
# CREATE VECTOR STORE INDEX
# ------------------------------
try:
    index = VectorStoreIndex(nodes, vector_store=vector_store)
    print("✅ Vector store index created successfully.")
    persist_dir = "./persisted_index"  # Specify the directory where you want to store the index
    os.makedirs(persist_dir, exist_ok=True)  # Make sure the directory exists
    index.storage_context.persist(persist_dir=persist_dir)
    print(f"✅ Index persisted to {persist_dir}")
except Exception as e:
    print(f"❌ Error creating VectorStoreIndex: {e}")
    exit()

# ------------------------------
# CREATE CHAT ENGINE & PROCESS QUERY
# ------------------------------
class RAGQueryEngine(CustomQueryEngine):
    """RAG Query Engine for custom retrieval and response synthesis."""

    retriever: BaseRetriever
    response_synthesizer: BaseSynthesizer

    def custom_query(self, query_str: str):
        # Retrieve relevant nodes using the retriever
        nodes = self.retriever.retrieve(query_str)
        
        # Generate response using the response synthesizer
        response_obj = self.response_synthesizer.synthesize(query_str, nodes)
        
        # Return the synthesized response
        return response_obj

# Configure retriever
retriever = index.as_retriever()

# Handle the attention mask warning explicitly
synthesizer = get_response_synthesizer(response_mode="compact")

query_engine = RAGQueryEngine(
    retriever=retriever, response_synthesizer=synthesizer
)

# Query the engine
response = query_engine.query("What is Python Indentation?")
print(response)
