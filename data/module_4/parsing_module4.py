from llama_index.readers.file import PptxReader, IPYNBReader, HTMLTagReader
from llama_index.core import SimpleDirectoryReader, download_loader

# loading the file extractors 
PptxReader = download_loader("PptxReader")
IPYNBReader = download_loader("IPYNBReader")
HTMLTagReader = download_loader("HTMLTagReader")

# defining file extractors
file_extractor = {
    ".pptx": PptxReader(),
    ".ipynb": IPYNBReader(),
    ".html": HTMLTagReader(),
}

# loading documents from the directory
reader = SimpleDirectoryReader(input_dir="./data/module_4", file_extractor=file_extractor, recursive=True)
documents = reader.load_data()

# debugging: printing the number of documents loaded
print(f"Number of documents loaded: {len(documents)}")

# writing a function to chunk text
def chunk_text(text, chunk_size=1000):
    """Break text into fixed-size chunks."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

# processing and printing chunks
for doc in documents:
    print(f"Processing document: {getattr(doc, 'file_path', 'Unknown File')}")
    content = getattr(doc, 'text', None)  # handling potential attribute variations
    
    if not content:
        print("Warning: Document has no text content.")
        continue
    
    # chunking the document content
    chunks = chunk_text(content)
    
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i + 1}/{len(chunks)}: {chunk[:200]}...")  # printing only the first 200 characters