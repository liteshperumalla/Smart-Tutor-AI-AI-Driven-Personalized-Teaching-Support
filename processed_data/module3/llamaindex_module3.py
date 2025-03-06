#Import Library
from llama_index.core import SimpleDirectoryReader

#Instantiate Reader
reader = SimpleDirectoryReader(input_dir="data\module_3",
                               exclude = ["readme.txt",
                                          "llamaindex_module3.py"],
                                num_files_limit = 4)
documents = reader.load_data()

#Ensure data for loaded documents
for doc in documents:
    print(f"Document Name: {doc.metadata.get('file_name', 'Unknown')}")
    print(f"Document Text: {doc.text[:500]}")
    print("="*80)

output_file = "processed_data/module3/module_3_parsed_data.txt"

with open(output_file, "w", encoding = "utf-8") as f:
    for doc in documents:
        file_name = doc.metadata.get('file_name', 'Unknown')
        text_content = doc.text[:]

        f.write(f"Document Name: {file_name}\n")
        f.write(f"Document Text: {text_content}\n")
print(f"Parsed data has been saved to {output_file}")
