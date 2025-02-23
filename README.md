# Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support

Background 
With the rise of digital learning platforms, students rely on search engines and LLMs for quick information. However, these tools often return irrelevant results. Smart Tutor AI (STA) bridges this gap by providing professor-validated course materials, ensuring students receive precise and relevant content. Additionally, graduates lose access to valuable academic resources after completing courses. STA leverages retrieval-augmented generation (RAG) and structured metadata to improve content retrieval, ensuring students retain access to essential knowledge.  Objectives  Develop a structured pipeline for data collection and metadata creation. Implement a vector-based retrieval system for efficient searches. 

Build a question-answering system using RAG for contextual responses. Develop a user-friendly interface with API and Streamlit. Integrate an automated meeting scheduler for workflow efficiency. Method Design  Data Collection & Parsing: Extract Canvas course materials, clean, and structure data into JSON or a database for efficient retrieval. 

Metadata Generation: Applied NLP techniques (e.g., Named Entity Recognition) to tag data with keywords, timestamps, and categories, improving search relevance. 

Vector Database & Model Selection: Selected a scalable vector database (e.g., FAISS, Pinecone) and an embedding model (e.g., SBERT, BERT) to optimize retrieval.

RAG Model Development: Integrated the vector database with a generative model (e.g., GPT-4) for precise responses, ranking retrieved documents by relevance. Front-End Integration: Use Streamlit or Flask to create an interactive UI with real-time query processing and search history. 

Meeting Scheduler Agent: Automated scheduling via NLP-based intent detection, integrating with Google Calendar and Outlook. This system enhances learning by providing structured, relevant, and easily accessible academic conten


![smart tutor ai assitant flow diagram-Page-1 drawio (1)](https://github.com/user-attachments/assets/fd4827f3-0157-430f-8d58-d64ac8bee433)
