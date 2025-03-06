# Import necessary modules
from llama_index.readers.file import PptxReader, IPYNBReader, HTMLTagReader
from llama_index.core import SimpleDirectoryReader, download_loader
from transformers import ViTImageProcessor, AutoTokenizer, AutoModel
import os

# Ensure latest transformers library is installed
try:
    import transformers
    assert transformers.__version__ >= "4.25.0"  # Replace with latest version if needed
except (ImportError, AssertionError):
    os.system("pip install --upgrade transformers")  # Upgrade transformers if outdated

# Load file extractors
PptxReader = download_loader("PptxReader")
IPYNBReader = download_loader("IPYNBReader")
HTMLTagReader = download_loader("HTMLTagReader")

# Define file extractors for different file types
file_extractor = {
    ".pptx": PptxReader(),
    ".ipynb": IPYNBReader(),
    ".html": HTMLTagReader(),
}

# Load documents from the directory
reader = SimpleDirectoryReader(input_dir="./data/module_4", file_extractor=file_extractor, recursive=True)
documents = reader.load_data()

# Debugging: Print the number of documents loaded
print(f"Number of documents loaded: {len(documents)}")

# Function to chunk text into fixed-size segments
def chunk_text(text, chunk_size=1000):
    """Break text into fixed-size chunks."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

# Process and print document chunks
for doc in documents:
    file_path = getattr(doc, 'file_path', 'Unknown File')
    print(f"\nProcessing document: {file_path}")

    content = getattr(doc, 'text', None)  # Handle potential attribute variations
    if not content:
        print("Warning: Document has no text content.")
        continue

    # Chunking the document content
    chunks = chunk_text(content)

    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i + 1}/{len(chunks)}: {chunk[:200]}...")  # Printing first 200 characters

# Load GPT-2 but fix padding token issue
tokenizer = AutoTokenizer.from_pretrained("gpt2")
tokenizer.pad_token = tokenizer.eos_token  # Set pad token to eos token

model = AutoModel.from_pretrained("gpt2")

# Example tokenization with attention mask
text = "This is an example sentence for testing."
inputs = tokenizer(text, padding=True, truncation=True, return_tensors="pt")

# Ensure attention mask is used when passing input
outputs = model(**inputs)

# Fix deprecated VitFeatureExtractor by using ViTImageProcessor
image_processor = ViTImageProcessor.from_pretrained("facebook/dino-vitb8")

# Confirmation message
print("\n✅ Document processing completed successfully!")
