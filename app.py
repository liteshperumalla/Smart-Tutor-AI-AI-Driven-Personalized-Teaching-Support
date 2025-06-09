import streamlit as st
from sidebar import sidebar_content
from utils import BASE_CSS, LIGHT_MODE_CSS, DARK_MODE_CSS, load_chat_sessions
from views import home, chat, appointment, research, quiz, resources, about, feedback
from auth import initialize_session, display_login_page, display_signup_page

def main():
    st.set_page_config(page_title="Smart AI Tutor", page_icon="🎓", layout="wide")

    # Initialize session state for authentication and general app state
    initialize_session() # Initializes 'authenticated', 'user_name', 'auth_page'

    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False
    if 'page' not in st.session_state: # For main app navigation
        st.session_state.page = 'home'


    # Apply base CSS - should be applied regardless of auth state for consistency
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    # Apply light/dark mode CSS - also global
    st.markdown(DARK_MODE_CSS if st.session_state.dark_mode else LIGHT_MODE_CSS,
                unsafe_allow_html=True)

    # Authentication Check
    if not st.session_state.get('authenticated', False):
        auth_page_to_display = st.session_state.get('auth_page', 'login')
        if auth_page_to_display == 'login':
            display_login_page()
        elif auth_page_to_display == 'signup':
            display_signup_page()
        else: # Default to login if auth_page is invalid
            st.session_state.auth_page = 'login'
            display_login_page()
        st.stop() # Stop further rendering if not authenticated

    # --- Authenticated App Content ---
    # --- CHAT SESSION INITIALIZATION (Moved here, only for authenticated users) ---
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = load_chat_sessions()

    if not st.session_state.chat_sessions:
        st.session_state.chat_sessions["Default"] = []
        st.session_state.current_chat = "Default"
    elif "current_chat" not in st.session_state or st.session_state.current_chat not in st.session_state.chat_sessions:
        if "Default" in st.session_state.chat_sessions:
            st.session_state.current_chat = "Default"
        else:
            st.session_state.current_chat = list(st.session_state.chat_sessions.keys())[0]
    # --- END OF CHAT SESSION INITIALIZATION ---

    # Render sidebar and handle navigation (Only if authenticated)
    sidebar_content()


    # Page routing (Only if authenticated)
    if st.session_state.page == 'home':
        home.render()
    elif st.session_state.page == 'chat':
        chat.render()
    elif st.session_state.page == 'scheduleappointment':
        appointment.render()
    elif st.session_state.page == 'Research Mode':
        research.render()
    elif st.session_state.page == 'quizgenerator':
        quiz.render()
    elif st.session_state.page == 'Resources':
        resources.render()
    elif st.session_state.page == 'About':
        about.render()
    elif st.session_state.page == 'Feedback And Bug Report':
        feedback.render()

if __name__ == '__main__':
    main()
