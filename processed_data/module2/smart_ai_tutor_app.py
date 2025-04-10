import streamlit as st
import os
import time
from llama_index.core import StorageContext, load_index_from_storage, get_response_synthesizer
from Tutor_chat import RAGQueryEngine

# ---------- MUST BE FIRST STREAMLIT COMMAND ----------
st.set_page_config(page_title="Smart AI Tutor", page_icon="🎓", layout="wide")

# ---------- CONFIG ----------
persist_dir = "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/persisted_index"
storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

def is_greeting(message):
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "greetings"]
    return any(message.lower().strip().startswith(greet) for greet in greetings)

def store_query(query):
    with open("query_log.txt", "a") as file:
        file.write(query + "\n")        

def generate_response_with_sources(query):
    try:
        index = load_index_from_storage(storage_context)
        retriever = index.as_retriever()
        synthesizer = get_response_synthesizer(response_mode="compact")
        nodes = retriever.retrieve(query)

        file_links = list(set([
            (
                os.path.basename(node.metadata.get("file_path", "Unknown.pdf")),
                node.metadata.get("file_path", "")
            )
            for node in nodes if hasattr(node, "metadata") and "file_path" in node.metadata
        ]))

        query_engine = RAGQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
        response = query_engine.query(query)
        return str(response), file_links

    except Exception as e:
        return f"⚠️ Error: {str(e)}", []

# ---------- HOMEPAGE ----------
def home():
    st.markdown("""
    <style>
        .main-title {
            font-size: 2.7em;
            font-weight: 800;
            color: white;
            margin-bottom: 5px;
        }
        .subtitle {
            font-size: 1.2em;
            color: #00e676; /* bright green */
            margin-bottom: 5px;
        }
        hr {
            border: none;
            height: 2px;
            background-color: #ccc;
            margin-bottom: 20px;
        }
        .announcement-scroll {
            max-height: 120px;
            overflow-y: auto;
            padding: 15px;
            background-color: #ffebee;
            border-left: 6px solid #d32f2f;
            border-radius: 8px;
            color: #b71c1c;
            font-weight: 500;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .highlight {
            color: #d50000;
        }
        .start-button {
            margin-top: 20px;
            text-align: center;
        }
        .stButton>button {
            background-color: #1e88e5;
            color: white;
            font-size: 1em;
            padding: 10px 20px;
            border-radius: 10px;
            border: none;
            transition: background-color 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #1565c0;
            cursor: pointer;
        }
    </style>

    <div style='text-align: center;'>
        <div class='main-title'>📘 INFO 5731 - Computational Methods</div>
        <div class='subtitle'>University of North Texas | Fall 2025</div>
    </div>
    <hr>
    """, unsafe_allow_html=True)


    
        # Create layout with empty space on the left, professor on the right
    col1, col2 = st.columns([3, 1])  # Wider left column, smaller right column

    with col2:
        st.markdown("### 👨‍🏫 Professor")
        st.write("**Dr. Haihua Chen**")
        st.markdown("[LinkedIn](https://www.linkedin.com/in/haihua-chen/)  \n[Google Scholar](https://scholar.google.com)")


        
    st.markdown("<div class='announcement-scroll'>"
                "📢 <b>Latest Announcements</b><br><br>"
                "<p><b>April 8, 2025:</b> Assignment 3 released. Due by April 15.</p>"
                "<p class='highlight'><b>[Reminder]</b> Extra Credit Opportunity – Health Informatics Lecture Series: "
                "<i>Cybersecurity in Modern Healthcare</i> <b>[April 9, 2025]</b></p>"
                "<p><b>April 5, 2025:</b> Lecture notes updated in the course folder.</p>"
                "</div>", unsafe_allow_html=True)

    # Course Topics below
    st.markdown("### 📚 Course Topics")
    st.write("""
    - Python & Scientific Computing  
    - Machine Learning Foundations  
    - Web Scraping and Data Collection  
    - Natural Language Processing  
    - LLMs, RAG, & Topic Modelling  
    """)

    # Start Button (center)
    st.markdown("""<div class='start-button'>""", unsafe_allow_html=True)
    if st.button("🚀 Start Chat with Smart AI Tutor"):
        st.session_state.page = "chat"
    st.markdown("""</div>""", unsafe_allow_html=True)


# ---------- CHATBOT ----------
def chatbot():
    st.title("🤖 Smart AI Tutor")
    if st.button("⬅️ Back to Home"):
        st.session_state.page = "home"
        st.rerun()

    st.subheader("Ask your questions from INFO 5731 course materials")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg_index, entry in enumerate(st.session_state.chat_history):
        role = entry["role"]
        content = entry["content"]
        sources = entry.get("sources", [])

        if role == "user":
            st.markdown(f"**🧑 You:** {content}")
        elif role == "assistant":
            st.markdown(f"**🤖 Assistant:** {content}")
            if sources and not is_greeting(st.session_state.chat_history[msg_index - 1]["content"]):
                st.markdown("**📂 Source File(s) Used:**")
                for i, (file_name, file_path) in enumerate(sources):
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label=f"Download {file_name}",
                                data=f,
                                file_name=file_name,
                                mime="application/octet-stream",
                                key=f"download-history-{msg_index}-{i}"
                            )
                    else:
                        st.warning(f"⚠️ File not found: {file_name}")

    st.markdown("---")

    user_input = st.chat_input("Ask your question...")
    if user_input:
        store_query(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Generating resources, finding files..."):
                response_text, source_files = generate_response_with_sources(user_input)

                response_placeholder = st.empty()
                streamed_response = ""
                for word in response_text.split():
                    streamed_response += word + " "
                    response_placeholder.markdown(streamed_response + "▌")
                    time.sleep(0.03)
                response_placeholder.markdown(streamed_response.strip())

                if source_files and not is_greeting(user_input):
                    st.markdown("**📂 Source File(s) Used:**")
                    for i, (file_name, file_path) in enumerate(source_files):
                        if os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    label=f"Download {file_name}",
                                    data=f,
                                    file_name=file_name,
                                    mime="application/octet-stream",
                                    key=f"download-current-{i}"
                                )
                        else:
                            st.warning(f"⚠️ File not found: {file_name}")

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response_text,
            "sources": source_files
        })
        
        # 📅 Teams Appointment Form Button (add below chat input)
    
    # Initialize session states
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    if "form_submitted" not in st.session_state:
        st.session_state.form_submitted = False

    # Button to trigger the form
    if st.button("📅 Book Teams Appointment"):
        st.session_state.show_form = True
        st.session_state.form_submitted = False  # Reset on each new form request

    # Show form only if triggered and not yet submitted
    if st.session_state.show_form and not st.session_state.form_submitted:
        with st.form("appointment_form"):
            # Inside your form
            name = st.text_input("Your Name")
            email = st.text_input("Your Email")
            date = st.date_input("Preferred Date")
            preferred_time = st.time_input("Preferred Time")  # ✅ FIXED NAME
            reason = st.text_area("Reason for the Meeting (Optional)")


            submitted = st.form_submit_button("Submit Request")

            if submitted:
                st.session_state.form_submitted = True  # ✅ Hide form after submission
                st.success("✅ Appointment request submitted. The team will reach out via Teams.")

    # Optional: Show message if submitted and revisited
    elif st.session_state.form_submitted:
        st.success("✅ Appointment request already submitted.")

                           

# ---------- APP ROUTING ----------
if "page" not in st.session_state:
    st.session_state.page = "home"

if st.session_state.page == "home":
    home()
elif st.session_state.page == "chat":
    chatbot()
