import streamlit as st
from sidebar import sidebar_content
from utils import BASE_CSS, LIGHT_MODE_CSS, DARK_MODE_CSS, load_chat_sessions # Added load_chat_sessions
from views import home, chat, appointment, research, quiz, resources, about, feedback

def main():
    st.set_page_config(page_title="Smart AI Tutor", page_icon="🎓", layout="wide")

    # Initialize session state
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False
    if 'page' not in st.session_state:
        st.session_state.page = 'home'

    # --- CHAT SESSION INITIALIZATION (Updated) ---
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = load_chat_sessions() # load_chat_sessions no longer auto-creates "Default"

    if not st.session_state.chat_sessions:
        # If NO saved chats were found by load_chat_sessions (e.g., first run or all chats deleted),
        # then create an in-memory "Default" session to start with.
        st.session_state.chat_sessions["Default"] = []
        st.session_state.current_chat = "Default"
    elif "current_chat" not in st.session_state or st.session_state.current_chat not in st.session_state.chat_sessions:
        if "Default" in st.session_state.chat_sessions:
            st.session_state.current_chat = "Default"
        else:
            # This ensures current_chat is always valid if any sessions exist
            st.session_state.current_chat = list(st.session_state.chat_sessions.keys())[0]
    # --- END OF CHAT SESSION INITIALIZATION UPDATE ---

    # Apply base CSS
    st.markdown(BASE_CSS, unsafe_allow_html=True)

    # Render sidebar and handle navigation
    sidebar_content()

    # Apply light/dark mode CSS
    st.markdown(DARK_MODE_CSS if st.session_state.dark_mode else LIGHT_MODE_CSS,
                unsafe_allow_html=True)

    # Page routing
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
