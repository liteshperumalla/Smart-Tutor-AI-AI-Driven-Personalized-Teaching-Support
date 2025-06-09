import streamlit as st
import os
import json
import re
from utils import load_chat_sessions, save_chat_session, sanitize_filename
import auth
auth.initialize_session()
auth.display_logout_button()

def sidebar_content():
    """Renders the sidebar content and handles navigation."""
    with st.sidebar:
        st.markdown("### Navigation")
        # Navigation buttons
        pages_navigation = {
            "Home": "home",
            "Research Mode": "Research Mode",
            "Quiz Generator": "quizgenerator",
            "Schedule Appointment": "scheduleappointment",
            "Resources": "Resources",
            "About": "About",
            "Feedback And Bug Report": "Feedback And Bug Report",
        }
        for label, page_key in pages_navigation.items():
            if st.button(label, key=f"nav_{page_key}"): # Added unique keys for nav buttons
                st.session_state.page = page_key
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### Chats")

        # Initialize chat session state if not already done (e.g. by app.py)
        if "chat_sessions" not in st.session_state:
            st.session_state.chat_sessions = load_chat_sessions()
        if "current_chat" not in st.session_state:
            # Ensure 'Default' chat session exists if it's the initial current_chat
            if "Default" not in st.session_state.chat_sessions:
                 st.session_state.chat_sessions["Default"] = []
            st.session_state.current_chat = "Default"

        if "open_menu" not in st.session_state:
            st.session_state.open_menu = None

        # “New Chat” button
        if st.button("➕ New Chat"):
            # Find a unique new chat name
            i = 1
            while f"Session {i}" in st.session_state.chat_sessions:
                i += 1
            name = f"Session {i}"

            st.session_state.chat_sessions[name] = []
            st.session_state.current_chat = name
            save_chat_session(name, [])
            st.session_state.page = 'chat' # Switch to chat page on new chat
            st.session_state.open_menu = None
            st.rerun()

        # Build list: current first
        current = st.session_state.current_chat
        # Ensure current chat exists, if not, reset to Default or first available
        if current not in st.session_state.chat_sessions:
            if "Default" in st.session_state.chat_sessions:
                st.session_state.current_chat = "Default"
            elif st.session_state.chat_sessions:
                st.session_state.current_chat = list(st.session_state.chat_sessions.keys())[0]
            else: # No chats exist, create Default
                st.session_state.chat_sessions["Default"] = []
                st.session_state.current_chat = "Default"
            current = st.session_state.current_chat


        names = [current] + [n for n in st.session_state.chat_sessions if n != current and n is not None]
        # Filter out None if it somehow gets in
        names = [n for n in names if n is not None]


        # Render each session with inline menu
        for name in names:
            if name is None: continue # Skip if name is None

            is_current = (name == st.session_state.current_chat)

            # Main row: session button + three‐dots
            with st.container():
                col1, col2 = st.columns([0.8, 0.2], gap="small") # Adjusted column ratio
                with col1:
                    # Use a unique key for each chat button
                    if st.button(name, key=f"chat_select_{name}", use_container_width=True):
                        st.session_state.current_chat = name
                        st.session_state.page = 'chat' # Switch to chat page
                        st.session_state.open_menu = None
                        st.rerun()
                    if is_current:
                        st.markdown(
                            f"<style>div[data-testid='stButton-button']:has(span:contains('{name}')) {{background-color:#eef9ff; font-weight:bold; border: 1px solid #ade8f4 !important;}}</style>",
                            unsafe_allow_html=True,
                        )
                with col2:
                    if st.button("⋮", key=f"menu_toggle_{name}"):
                        st.session_state.open_menu = None if st.session_state.open_menu == name else name

                # Inline submenu if open
                if st.session_state.open_menu == name:
                    subcol1, subcol2, subcol3 = st.columns([0.6, 0.2, 0.2], gap="small") # Adjusted ratio
                    with subcol1:
                        new_name_input = st.text_input(
                            "New name", value=name, key=f"rename_input_{name}",
                            label_visibility="collapsed"
                        )
                    with subcol2:
                        if st.button("✔️", key=f"confirm_rename_{name}", help="Save new name"):
                            if new_name_input and new_name_input != name:
                                sessions = st.session_state.chat_sessions
                                if new_name_input not in sessions: # Ensure new name is unique
                                    # Preserve history and delete old file before saving new one
                                    history_to_move = sessions.pop(name)
                                    old_chat_path = os.path.join("previous_chats", f"{sanitize_filename(name)}.json")
                                    if os.path.exists(old_chat_path):
                                        os.remove(old_chat_path)

                                    sessions[new_name_input] = history_to_move
                                    if st.session_state.current_chat == name:
                                        st.session_state.current_chat = new_name_input
                                    save_chat_session(new_name_input, sessions[new_name_input])
                                    st.session_state.open_menu = None
                                    st.rerun()
                                else:
                                    st.warning("Name already exists.")
                            else:
                                st.session_state.open_menu = None # Close if name is empty or unchanged
                                st.rerun()

                    with subcol3:
                        if st.button("🗑️", key=f"delete_chat_{name}", help="Delete chat"):
                            if name == "Default" and len(st.session_state.chat_sessions) == 1:
                                st.warning("Cannot delete the 'Default' chat when it's the only one.")
                            else:
                                sessions = st.session_state.chat_sessions
                                sessions.pop(name, None)
                                
                                # Delete file on disk
                                filepath = os.path.join("previous_chats", f"{sanitize_filename(name)}.json")
                                if os.path.exists(filepath):
                                    try:
                                        os.remove(filepath)
                                    except OSError as e:
                                        st.error(f"Error deleting chat file: {e}")

                                # Pick a new current chat
                                if st.session_state.current_chat == name:
                                    remaining_keys = list(sessions.keys())
                                    if "Default" in remaining_keys:
                                        st.session_state.current_chat = "Default"
                                    elif remaining_keys:
                                        st.session_state.current_chat = remaining_keys[0]
                                    else: # No chats left, create a new Default
                                        sessions["Default"] = []
                                        st.session_state.current_chat = "Default"
                                        save_chat_session("Default", [])
                                
                                st.session_state.open_menu = None
                                st.rerun()
        
        st.markdown("<hr>", unsafe_allow_html=True)
        st.checkbox("Dark Mode", key="dark_mode")