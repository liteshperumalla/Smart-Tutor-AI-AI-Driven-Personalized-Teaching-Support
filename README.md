# Smart Tutor AI: Personalized Teaching Support

**INFO 5731 - Computational Methods for Information Systems**  
University of North Texas, Spring 2025

[RAG Pipeline Architecture]

<img width="746" alt="RAG Pipeline" src="https://github.com/user-attachments/assets/856dca10-e7c4-42e5-ac78-f39ca13ee96a" />

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
   - Real-time Evaluation: [langfuse](https://langfuse.com/) for real time evaluation tracing using LLM as Judge.
---
## Features

1. Conversational Teaching Assistant Chatbot
24/7 Student Support: Engage in natural language conversations to clarify concepts, provide summaries, and answer questions directly from course-specific materials.
Context-Aware Responses: Utilizes advanced retrieval-augmented generation (RAG) pipeline, ensuring answers are grounded in the latest course content.

3. Research Mode
Multi-Format Document Upload: Students and instructors can upload and index various materials (PDFs, PPTX, DOCX, TXT) for enhanced Q&A.
Article Integration: Add links of scholarly articles, research papers, and supplementary readings to the knowledge base for deeper learning and richer queries.
Image Understanding: Upload relevant diagrams, screenshots, and visual course content. The system can extract text and context from images to support visual learning.
YouTube & Video Support: Submit YouTube video links; transcripts and extracted audio content are indexed, enabling users to ask questions about lecture or tutorial videos.

5. Automated Quiz Generator
On-Demand Quiz Creation: Generate quizzes to test understanding of uploaded course materials or user-selected topics.
Adaptive Questions: Topic coverage can be adjusted; generates multiple-choice, short answer.
Immediate Feedback: Provides instant grading and explanations.

7. Metadata Tagging & Smart Retrieval
Automated Metadata Extraction: Each document, chunk, or resource is tagged with relevant metadata (source, upload date, topic/module, file type, etc.).

9. Material Download & Resource Sharing
Downloadable Content: Users can download original or processed course materials, generated quizzes, and annotated notes directly from the chat interface.

11. Feedback & Continuous Improvement
User Feedback Collection: Built-in thumbs up/down feedback on each answer to refine chatbot accuracy and performance.
Human and Automated Evaluation: Combines user feedback with Evidently AI analysis to enhance faithfulness, relevance, and factuality of responses and Real time Evaluation using Langfuse.

## Getting Started

### Requirements

- Python 3.9+
- [LlamaIndex](https://www.llamaindex.ai/)
- [ollama](https://ollama/)
- [HuggingFace Transformers](https://huggingface.co/)
- [ChromaDB](https://www.trychroma.com/)
- [Streamlit](https://streamlit.io/)
- [Evidently AI](https://www.evidentlyai.com/)
- [Langfuse](https://langfuse.com/)

Install dependencies:
```bash
pip install -r requirements.txt
