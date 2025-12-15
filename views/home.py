import os
import streamlit as st
from textwrap import dedent
from utils import render_footer, get_system_status, get_recent_chat_summaries, load_chat_sessions


def _render_html_block(html: str):
    """Helper to drop indentation so Streamlit doesn't treat HTML as code."""
    st.markdown(dedent(html).strip(), unsafe_allow_html=True)

def render():
    """Renders the home page with beautiful UI elements."""
    
    # Main Header
    _render_html_block("""
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
    """)
    
    # Statistics
    c1, c2, c3 = st.columns(3)
    with c1:
        _render_html_block("""
        <div class="custom-card" style="text-align: center;">
            <div style="font-size: 2.5rem; font-weight: 700; color: var(--accent-color);">11</div>
            <div class="subtitle">Course Topics</div>
        </div>
        """)
    with c2:
        _render_html_block("""
        <div class="custom-card" style="text-align: center;">
            <div style="font-size: 2.5rem; font-weight: 700; color: var(--accent-color);">15</div>
            <div class="subtitle">Weeks</div>
        </div>
        """)
    with c3:
        _render_html_block("""
        <div class="custom-card" style="text-align: center;">
            <div style="font-size: 2.5rem; font-weight: 700; color: var(--accent-color);">100%</div>
            <div class="subtitle">Success Rate</div>
        </div>
        """)
    system_status = get_system_status()
    kb_stats = system_status["knowledge_base"]
    status_cols = st.columns(3, gap="large")
    with status_cols[0]:
        _render_html_block(f"""
        <div class="custom-card" style="border-left: 4px solid {'#10b981' if kb_stats.get('ready') else '#f87171'};">
            <div class="subtitle">Knowledge Base</div>
            <div style="font-size: 2rem; font-weight: 700;">{kb_stats.get('document_count', 0):,}</div>
            <div style="font-size: 0.9rem; color: var(--text-secondary);">
                from {kb_stats.get('source_count', 0)} source files
            </div>
        </div>
        """)
    with status_cols[1]:
        _render_html_block(f"""
        <div class="custom-card" style="border-left: 4px solid {'#10b981' if system_status.get('evaluation_ready') else '#f87171'};">
            <div class="subtitle">Evaluation Suite</div>
            <div style="font-size: 2rem; font-weight: 700;">{system_status.get('evaluation_cases', 0)}</div>
            <div style="font-size: 0.9rem; color: var(--text-secondary);">
                test cases ready
            </div>
        </div>
        """)
    with status_cols[2]:
        ollama_ready = system_status["ollama"].get("ready")
        model_count = len(system_status["ollama"].get("models", []))
        _render_html_block(f"""
        <div class="custom-card" style="border-left: 4px solid {'#10b981' if ollama_ready else '#f87171'};">
            <div class="subtitle">LLM Service</div>
            <div style="font-size: 2rem; font-weight: 700;">{"Online" if ollama_ready else "Offline"}</div>
            <div style="font-size: 0.9rem; color: var(--text-secondary);">
                {model_count} model{'s' if model_count != 1 else ''} detected
            </div>
        </div>
        """)

    if system_status["issues"]:
        llm_model = os.getenv("LLM_MODEL", "llama3.2:latest")
        ollama_base = system_status["ollama"].get("base_url", "http://localhost:11434")
        issue_items = []
        for issue in system_status["issues"]:
            if "ollama" in issue.lower():
                issue_items.append(
                    f"<li>LLM service is unreachable at <code>{ollama_base}</code>. Start it locally with "
                    f"<code>ollama serve</code> and ensure <code>ollama pull {llm_model}</code> has been run.</li>"
                )
            else:
                issue_items.append(f"<li>{issue}</li>")

        _render_html_block(f"""
        <div class="custom-card" style="border-left: 4px solid #f97316; background: rgba(249, 115, 22, 0.08); margin-top: 0.5rem;">
            <strong>Action needed:</strong>
            <ul style="margin: 0.5rem 0 0 1.25rem;">{''.join(issue_items)}</ul>
        </div>
        """)

    st.markdown("<br>", unsafe_allow_html=True)

    quick_actions = [
        {
            "emoji": "💬",
            "title": "Start Chatting",
            "description": "Ask anything about INFO 5731 and cite actual course material.",
            "page": "chat",
            "cta": "Go to Chat",
        },
        {
            "emoji": "🧪",
            "title": "Generate a Quiz",
            "description": "Create targeted quizzes with instant scoring and exportable results.",
            "page": "quizgenerator",
            "cta": "Open Quiz Builder",
        },
        {
            "emoji": "📂",
            "title": "Research Mode",
            "description": "Upload or browse indexed material to expand your personal knowledge base.",
            "page": "Research Mode",
            "cta": "Open Research Mode",
        },
    ]

    st.markdown("#### Quick Actions")
    qa_cols = st.columns(len(quick_actions), gap="large")
    for idx, action in enumerate(quick_actions):
        with qa_cols[idx]:
            _render_html_block(f"""
            <div class="custom-card" style="min-height: 180px;">
                <div style="font-size: 2rem;">{action['emoji']}</div>
                <div style="font-weight: 600; margin-top: 0.5rem;">{action['title']}</div>
                <div style="font-size: 0.9rem; color: var(--text-secondary); margin: 0.5rem 0 1rem;">
                    {action['description']}
                </div>
            </div>
            """)
            if st.button(action["cta"], key=f"quick_action_{idx}", use_container_width=True):
                st.session_state.page = action["page"]
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Content
    col1, col2 = st.columns([2, 1], gap="large")
    
    with col1:
        # Announcements
        _render_html_block("""
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
        """)
        
        # Course Topics
        _render_html_block("""
        <div class="custom-card">
            <h3 style="border-bottom: 2px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                📚 Course Topics
            </h3>
        """)
        
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
            _render_html_block(f"""
            <a href="{topic_url}" target="_blank" style="text-decoration: none; color: inherit;">
                <div style="padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; transition: background 0.2s; border: 1px solid var(--border-color);" onmouseover="this.style.background='rgba(0,0,0,0.05)'" onmouseout="this.style.background='transparent'">
                    {topic_name}
                </div>
            </a>
            """)
            
        _render_html_block("</div>")

    with col2:
        # Professor Card
        _render_html_block("""
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
        """)

        recent_sessions = get_recent_chat_summaries(limit=3)
        if recent_sessions:
            _render_html_block("""
            <div class="custom-card" style="margin-top: 1.5rem;">
                <h4 style="margin-bottom: 0.5rem;">Continue a Conversation</h4>
                <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0;">
                    Jump back into your most recent chats.
                </p>
            </div>
            """)

            for idx, session in enumerate(recent_sessions):
                session_cols = st.columns([0.7, 0.3], gap="small")
                with session_cols[0]:
                    st.markdown(f"**{session['name']}**")
                    st.caption(session["preview"])
                    st.caption(f"Updated {session['updated_display']}")
                with session_cols[1]:
                    if st.button("Resume", key=f"resume_chat_{idx}", use_container_width=True):
                        if "chat_sessions" not in st.session_state:
                            st.session_state.chat_sessions = load_chat_sessions()
                        if session["name"] in st.session_state.chat_sessions:
                            st.session_state.current_chat = session["name"]
                        st.session_state.page = 'chat'
                        st.rerun()

    render_footer()
