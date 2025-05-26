from chromadb import PersistentClient

# Connect to your ChromaDB folder
client = PersistentClient(path="./chat_history")

# Access your collection (change name if needed)
collection = client.get_or_create_collection("chat_history")

# Peek at the first few entries (default is 10)
peeked_data = collection.peek()

# Display peeked data
print("🔍 Peeked Documents from Collection:")
for i, (doc, meta, _id) in enumerate(zip(peeked_data["documents"], peeked_data["metadatas"], peeked_data["ids"])):
    print(f"\n--- Document {i+1} ---")
    print("ID:", _id)
    print("Text (truncated):", doc[:300], "..." if len(doc) > 300 else "")
    print("Metadata:", meta)

