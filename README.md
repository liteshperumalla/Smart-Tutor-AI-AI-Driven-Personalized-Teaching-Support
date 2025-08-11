# Smart Tutor AI: AI-Driven Personalized Teaching Support

## Problem
Students struggle with personalized learning support, especially accessing relevant information from course materials. Traditional search engines and LLMs often return irrelevant or inaccurate results, creating gaps in learning comprehension and academic performance.

## Approach
Leverages Retrieval-Augmented Generation (RAG) with Large Language Models to provide context-aware, personalized teaching support. Combines course-specific materials with advanced language modeling to eliminate LLM hallucinations and ensure factual, relevant responses through a multi-step pipeline including document parsing, vector embeddings, similarity search, and intelligent response generation.

## Tech Stack
- **Backend**: Python 3.9+, LlamaIndex, Ollama
- **ML/AI**: Llama 3.1 7B/8B, HuggingFace Transformers (all-MiniLM-L6-v2)
- **Database**: ChromaDB (vector storage)
- **Frontend**: Streamlit
- **Evaluation**: Evidently AI, Langfuse for real-time evaluation
- **Data Processing**: Multi-format support (PDF, PPT, DOCX, CSV, images, YouTube videos)

## Quickstart

### Install
```bash
# Clone the repository
git clone https://github.com/liteshperumalla/Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support.git
cd Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support

# Install dependencies
pip install -r requirements.txt
```

### Run
```bash
# Start the Streamlit application
streamlit run app.py

# Access the application at http://localhost:8501
```

## Results & Metrics
- **24/7 Availability**: Continuous student support with context-aware responses
- **Multi-format Support**: Processes PDFs, presentations, documents, images, and video content
- **Real-time Evaluation**: Integrated feedback system with human and automated assessment
- **Personalized Learning**: Adaptive quiz generation and individualized response tailoring
- **Academic Integration**: Successfully deployed for INFO 5731 course at University of North Texas

---

## Architecture Overview
![RAG Pipeline](https://github.com/user-attachments/assets/856dca10-e7c4-42e5-ac78-f39ca13ee96a)

## Features
- **Conversational AI Tutor**: Natural language Q&A with course materials
- **Research Mode**: Multi-format document upload and indexing
- **Automated Quiz Generation**: On-demand assessments with instant feedback
- **Smart Retrieval**: Metadata tagging and context-aware search
- **Content Download**: Access to processed materials and generated content
- **Continuous Improvement**: Built-in feedback collection and evaluation

## Getting Started - Detailed Setup

### Requirements
- Python 3.9+
- [LlamaIndex](https://www.llamaindex.ai/)
- [Ollama](https://ollama.ai/)
- [HuggingFace Transformers](https://huggingface.co/)
- [ChromaDB](https://www.trychroma.com/)
- [Streamlit](https://streamlit.io/)
- [Evidently AI](https://www.evidentlyai.com/)
- [Langfuse](https://langfuse.com/)

### Installation
```bash
pip install -r requirements.txt
```

*INFO 5731 - Computational Methods for Information Systems | University of North Texas, Spring 2025*
