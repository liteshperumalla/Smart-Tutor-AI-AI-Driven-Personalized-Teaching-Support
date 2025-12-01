
import streamlit as st

def load_fonts():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        </style>
    """, unsafe_allow_html=True)

COMMON_STYLES = """
<style>
    /* Global Reset & Typography */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    p, div, span {
        font-family: 'Inter', sans-serif;
    }

    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }

    /* Button Styling Override */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
        border: 1px solid transparent;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }

    /* Input Fields */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        padding: 0.5rem 1rem;
    }
    .stTextInput > div > div > input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }

    /* Sidebar Button Styles */
    [data-testid="stSidebar"] button {
        background-color: transparent;
        color: inherit;
        border: 1px solid transparent;
        text-align: left;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        transition: all 0.2s ease;
        width: 100%;
        justify-content: flex-start;
    }
    
    [data-testid="stSidebar"] button:hover {
        background-color: rgba(0, 0, 0, 0.05);
        border-color: rgba(0, 0, 0, 0.1);
    }
    
    [data-testid="stSidebar"] button:focus {
        background-color: rgba(59, 130, 246, 0.1);
        color: #3b82f6;
        border-color: #3b82f6;
    }
</style>
"""

LIGHT_THEME = """
<style>
    :root {
        --bg-color: #f8fafc;
        --card-bg: #ffffff;
        --text-primary: #1e293b;
        --text-secondary: #64748b;
        --accent-color: #3b82f6;
        --border-color: #e2e8f0;
        --sidebar-bg: #ffffff;
    }

    /* App Background */
    .stApp {
        background-color: var(--bg-color);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid var(--border-color);
    }

    /* Text Colors */
    h1, h2, h3, h4, p, span, div {
        color: var(--text-primary);
    }
    
    .subtitle {
        color: var(--text-secondary) !important;
    }

    /* Cards */
    .custom-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        transition: all 0.3s ease;
    }
    
    .custom-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        transform: translateY(-2px);
    }

    /* Chat Bubbles */
    .user-bubble {
        background-color: #dbeafe; /* Blue 100 */
        color: #1e3a8a; /* Blue 900 */
        padding: 10px 15px;
        border-radius: 15px 15px 0 15px;
        margin: 5px 10px;
        max-width: 75%;
        text-align: left;
        float: right;
        clear: both;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        word-wrap: break-word;
    }
    
    .assistant-bubble {
        background-color: #f1f5f9; /* Slate 100 */
        color: #334155; /* Slate 700 */
        padding: 10px 15px;
        border-radius: 15px 15px 15px 0;
        margin: 5px 10px;
        max-width: 75%;
        text-align: left;
        float: left;
        clear: both;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        word-wrap: break-word;
    }

    .timestamp {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 4px;
        display: block;
    }
</style>
"""

DARK_THEME = """
<style>
    :root {
        --bg-color: #0f172a;
        --card-bg: #1e293b;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --accent-color: #60a5fa;
        --border-color: #334155;
        --sidebar-bg: #1e293b;
    }

    /* App Background */
    .stApp {
        background-color: var(--bg-color);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid var(--border-color);
    }

    /* Text Colors */
    h1, h2, h3, h4, p, span, div {
        color: var(--text-primary) !important;
    }
    
    .subtitle {
        color: var(--text-secondary) !important;
    }

    /* Cards */
    .custom-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    }

    /* Chat Bubbles */
    .user-bubble {
        background-color: #1e3a8a; /* Darker blue for dark mode */
        color: #e0f2fe;
        padding: 10px 15px;
        border-radius: 15px 15px 0 15px;
        margin: 5px 10px;
        max-width: 75%;
        text-align: left;
        float: right;
        clear: both;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        word-wrap: break-word;
    }
    
    .assistant-bubble {
        background-color: #334155; /* Slate 700 */
        color: #f1f5f9;
        padding: 10px 15px;
        border-radius: 15px 15px 15px 0;
        margin: 5px 10px;
        max-width: 75%;
        text-align: left;
        float: left;
        clear: both;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        word-wrap: break-word;
    }

    .timestamp {
        font-size: 0.75rem;
        color: #94a3b8;
        margin-top: 4px;
        display: block;
    }
</style>
"""

CHAT_STYLES = """
<style>
    /* Typing Indicator */
    .typing-indicator-bubble {
        background-color: var(--card-bg);
        padding: 10px 15px;
        border-radius: 15px;
        margin: 5px 10px;
        max-width: fit-content;
        float: left;
        clear: both;
        border: 1px solid var(--border-color);
    }

    .typing-indicator span {
        height: 8px;
        width: 8px;
        margin: 0 2px;
        background-color: var(--text-secondary);
        border-radius: 50%;
        display: inline-block;
        animation: typing-bounce 1.4s infinite both;
    }
    
    .typing-indicator span:nth-child(1) { animation-delay: 0s; }
    .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
    
    @keyframes typing-bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }

    /* Clearfix */
    .chat-message-container::after {
        content: "";
        display: table;
        clear: both;
    }
    
    .timestamp-user { text-align: right; margin-right: 10px; }
    .timestamp-assistant { text-align: left; margin-left: 10px; }

    /* Code Blocks */
    pre {
        background-color: #282c34 !important;
        color: #abb2bf !important;
        padding: 1rem !important;
        border-radius: 8px !important;
        overflow-x: auto !important;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.9em;
        margin: 0.5rem 0;
    }
    
    code {
        background-color: #282c34 !important;
        color: #abb2bf !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.9em;
    }
</style>
"""

def apply_custom_styles(dark_mode=False):
    load_fonts()
    st.markdown(COMMON_STYLES, unsafe_allow_html=True)
    st.markdown(CHAT_STYLES, unsafe_allow_html=True) # Apply chat styles globally
    if dark_mode:
        st.markdown(DARK_THEME, unsafe_allow_html=True)
    else:
        st.markdown(LIGHT_THEME, unsafe_allow_html=True)
