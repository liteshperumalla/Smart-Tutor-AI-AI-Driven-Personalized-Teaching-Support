import streamlit as st
from utils import render_footer
import auth
auth.initialize_session()

def render():
    """Renders the home page with beautiful UI elements."""
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        color: white !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 1px solid #333;
    }
    
    .main-title {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        margin-bottom: 0.5rem !important;
        color: #ffffff !important;
    }
    
    .subtitle {
        font-size: 1.2rem !important;
        opacity: 0.8;
        font-weight: 300 !important;
        color: #ffffff !important;
    }
    
    .course-code {
        font-size: 1.1rem !important;
        background: rgba(255,255,255,0.1);
        padding: 0.5rem 1rem;
        border-radius: 25px;
        display: inline-block;
        margin-top: 1rem;
        border: 1px solid rgba(255,255,255,0.2);
        color: white !important;
    }
    
    .announcement-card {
        background: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 15px !important;
        padding: 2rem !important;
        margin-bottom: 2rem !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .announcement-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    
    .announcement-header {
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        color: #000000 !important;
        margin-bottom: 1.5rem !important;
        border-bottom: 2px solid #000000;
        padding-bottom: 0.5rem;
    }
    
    .announcement-item {
        background: #f8f8f8 !important;
        padding: 1rem !important;
        border-radius: 8px !important;
        margin-bottom: 1rem !important;
        border-left: 4px solid #000000 !important;
        transition: all 0.3s ease;
        color: #000000 !important;
    }
    
    .announcement-item:hover {
        background: #f0f0f0 !important;
        transform: translateX(5px);
    }
    
    .announcement-date {
        font-weight: 600 !important;
        color: #000000 !important;
    }
    
    .reminder-item {
        background: #000000 !important;
        color: white !important;
        padding: 1rem !important;
        border-radius: 8px !important;
        margin-bottom: 1rem !important;
        border: 2px solid #333 !important;
    }
    
    .topics-card {
        background: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 15px !important;
        padding: 2rem !important;
        transition: transform 0.3s ease;
    }
    
    .topics-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    
    .topics-header {
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        color: #000000 !important;
        margin-bottom: 1.5rem !important;
        text-align: center;
        border-bottom: 2px solid #000000;
        padding-bottom: 0.5rem;
    }
    
    .topic-item {
        background: #f8f8f8 !important;
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        padding: 1rem !important;
        margin-bottom: 0.8rem !important;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .topic-item::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: #000000;
        transition: width 0.3s ease;
        border-radius: 8px 0 0 8px;
    }
    
    .topic-item:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-color: #000000 !important;
        background: #f0f0f0 !important;
    }
    
    .topic-item:hover::before {
        width: 100%;
        opacity: 0.05;
    }
    
    .topic-link {
        color: #000000 !important;
        text-decoration: none !important;
        font-weight: 500 !important;
        display: block;
        position: relative;
        z-index: 1;
    }
    
    .topic-link:hover {
        color: #333 !important;
        text-decoration: none !important;
    }
    
    .professor-card {
        background: #000000 !important;
        color: white !important;
        border: 2px solid #333 !important;
        border-radius: 15px !important;
        padding: 2rem !important;
        text-align: center;
    }
    
    .professor-title {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        margin-bottom: 1rem !important;
        border-bottom: 1px solid #333;
        padding-bottom: 0.5rem;
        color: #ffffff !important;
    }
    
    .professor-name {
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        margin-bottom: 1.5rem !important;
        color: #ffffff !important;
    }
    
    .professor-link {
        color: white !important;
        text-decoration: none !important;
        margin: 0 0.5rem;
        padding: 0.5rem 1rem;
        border: 2px solid white;
        border-radius: 5px;
        transition: all 0.3s ease;
        display: inline-block;
    }
    
    .professor-link:hover {
        background: white !important;
        color: black !important;
        text-decoration: none !important;
    }
    
    .stats-container {
        display: flex !important;
        gap: 1rem;
        margin: 2rem 0 !important;
        flex-wrap: wrap;
    }
    
    .stat-card {
        background: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        text-align: center !important;
        flex: 1;
        min-width: 200px;
        transition: transform 0.3s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .stat-number {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #000000 !important;
        display: block;
    }
    
    .stat-label {
        color: #666 !important;
        font-size: 0.9rem !important;
        margin-top: 0.5rem !important;
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .fade-in {
        animation: fadeIn 0.8s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Override Streamlit's default styles */
    .stMarkdown > div {
        color: inherit !important;
    }
    
    /* Hide Streamlit's default margin */
    .block-container {
        padding-top: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Main header with gradient background
    st.markdown("""
    <div class='main-header fade-in'>
        <h1 class='main-title'>🎓 Smart AI Tutor</h1>
        <div class='subtitle'>Advanced Computational Methods for Information Science</div>
        <div class='course-code'>INFO 5731 | UNT Fall 2025</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Statistics cards
    st.markdown("""
    <div class='stats-container fade-in'>
        <div class='stat-card'>
            <span class='stat-number'>11</span>
            <div class='stat-label'>Course Topics</div>
        </div>
        <div class='stat-card'>
            <span class='stat-number'>15</span>
            <div class='stat-label'>Weeks</div>
        </div>
        <div class='stat-card'>
            <span class='stat-number'>100%</span>
            <div class='stat-label'>Success Rate</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Main content columns
    c1, c2 = st.columns([3, 1], gap="large")
    
    with c1:
        # Announcements section
        st.markdown("""
        <div class='announcement-card fade-in'>
            <div class='announcement-header'>
                📢 Latest Announcements
            </div>
            
            <div class='announcement-item'>
                <div class='announcement-date'>April 8, 2025:</div>
                <div style='margin-top: 0.5rem;'>Assignment 3 has been released. Please submit by April 15th. Check Canvas for detailed requirements.</div>
            </div>
            
            <div class='reminder-item pulse'>
                <div style='font-weight: 600; margin-bottom: 0.5rem;'>🔔 Reminder - Extra Credit Opportunity</div>
                <div><strong>Health Informatics Lecture Series:</strong> <em>Cybersecurity in Modern Healthcare</em></div>
                <div style='margin-top: 0.5rem; font-size: 0.9rem;'>📅 April 9, 2025 | Don't miss this valuable learning opportunity!</div>
            </div>
            
            <div class='announcement-item'>
                <div class='announcement-date'>April 5, 2025:</div>
                <div style='margin-top: 0.5rem;'>Lecture notes have been updated with additional examples and clarifications.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Course topics section
        st.markdown("""
        <div class='topics-card fade-in'>
            <div class='topics-header'>📚 Course Topics</div>
        """, unsafe_allow_html=True)
        
        # Course topics as individual components
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
            <div class='topic-item'>
                <a href='{topic_url}' target='_blank' class='topic-link'>
                    {topic_name}
                </a>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with c2:
        # Professor card
        st.markdown("""
        <div class='professor-card fade-in'>
            <h4 class='professor-title'>Professor</h4>
            <div class='professor-name'>Dr. Haihua Chen</div>
            <div class='professor-links'>
                <a href='https://www.linkedin.com/in/haihua-chen/' target='_blank' class='professor-link'>
                    LinkedIn
                </a><br><br>
                <a href='https://scholar.google.com/citations?user=URmnWAQAAAAJ' target='_blank' class='professor-link'>
                    Google Scholar
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    render_footer()