# Smart Tutor AI: Personalized Teaching Support

**INFO 5731 - Computational Methods for Information Systems**  
University of North Texas, Spring 2025


![RAG Pipeline Architecture](<img width="746" alt="RAG Pipeline" src="https://github.com/user-attachments/assets/856dca10-e7c4-42e5-ac78-f39ca13ee96a" />)

## Abstract

Smart Tutor AI leverages Retrieval-Augmented Generation (RAG) and Large Language Models (LLMs) to provide personalized, context-aware teaching support. By combining course-specific materials with advanced language modeling, the system addresses the hallucination problem of traditional LLMs, ensuring more factual, relevant, and helpful student support.

---

## Pipeline Overview

Our architecture consists of the following steps (see the diagram above):

1. **Data Collection**  
   - Source: Course documents (PPT, PDF, Python, CSV, DOCX, etc.)
   - Files are collected and stored for parsing.

2. **Document Parsing**  
   - Tool: [LlamaIndex](https://www.llamaindex.ai/)
   - Documents are ingested, parsed, and preprocessed (text cleaning, chunking).

3. **Embeddings**  
   - Tool: [HuggingFace Transformers](https://huggingface.co/) (`all-MiniLM-L6-v2`)
   - Text chunks are converted into vector embeddings.
   - Embeddings are stored in [ChromaDB](https://www.trychroma.com/).

4. **Similarity Search & Reranking**  
   - User queries are embedded.
   - Top-K relevant chunks are retrieved and re-ranked for context relevance.

5. **LLM Response Generation**  
   - Model: Llama 3.1 7B/8B, running locally or via API (e.g., Ollama)
   - The LLM combines retrieved context with prompt engineering to generate responses.

6. **Frontend**  
   - [Streamlit](https://streamlit.io/) UI for user interaction.
   - Chat interface for querying, response display, and feedback collection.

7. **Evaluation**  
   - Human evaluation: Fluency, coherence, factuality, and relevance (Likert scale).
   - Automated evaluation: [Evidently AI](https://www.evidentlyai.com/) for context quality and faithfulness.

---

## Getting Started

### Requirements

- Python 3.9+
- [LlamaIndex](https://www.llamaindex.ai/)
- [HuggingFace Transformers](https://huggingface.co/)
- [ChromaDB](https://www.trychroma.com/)
- [Streamlit](https://streamlit.io/)
- [Evidently AI](https://www.evidentlyai.com/)

Install dependencies:
```bash
pip install -r requirements.txt
