import streamlit as st
import os
import json
import re
from datetime import datetime, timezone # Added
from utils import load_chat_sessions, save_chat_session, sanitize_filename
# Assuming load_chat_sessions now returns Dict[str, {'history': List, 'last_message_timestamp': datetime}]
import auth

auth.initialize_session()
auth.display_logout_button()

def sidebar_content():
    """Renders the sidebar content and handles navigation."""
    with st.sidebar:
        st.markdown("### Navigation")
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
            if st.button(label, key=f"nav_{page_key}"):
                st.session_state.page = page_key
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### Chats")

        # Initialize chat session state if not already done.
        # Assumes load_chat_sessions() now returns the new rich structure.
        if "chat_sessions" not in st.session_state:
            st.session_state.chat_sessions = load_chat_sessions()

        # Ensure 'Default' chat session exists with the new structure if no sessions were loaded.
        if not st.session_state.chat_sessions:
            st.session_state.chat_sessions["Default"] = {
                "history": [],
                "last_message_timestamp": datetime.now(timezone.utc)
            }

        if "current_chat" not in st.session_state or st.session_state.current_chat not in st.session_state.chat_sessions:
            if "Default" in st.session_state.chat_sessions:
                st.session_state.current_chat = "Default"
            elif st.session_state.chat_sessions: # Pick first available if Default somehow isn't there
                st.session_state.current_chat = next(iter(st.session_state.chat_sessions))
            else: # Absolute fallback: create Default if chat_sessions is totally empty
                st.session_state.chat_sessions["Default"] = {
                    "history": [],
                    "last_message_timestamp": datetime.now(timezone.utc)
                }
                st.session_state.current_chat = "Default"

        if "open_menu" not in st.session_state:
            st.session_state.open_menu = None

        # “New Chat” button
        if st.button("➕ New Chat"):
            i = 1
            while f"Session {i}" in st.session_state.chat_sessions:
                i += 1
            name = f"Session {i}"

            # Create new session with the rich structure
            st.session_state.chat_sessions[name] = {
                "history": [],
                "last_message_timestamp": datetime.now(timezone.utc) # New chats are most recent
            }
            st.session_state.current_chat = name
            save_chat_session(name, []) # save_chat_session expects just the history list
            st.session_state.page = 'chat'
            st.session_state.open_menu = None
            st.rerun()

        # --- Sorting Logic ---
        current_chat_name = st.session_state.current_chat

        session_items_for_sorting = []
        for name, data_dict in st.session_state.chat_sessions.items():
            if name and isinstance(data_dict, dict) and 'last_message_timestamp' in data_dict:
                session_items_for_sorting.append({'name': name, 'timestamp': data_dict['last_message_timestamp']})
            elif name: # Fallback for robustness if data is not as expected
                session_items_for_sorting.append({'name': name, 'timestamp': datetime.min.replace(tzinfo=timezone.utc)})

        current_chat_item = None
        other_chat_items = []

        for item in session_items_for_sorting:
            if item['name'] == current_chat_name:
                current_chat_item = item
            else:
                other_chat_items.append(item)

        other_chat_items.sort(key=lambda x: x['timestamp'], reverse=True)

        ordered_session_names = []
        if current_chat_item:
            ordered_session_names.append(current_chat_item['name'])

        for item in other_chat_items:
            if item['name'] not in ordered_session_names:
                ordered_session_names.append(item['name'])

        if current_chat_name in st.session_state.chat_sessions and current_chat_name not in ordered_session_names:
            ordered_session_names.insert(0, current_chat_name)

        if not ordered_session_names: # Should not happen if Default is always created
             if "Default" not in st.session_state.chat_sessions: # Ensure Default truly exists
                  st.session_state.chat_sessions["Default"] = {"history": [], "last_message_timestamp": datetime.now(timezone.utc)}
             st.session_state.current_chat = "Default" # Select it
             ordered_session_names = ["Default"]


        # Render each session with inline menu using ordered_session_names
        for name in ordered_session_names:
            if name is None: continue

            is_current = (name == st.session_state.current_chat)
            with st.container():
                col1, col2 = st.columns([0.8, 0.2], gap="small")
                with col1:
                    if st.button(name, key=f"chat_select_{name}", use_container_width=True):
                        st.session_state.current_chat = name
                        st.session_state.page = 'chat'
                        st.session_state.open_menu = None
                        # Clear query processing flags when switching chats
                        st.session_state.user_query_to_process = None
                        st.session_state.assistant_response_streaming = False
                        st.session_state.assistant_response_final = None
                        st.session_state.assistant_sources_final = None
                        st.rerun()
                    if is_current:
                        st.markdown(
                            f"<style>div[data-testid='stButton-button']:has(span:contains('{name}')) {{background-color:#eef9ff; font-weight:bold; border: 1px solid #ade8f4 !important;}}</style>",
                            unsafe_allow_html=True,
                        )
                with col2:
                    if st.button("⋮", key=f"menu_toggle_{name}"):
                        st.session_state.open_menu = None if st.session_state.open_menu == name else name

                if st.session_state.open_menu == name:
                    subcol1, subcol2, subcol3 = st.columns([0.6, 0.2, 0.2], gap="small")
                    with subcol1:
                        new_name_input = st.text_input(
                            "New name", value=name, key=f"rename_input_{name}",
                            label_visibility="collapsed"
                        )
                    with subcol2:
                        if st.button("✔️", key=f"confirm_rename_{name}", help="Save new name"):
                            if new_name_input and new_name_input != name:
                                sessions = st.session_state.chat_sessions
                                if new_name_input not in sessions:
                                    # Preserve history and timestamp, delete old file
                                    session_data_to_move = sessions.pop(name) # This is the dict {'history': ..., 'timestamp': ...}
                                    old_chat_path = os.path.join("previous_chats", f"{sanitize_filename(name)}.json")
                                    if os.path.exists(old_chat_path):
                                        os.remove(old_chat_path)

                                    sessions[new_name_input] = session_data_to_move # Assign the whole dict
                                    if st.session_state.current_chat == name:
                                        st.session_state.current_chat = new_name_input
                                    # save_chat_session expects only the history list
                                    save_chat_session(new_name_input, sessions[new_name_input]['history'])
                                    st.session_state.open_menu = None
                                    st.rerun()
                                else:
                                    st.warning("Name already exists.")
                            else:
                                st.session_state.open_menu = None
                                st.rerun()

                    with subcol3:
                        if st.button("🗑️", key=f"delete_chat_{name}", help="Delete chat"):
                            if name == "Default" and len(st.session_state.chat_sessions) == 1:
                                st.warning("Cannot delete the 'Default' chat when it's the only one.")
                            else:
                                sessions = st.session_state.chat_sessions
                                sessions.pop(name, None)
                                
                                filepath = os.path.join("previous_chats", f"{sanitize_filename(name)}.json")
                                if os.path.exists(filepath):
                                    try:
                                        os.remove(filepath)
                                    except OSError as e:
                                        st.error(f"Error deleting chat file: {e}")

                                if st.session_state.current_chat == name:
                                    remaining_keys = list(sessions.keys())
                                    if "Default" in remaining_keys:
                                        st.session_state.current_chat = "Default"
                                    elif remaining_keys:
                                        st.session_state.current_chat = remaining_keys[0]
                                    else:
                                        sessions["Default"] = { # Recreate with new structure
                                            "history": [],
                                            "last_message_timestamp": datetime.now(timezone.utc)
                                        }
                                        st.session_state.current_chat = "Default"
                                        save_chat_session("Default", []) # Save history list
                                
                                st.session_state.open_menu = None
                                st.rerun()
        
        st.markdown("<hr>", unsafe_allow_html=True)
        st.checkbox("Dark Mode", key="dark_mode")

# If run as a script for testing sidebar independently (optional)
if __name__ == "__main__":
    # Minimal setup for st.session_state for standalone sidebar testing
    if "chat_sessions" not in st.session_state:
        # Mocking the new structure for testing
        st.session_state.chat_sessions = {
            "Default": {"history": [{"role": "user", "content": "Hello"}], "last_message_timestamp": datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)},
            "Session 1": {"history": [{"role": "user", "content": "Test"}], "last_message_timestamp": datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)}
        }
    if "current_chat" not in st.session_state:
        st.session_state.current_chat = "Default"
    if "page" not in st.session_state:
        st.session_state.page = "home"

    sidebar_content()
    st.write(f"Current Page: {st.session_state.page}")
    st.write(f"Current Chat: {st.session_state.current_chat}")
    st.write("Chat Sessions State:", st.session_state.chat_sessions)
