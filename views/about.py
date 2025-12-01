import streamlit as st
from utils import render_footer
import auth
auth.initialize_session()

def render():
    """Renders the About page for the Smart AI Tutor."""
    
    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="margin-bottom: 0.5rem;">ℹ️ About Smart AI Tutor</h1>
        <div class="subtitle">Empowering education with Artificial Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    # Purpose Section
    st.markdown("""
    <div class="custom-card" style="margin-bottom: 2rem;">
        <h3 style="margin-bottom: 1rem;">🎯 Purpose of the Application</h3>
        <p>
            <strong>Smart AI Tutor</strong> is an intelligent, interactive platform meticulously designed to revolutionize the way students learn, engage with educational content, and assess their understanding. Leveraging the power of cutting-edge Artificial Intelligence and Retrieval-Augmented Generation (RAG) technology, this application aims to provide a personalized and effective learning experience.
        </p>
        <div style="margin-top: 1.5rem;">
            <h4 style="margin-bottom: 0.5rem;">Key Features:</h4>
            <ul style="list-style-type: none; padding-left: 0;">
                <li style="margin-bottom: 0.5rem;">📄 <strong>Interactive Document Chat:</strong> Engage in conversations with your uploaded documents.</li>
                <li style="margin-bottom: 0.5rem;">🧠 <strong>Custom Quiz Generation:</strong> Create quizzes from course materials to test your knowledge.</li>
                <li style="margin-bottom: 0.5rem;">💡 <strong>Personalized Tutoring:</strong> Experience AI-driven tutoring that adapts to your learning pace.</li>
                <li style="margin-bottom: 0.5rem;">🗂️ <strong>Resource Hub:</strong> Access a curated list of relevant course materials.</li>
                <li style="margin-bottom: 0.5rem;">📅 <strong>Appointment Scheduling:</strong> Easily schedule appointments with professors.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Technology Stack
    st.markdown("""
    <div class="custom-card" style="margin-bottom: 2rem;">
        <h3 style="margin-bottom: 1rem;">🛠️ Technology Stack</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
            <div style="padding: 1rem; background: rgba(59, 130, 246, 0.05); border-radius: 8px; border: 1px solid var(--border-color);">
                <strong>Frontend</strong><br>Streamlit
            </div>
            <div style="padding: 1rem; background: rgba(16, 185, 129, 0.05); border-radius: 8px; border: 1px solid var(--border-color);">
                <strong>Backend & AI Core</strong><br>Python, LlamaIndex
            </div>
            <div style="padding: 1rem; background: rgba(245, 158, 11, 0.05); border-radius: 8px; border: 1px solid var(--border-color);">
                <strong>LLM</strong><br>Ollama (Llama 3.2)
            </div>
            <div style="padding: 1rem; background: rgba(139, 92, 246, 0.05); border-radius: 8px; border: 1px solid var(--border-color);">
                <strong>File Processing</strong><br>PyMuPDF, python-pptx
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Developer Profile
    st.markdown("""
    <div class="custom-card">
        <h3 style="margin-bottom: 1.5rem;">👨‍💻 Developer Profile</h3>
        <div style="display: flex; gap: 2rem; align-items: start; flex-wrap: wrap;">
            <div style="flex: 0 0 150px;">
                <img src="https://github.com/liteshperumalla.png" style="width: 150px; height: 150px; border-radius: 50%; border: 3px solid var(--accent-color); object-fit: cover;" alt="Litesh Perumalla">
            </div>
            <div style="flex: 1; min-width: 300px;">
                <h4 style="margin-bottom: 0.5rem; font-size: 1.5rem;">Litesh Perumalla</h4>
                <div style="color: var(--text-secondary); margin-bottom: 1rem;">Master's Student in Data Science, University of North Texas</div>
                <p style="margin-bottom: 1.5rem;">
                    An enthusiastic AI practitioner with a passion for developing intelligent solutions to real-world problems. My expertise lies in Python, Machine Learning, Natural Language Processing, and building RAG-based applications. I am dedicated to exploring the frontiers of AI to create impactful and user-centric tools.
                </p>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                    <a href="mailto:liteshperumalla@my.unt.edu" style="text-decoration: none; color: var(--text-primary); background: rgba(0,0,0,0.05); padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem;">
                        📧 liteshperumalla@my.unt.edu
                    </a>
                    <a href="https://github.com/liteshperumalla" target="_blank" style="text-decoration: none; color: var(--text-primary); background: rgba(0,0,0,0.05); padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem;">
                        🔗 GitHub
                    </a>
                    <a href="https://www.linkedin.com/in/perumalla-litesh/" target="_blank" style="text-decoration: none; color: var(--text-primary); background: rgba(0,0,0,0.05); padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem;">
                        🌐 LinkedIn
                    </a>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Contact Section
    st.markdown("""
    <div style="margin-top: 2rem; text-align: center; padding: 2rem; background: rgba(59, 130, 246, 0.05); border-radius: 12px;">
        <h4 style="margin-bottom: 1rem;">📢 Contact & Contributions</h4>
        <p style="margin-bottom: 1rem;">We welcome your feedback, feature requests, and bug reports!</p>
        <div style="font-size: 0.9rem; color: var(--text-secondary);">
            For feedback, please use the "Feedback and Bug Report" page in the sidebar.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    render_footer()
