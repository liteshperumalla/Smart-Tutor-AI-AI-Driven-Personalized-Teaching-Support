import streamlit as st
from utils import render_footer # Assuming render_footer is in utils.py
import auth
auth.initialize_session()

def render():
    """Renders the About page for the Smart AI Tutor."""
    st.title("ℹ️ About Smart AI Tutor")


    st.markdown("""
        ### 🎯 Purpose of the Application
        **Smart AI Tutor** is an intelligent, interactive platform meticulously designed to revolutionize the way students learn, engage with educational content, and assess their understanding. Leveraging the power of cutting-edge Artificial Intelligence and Retrieval-Augmented Generation (RAG) technology, this application aims to provide a personalized and effective learning experience.

        Key features include:
        - 📄 **Interactive Document Chat:** Engage in conversations with your uploaded documents (PDF, DOCX, PPTX, TXT), ask questions, and get summaries.
        - 🧠 **Custom Quiz Generation:** Create quizzes from course materials or uploaded content to test your knowledge and identify areas for improvement.
        - 💡 **Personalized Tutoring:** Experience AI-driven tutoring that adapts to your learning pace and style. (Future Enhancement)
        - 🗂️ **Resource Hub:** Access a curated list of relevant course materials, external links, and academic resources.
        - 📅 **Appointment Scheduling:** Easily schedule appointments with professors or teaching assistants.

        Our overarching goal is to make education more accessible, engaging, and tailored to the individual needs of students, educators, and lifelong learners. We believe in harnessing AI to augment human potential and foster a deeper understanding of complex subjects.

        ---
        ### 🛠️ Technology Stack
        This application is built using a modern stack of technologies:
        -   **Frontend:** [Streamlit](https://streamlit.io/) - For creating a beautiful and interactive web application with Python.
        -   **Backend & AI Core:** Python, [LlamaIndex](https://www.llamaindex.ai/) - For data indexing, retrieval, and RAG pipeline.
        -   **Language Models (LLM):** Powered by [Ollama](https://ollama.ai/) for local LLM serving (e.g., Llama 3.2).
        -   **File Processing:** Libraries such as `PyMuPDF` (for PDFs), `python-pptx` (for PowerPoint), `python-docx` (for Word documents), `Pillow` & `pytesseract` (for OCR).
        -   **Chat & NLP:** Core NLP tasks handled by LlamaIndex and the underlying LLM.

        ---
        ### 👨‍💻 Developer Profile
    """)

    # Developer Info Columns
    col1, col2 = st.columns([1, 3])
    with col1:
        # Placeholder for a profile picture if you have one
        st.image("/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/1744122201330.jpeg", width=150)

    with col2:
        st.markdown("""
            **Litesh Perumalla** *Master's Student in Data Science, University of North Texas* An enthusiastic AI practitioner with a passion for developing intelligent solutions to real-world problems. My expertise lies in Python, Machine Learning, Natural Language Processing, and building RAG-based applications. I am dedicated to exploring the frontiers of AI to create impactful and user-centric tools.
            
            - 📧 **Email:** `liteshperumalla@my.unt.edu`
            - 🔗 **GitHub:** [github.com/liteshperumalla](https://github.com/liteshperumalla)
            - 🌐 **LinkedIn:** [linkedin.com/in/perumalla-litesh](https://www.linkedin.com/in/perumalla-litesh/)
        """)
    
    st.markdown("""
        ---
        ### 📢 Contact & Contributions
        We welcome your feedback, feature requests, and bug reports! 
        - For **feedback or to report a bug**, please use the dedicated "Feedback and Bug Report" page in the sidebar.
        - For **collaboration inquiries or direct contact**, please reach out via the email address listed above.

        This project is a continuous effort, and contributions or suggestions for improvement are always appreciated.
    """)
    
    render_footer()
