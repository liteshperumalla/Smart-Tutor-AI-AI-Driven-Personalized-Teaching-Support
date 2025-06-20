import streamlit as st
import time
import re
from html import escape
from pathlib import Path
import os 
import logging 
import auth
auth.initialize_session()

from utils import (
    generate_response_stream_and_sources, 
    make_session_title, 
    save_chat_session, 
    render_footer, 
    sanitize_filename 
)
try:
    from Tutor_chat import langfuse_client 
except ImportError:
    langfuse_client = None

def render():
    st.markdown("<h1 style='text-align:center; margin-bottom:0.2em;'>Smart AI Tutor 🎓</h1>", unsafe_allow_html=True)
    st.markdown("<p class='chat-subtitle' style='text-align:center;'>Ask your questions:</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:right;'>-Powered by Ollama.</p>", unsafe_allow_html=True)

    # --- CSS (Includes bubble styles, typing indicator, button styles, fixed input) ---
    st.markdown("""
    <style>
    /* Chat bubble and general styling */
    .user-bubble { 
        background:#cce5ff; padding:10px 15px; border-radius:15px; 
        margin:5px 10px; max-width:70%; text-align:left; 
        float:right; clear:both; box-shadow: 0 1px 3px rgba(0,0,0,0.1); 
        word-wrap: break-word; 
    }
    .assistant-bubble { 
        background:#d4edda; padding:10px 15px; border-radius:15px; 
        margin:5px 10px; max-width:70%; text-align:left; 
        float:left; clear:both; box-shadow: 0 1px 3px rgba(0,0,0,0.1); 
        word-wrap: break-word; 
    }
    .typing-indicator-bubble { 
        background:#e0e0e0; color: #555;
        padding:10px 15px; border-radius:15px; margin:5px 10px; 
        max-width:fit-content; text-align:left; float:left; clear:both; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .timestamp { 
        font-size:0.7em; color:gray; margin-top:3px; display:block; 
    }
    .timestamp-user { 
        text-align:right; margin-right:10px; margin-bottom: 5px;
    }
    .timestamp-assistant { 
        text-align:left; margin-left:10px; margin-bottom: 5px;
    }
    pre { 
        background:#282c34 !important; color:#abb2bf !important; 
        padding:10px !important; border-radius:8px !important; 
        overflow-x:auto !important; font-family: 'Courier New', Courier, monospace; 
        font-size: 0.9em; 
    }
    code { 
        background:#282c34 !important; color:#abb2bf !important; 
        padding:2px 4px !important; border-radius:4px !important; 
        font-family: 'Courier New', Courier, monospace;
    }
    
    .typing-indicator span {
        height: 8px; width: 8px; margin: 0 1px;
        background-color: #707070; border-radius: 50%;
        display: inline-block;
        animation: typing-bounce 1.4s infinite both;
    }
    .typing-indicator span:nth-child(1) { animation-delay: 0.0s; }
    .typing-indicator span:nth-child(2) { animation-delay: 0.4s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0.8s; }
    @keyframes typing-bounce { 
        0%, 80%, 100% { transform: scale(0); } 
        40% { transform: scale(1.0); } 
    }

    .source-buttons-group {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 10px 0;
        align-items: flex-start;
    }
    
    .source-button-container {
        flex: 0 1 auto;
        min-width: 200px;
        max-width: 300px;
    }
    
    /* Ensure buttons have consistent styling */
    .stDownloadButton > button {
        width: 100%;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 0.85rem;
        padding: 0.25rem 0.5rem;
        height: auto;
        min-height: 2.5rem;
    }

    /* Clear floats after chat messages */
    .chat-message-container::after {
        content: "";
        display: table;
        clear: both;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Session State & History Initialization ---
    if "chat_sessions" not in st.session_state: 
        st.session_state.chat_sessions = {"Default": []}
    if "current_chat" not in st.session_state or st.session_state.current_chat not in st.session_state.chat_sessions:
        if "Default" in st.session_state.chat_sessions: 
            st.session_state.current_chat = "Default"
        elif st.session_state.chat_sessions: 
            st.session_state.current_chat = list(st.session_state.chat_sessions.keys())[0]
        else: 
            st.session_state.chat_sessions["Default"] = []
            st.session_state.current_chat = "Default"
    
    # State for managing query processing and streaming
    if "user_query_to_process" not in st.session_state: 
        st.session_state.user_query_to_process = None
    if "assistant_response_streaming" not in st.session_state: 
        st.session_state.assistant_response_streaming = False
    if "assistant_response_final" not in st.session_state: 
        st.session_state.assistant_response_final = None
    if "assistant_sources_final" not in st.session_state: 
        st.session_state.assistant_sources_final = None

    history = st.session_state.chat_sessions[st.session_state.current_chat]
    
    # Callback when user submits input
    def on_user_input():
        query = st.session_state.chat_input_widget_key
        if query and query.strip():
            user_timestamp = time.strftime("%I:%M %p, %b %d", time.localtime()) 
            history.append({
                "role": "user", 
                "content": query.strip(), 
                "timestamp": user_timestamp
            })
            st.session_state.user_query_to_process = query.strip()
            st.session_state.assistant_response_streaming = True
            st.session_state.assistant_response_final = None 
            st.session_state.assistant_sources_final = None

    # --- Display Chat History & Handle Streaming ---
    chat_display_container = st.container() 
    with chat_display_container:
        seen_file_paths_for_download = set() 

        # Display existing chat history
        for msg_idx, msg_entry in enumerate(history): 
            if not isinstance(msg_entry, dict): 
                continue

            role = msg_entry.get("role")
            text_content = msg_entry.get("content", "")
            sources = msg_entry.get("sources", []) 
            timestamp = msg_entry.get("timestamp", "") 

            if not role: 
                continue

            # Create message container with proper clearing
            with st.container():
                st.markdown("<div class='chat-message-container'>", unsafe_allow_html=True)
                
                # Display message bubble
                bubble_class = "user-bubble" if role == "user" else "assistant-bubble"
                timestamp_class = "timestamp-user" if role == "user" else "timestamp-assistant"
                
                # Process text content with code block support
                html_content = process_text_with_code_blocks(text_content)
                
                st.markdown(f"<div class='{bubble_class}'>{html_content}</div>", unsafe_allow_html=True)
                
                if timestamp:
                    st.markdown(f"<div class='timestamp {timestamp_class}'>{timestamp}</div>", unsafe_allow_html=True)

                # Display source buttons for assistant messages
                if role == "assistant" and sources:
                    display_source_buttons(sources, msg_idx, seen_file_paths_for_download)
                
                st.markdown("</div>", unsafe_allow_html=True)  # Close chat-message-container
        
        # Show typing indicator while streaming
        if st.session_state.get("assistant_response_streaming") and not st.session_state.get("assistant_response_final"):
            with st.container():
                st.markdown("""
                <div class='chat-message-container'>
                    <div class='typing-indicator-bubble'>
                        <div class='typing-indicator'>
                            <span></span><span></span><span></span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # --- Process User Query and Stream Response ---
    if st.session_state.get("user_query_to_process"):
        query_to_process = st.session_state.user_query_to_process
        st.session_state.user_query_to_process = None

        # Get session info safely
        current_session_id = "unknown_session"
        try:
            if hasattr(st, 'runtime') and hasattr(st.runtime, 'scriptrunner'):
                ctx = st.runtime.scriptrunner.get_script_run_ctx()
                if ctx:
                    current_session_id = ctx.session_id
        except:
            pass
        
        current_user_id = "chat_user_main"

        # Process the query and get streaming response
        try:
            collected_response_text = ""
            response_generator, sources_from_llm = generate_response_stream_and_sources(
                query_to_process, 
                user_id=current_user_id, 
                session_id=current_session_id
            )
            
            # Create placeholder for streaming response
            streaming_placeholder = st.empty()
            
            # Stream the response
            for chunk in response_generator:
                collected_response_text += chunk
                # Show streaming with cursor
                html_content = process_text_with_code_blocks(collected_response_text)
                streaming_placeholder.markdown(f"""
                <div class='chat-message-container'>
                    <div class='assistant-bubble'>{html_content}▌</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Clear the streaming placeholder
            streaming_placeholder.empty()
            
            # Store final response
            st.session_state.assistant_response_streaming = False
            st.session_state.assistant_response_final = collected_response_text
            st.session_state.assistant_sources_final = sources_from_llm
            
            # Add to chat history
            assistant_timestamp = time.strftime("%I:%M %p, %b %d", time.localtime())
            history.append({
                "role": "assistant", 
                "content": collected_response_text, 
                "sources": sources_from_llm, 
                "timestamp": assistant_timestamp
            })
            
            # Handle session renaming and saving
            handle_session_management(history)
            
        except Exception as e:
            st.error(f"Error processing query: {str(e)}")
            logging.error(f"Chat processing error: {e}")
            st.session_state.assistant_response_streaming = False

        # Rerun to display the completed message
        st.rerun()

    # --- Chat Input Widget ---
    st.chat_input(
        "Ask me anything...", 
        key="chat_input_widget_key",
        on_submit=on_user_input,
        disabled=st.session_state.get("assistant_response_streaming", False) 
    )

    render_footer()


def process_text_with_code_blocks(text_content):
    """Process text content to handle code blocks and basic formatting."""
    escaped_parts = []
    last_end = 0
    
    # Handle code blocks
    for match in re.finditer(r"```(?:(\w+)\n)?([\s\S]*?)```", text_content, flags=re.DOTALL):
        start, end = match.span()
        # Add text before code block
        escaped_parts.append(escape(text_content[last_end:start]).replace("\n", "<br>"))
        # Add code block
        language = match.group(1) or ""
        code_content = escape(match.group(2))
        escaped_parts.append(f"<pre><code>{code_content}</code></pre>")
        last_end = end
    
    # Add remaining text
    escaped_parts.append(escape(text_content[last_end:]).replace("\n", "<br>"))
    return "".join(escaped_parts)


def display_source_buttons(sources, msg_idx, seen_file_paths):
    """Display source buttons for a message in an organized layout."""
    if not sources:
        return
    st.markdown("<div class='source-buttons-group'>", unsafe_allow_html=True)
    
    # Filter out duplicate file paths first
    unique_sources = []
    processed_paths = set()
    
    for src_data in sources:
        fpath = src_data.get("file_path", "")
        if fpath and fpath not in processed_paths and fpath not in seen_file_paths:
            unique_sources.append(src_data)
            processed_paths.add(fpath)
    
    # Create organized layout with proper columns
    if unique_sources:
        # Calculate optimal number of columns (2-4 depending on number of sources)
        num_sources = len(unique_sources)
        if num_sources <= 2:
            num_cols = num_sources
        elif num_sources <= 4:
            num_cols = 2
        else:
            num_cols = 3
            
        # Create rows of columns
        sources_per_row = num_cols
        for row_start in range(0, len(unique_sources), sources_per_row):
            row_sources = unique_sources[row_start:row_start + sources_per_row]
            cols = st.columns(len(row_sources))
            
            for col_idx, src_data in enumerate(row_sources):
                with cols[col_idx]:
                    fname = src_data.get("file_name", "source.file")
                    fpath = src_data.get("file_path", "")
                    
                    # Create download button
                    if fpath and os.path.exists(fpath):
                        try:
                            with open(fpath, "rb") as fp_read:
                                file_bytes = fp_read.read()
                            
                            # Create unique key
                            src_idx = row_start + col_idx
                            dl_key = f"dl_{msg_idx}_{src_idx}_{sanitize_filename(fname)}"
                            
                            # Format display name
                            display_name = fname[:25] + ('...' if len(fname) > 25 else '')
                            
                            # Add container div for consistent styling
                            st.markdown("<div class='source-button-container'>", unsafe_allow_html=True)
                            
                            st.download_button(
                                label=f"📄 {display_name}",
                                data=file_bytes,
                                file_name=fname,
                                mime="application/octet-stream",
                                key=dl_key,
                                help=f"Download: {fname}",
                                use_container_width=True
                            )
                            
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            # Mark as processed
                            seen_file_paths.add(fpath)
                            
                        except Exception as e:
                            logging.error(f"Download error for {fpath}: {e}")
                            # Show error state button
                            st.button(
                                f"❌ {fname[:20]}...",
                                disabled=True,
                                help=f"Error loading: {fname}",
                                use_container_width=True
                            )
    
    st.markdown("</div>", unsafe_allow_html=True)


def handle_session_management(history):
    """Handle session renaming and saving logic."""
    current_chat_name = st.session_state.current_chat
    sessions = st.session_state.chat_sessions
    
    # Check if we should rename the session
    should_rename = (
        (current_chat_name == "Default" and len(history) >= 3) or 
        (current_chat_name.startswith("Session ") and len(history) >= 3)
    )
    
    if should_rename:
        new_title_candidate = make_session_title(history)
        if (new_title_candidate and 
            new_title_candidate != current_chat_name and 
            new_title_candidate not in sessions):
            
            # Handle old chat file cleanup
            old_chat_path = Path(f"previous_chats/{sanitize_filename(current_chat_name)}.json")
            
            # Rename session
            sessions[new_title_candidate] = sessions.pop(current_chat_name)
            st.session_state.current_chat = new_title_candidate
            
            # Save new session
            save_chat_session(sanitize_filename(new_title_candidate), sessions[new_title_candidate])
            
            # Clean up old file if different
            if (old_chat_path.exists() and 
                sanitize_filename(current_chat_name) != sanitize_filename(new_title_candidate)):
                try: 
                    old_chat_path.unlink()
                except OSError as e: 
                    logging.warning(f"Could not delete old chat file {old_chat_path}: {e}")
        else:
            save_chat_session(sanitize_filename(current_chat_name), history)
    else:
        save_chat_session(sanitize_filename(current_chat_name), history)