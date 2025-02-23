from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import TokenTextSplitter, SentenceSplitter
from llama_index.core.extractors import TitleExtractor
from llama_index.core import Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
import qdrant_client

# Set Hugging Face embedding model
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.llm = None
# Load data from directory
reader = SimpleDirectoryReader('/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/Module 2', required_exts=['.pptx', '.ipynb']).load_data()

# Create index
index = VectorStoreIndex(reader)
print("Index created:", index)

# Print out document data loaded by reader
print("Loaded documents:")
for doc in reader:
    print(f"Document name: {doc.doc_id}")
    print(f"Content: {doc.text[:200]}...")  # Display first 200 characters of the content for each document

# Initialize Qdrant client and vector store
client = qdrant_client.QdrantClient(location=":memory:")
vector_store = QdrantVectorStore(client=client, collection_name="test_store")

# Create ingestion pipeline
pipeline = IngestionPipeline(
    transformations=[
        TokenTextSplitter(),
        SentenceSplitter(chunk_size=50, chunk_overlap=0),
        TitleExtractor()  
    ],
    vector_store=vector_store
)

# Run the pipeline on documents
nodes = pipeline.run(documents=reader)
print("Parsed nodes:")
for node in nodes:
    print(f"Node ID: {node.node_id}")
    print(f"Text: {node.text[:200]}...")

# (Optional) Save the index for future use
# faiss.write_index(index, 'embeddings.index')

# Create index from the vector store
index = VectorStoreIndex.from_vector_store(vector_store)
collection_name = "test_store"

# List collections to ensure "test_store" exists
collections = client.get_collections()
print("Existing collections:", collections)

# If the collection exists, retrieve the first few vectors
if collection_name in collections:
    # Retrieve vectors from the collection
    search_result = client.search(
        collection_name=collection_name,  # The collection name
        query_vector=[0.1, 0.2, 0.3],  # Example query vector (use a real one here)
        limit=5  # Number of nearest neighbors to retrieve
    )
    
    print("Search result:", search_result)
else:
    print(f"Collection {collection_name} does not exist.")
collection_info = client.get_collection(collection_name)
print("Collection info:", collection_info)
