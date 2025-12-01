import streamlit as st
from utils import render_footer
import auth

def render():
    """Renders the home page with beautiful UI elements."""
    
    # Main Header
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0; margin-bottom: 2rem;">
        <h1 style="font-size: 3rem; margin-bottom: 0.5rem; background: linear-gradient(90deg, #3b82f6, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🎓 Smart AI Tutor
        </h1>
        <div class="subtitle" style="font-size: 1.25rem; margin-bottom: 1rem;">
            Advanced Computational Methods for Information Science
        </div>
        <div style="display: inline-block; padding: 0.5rem 1rem; background: rgba(59, 130, 246, 0.1); border-radius: 20px; color: var(--accent-color); font-weight: 500;">
            INFO 5731 | UNT Fall 2025
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Statistics
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="custom-card" style="text-align: center;">
            <div style="font-size: 2.5rem; font-weight: 700; color: var(--accent-color);">11</div>
            <div class="subtitle">Course Topics</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="custom-card" style="text-align: center;">
            <div style="font-size: 2.5rem; font-weight: 700; color: var(--accent-color);">15</div>
            <div class="subtitle">Weeks</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="custom-card" style="text-align: center;">
            <div style="font-size: 2.5rem; font-weight: 700; color: var(--accent-color);">100%</div>
            <div class="subtitle">Success Rate</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Content
    col1, col2 = st.columns([2, 1], gap="large")
    
    with col1:
        # Announcements
        st.markdown("""
        <div class="custom-card" style="margin-bottom: 2rem;">
            <h3 style="border-bottom: 2px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                📢 Latest Announcements
            </h3>
            
            <div style="background: rgba(59, 130, 246, 0.05); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid var(--accent-color);">
                <div style="font-weight: 600; margin-bottom: 0.25rem;">Welcome!</div>
                <div>Welcome to Smart AI Tutor! Your personalized learning assistant is ready to help you succeed.</div>
            </div>

            <div style="background: rgba(16, 185, 129, 0.05); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #10b981;">
                <div style="font-weight: 600; margin-bottom: 0.25rem;">💡 Getting Started</div>
                <div>Explore the features: Ask questions, generate quizzes, and access course materials.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Course Topics
        st.markdown("""
        <div class="custom-card">
            <h3 style="border-bottom: 2px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                📚 Course Topics
            </h3>
        """, unsafe_allow_html=True)
        
        topics = [
            ("🐍 Introduction to Python", "https://unt.instructure.com/courses/117821/pages/week-1-lecture-materials?module_item_id=7518917"),
            ("📖 Python Basics 1", "https://unt.instructure.com/courses/117821/pages/week-2-lecture-materials?module_item_id=7518922"),
            ("🔧 Python Basics 2", "https://unt.instructure.com/courses/117821/pages/week-3-lecture-materials?module_item_id=7518928"),
            ("🕸️ Web Scraping using Python", "https://unt.instructure.com/courses/117821/pages/week-4-lecture-materials?module_item_id=7518935"),
            ("🧹 Data Cleaning and Data Quality", "https://unt.instructure.com/courses/117821/pages/week-5-lecture-materials?module_item_id=7518942"),
            ("⚡ Feature Extraction", "https://unt.instructure.com/courses/117821/pages/week-6-lecture-materials?module_item_id=7518949"),
            ("🧠 Word Embedding and Transformer", "https://unt.instructure.com/courses/117821/pages/week-7-lecture-materials?module_item_id=7815101"),
            ("📊 Topic Modeling", "https://unt.instructure.com/courses/117821/pages/week-10-lecture-materials-2?module_item_id=7518962"),
            ("💭 Sentiment Analysis", "https://unt.instructure.com/courses/117821/pages/week-12-lecture-materials?module_item_id=7518972"),
            ("🏷️ Text Classification", "https://unt.instructure.com/courses/117821/pages/week-13-lecture-materials?module_item_id=7518976"),
            ("🤖 Generative AI in Natural Language Processing", "https://unt.instructure.com/courses/117821/pages/week-14-lecture-materials?module_item_id=7518981")
        ]
        
        for topic_name, topic_url in topics:
            st.markdown(f"""
            <a href="{topic_url}" target="_blank" style="text-decoration: none; color: inherit;">
                <div style="padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; transition: background 0.2s; border: 1px solid var(--border-color);" onmouseover="this.style.background='rgba(0,0,0,0.05)'" onmouseout="this.style.background='transparent'">
                    {topic_name}
                </div>
            </a>
            """, unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        # Professor Card
        st.markdown("""
        <div class="custom-card" style="text-align: center;">
            <h4 style="margin-bottom: 1rem;">Professor</h4>
            <div style="width: 80px; height: 80px; background: #e2e8f0; border-radius: 50%; margin: 0 auto 1rem; display: flex; align-items: center; justify-content: center; font-size: 2rem;">
                👨‍🏫
            </div>
            <div style="font-weight: 700; font-size: 1.1rem; margin-bottom: 1rem;">Dr. Haihua Chen</div>
            <div style="display: flex; gap: 0.5rem; justify-content: center;">
                <a href="https://www.linkedin.com/in/haihua-chen/" target="_blank" style="text-decoration: none; color: var(--accent-color); font-size: 0.9rem; padding: 0.25rem 0.5rem; border: 1px solid var(--accent-color); border-radius: 4px;">
                    LinkedIn
                </a>
                <a href="https://scholar.google.com/citations?user=URmnWAQAAAAJ" target="_blank" style="text-decoration: none; color: var(--accent-color); font-size: 0.9rem; padding: 0.25rem 0.5rem; border: 1px solid var(--accent-color); border-radius: 4px;">
                    Scholar
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)

    render_footer()