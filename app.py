import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from sidebar import sidebar_content
from utils import BASE_CSS, LIGHT_MODE_CSS, DARK_MODE_CSS, load_chat_sessions
from views import home, chat, appointment, research, quiz, resources, about, feedback, profile as profile_view, code # Added profile_view
from auth import initialize_session, display_login_page, display_signup_page
from user_management import get_user # Added get_user

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
    # NOTE: Light/dark mode CSS application is moved down, after theme preference is loaded.

    # Authentication Check
    if not st.session_state.get('authenticated', False):
        auth_page_to_display = st.session_state.get('auth_page', 'login')
        if auth_page_to_display == 'login':
            display_login_page()
            st.stop()  # ✅ STOP right after showing login page
        elif auth_page_to_display == 'signup':
            display_signup_page()
            st.stop()  # ✅ STOP here too
        else:
            st.session_state.auth_page = 'login'
            display_login_page()
            st.stop()  # ✅ And stop in fallback case too

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
    sidebar_content() # sidebar_content itself will call display_logout_button

    # Initialize dark_mode from user preference IF NOT ALREADY SET by theme toggle on profile page
    # This flag ensures that if a user toggles the theme on the profile page,
    # it's not immediately overridden by their saved preference on the next rerun within that session.
    # The flag is reset on new login (in auth.py) to load the preference for the new user.
    if 'dark_mode_initialized_from_user_preference' not in st.session_state and st.session_state.get('authenticated', False):
        current_username = st.session_state.get("user_name")
        if current_username:
            user_data = get_user(current_username)
            if user_data:
                user_theme = user_data.get('theme', 'light')
                st.session_state.dark_mode = (user_theme == 'dark')
                st.session_state.dark_mode_initialized_from_user_preference = True
            else: # User data couldn't be fetched, default to light and don't set flag
                st.session_state.dark_mode = False
        else: # No username, default to light and don't set flag
            st.session_state.dark_mode = False

    # Apply light/dark mode CSS - now uses potentially user-set theme
    st.markdown(DARK_MODE_CSS if st.session_state.get('dark_mode', False) else LIGHT_MODE_CSS,
                unsafe_allow_html=True)

    # Page routing (Only if authenticated)
    if st.session_state.page == 'home':
        home.render()
    elif st.session_state.page == 'chat':
        chat.render()
    elif st.session_state.page == 'code':
        code.render()
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
    elif st.session_state.page == 'profile': # Added profile route
        profile_view.render()

if __name__ == '__main__':
    main()