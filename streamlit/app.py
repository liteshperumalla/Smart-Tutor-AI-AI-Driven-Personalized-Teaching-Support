import streamlit as st
import time


def store_query(query):
    """
    Store the query for logging or further processing.
    This is just a placeholder that writes to a file.
    """
    with open("query_log.txt", "a") as file:
        file.write(query + "\n")
    # You can add additional storage logic here (e.g., database)

def generate_response(query):
    """
    Generate a response based on the query.
    Replace this logic with your actual processing (e.g., RAG search).
    """
    # Simulate some processing delay
    time.sleep(2)
    return f"I did not find any resources for this : {query}. Please reframe your query"


# Set page configuration
st.set_page_config(
    page_title="5731 Computational Methods",
    page_icon="📚",
    layout="wide"
)

# Sidebar 
st.sidebar.header("Navigation")
st.sidebar.markdown("""
- Home
- About
- Resources
""")

# Main Header
st.title("INFO 5731 Computational Methods")
st.subheader("Professor Dr. Chen Haihua")

# Centered Search Bar: Use columns to center the search widget
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("### Search Course Resources")
    user_query = st.text_input("Enter your query", placeholder="Type here...")
    if st.button("Search"):
        # Store the query for later reference
        store_query(user_query)
        
        # Show a spinner while generating the response
        with st.spinner("Generating resources, finding files..."):
            response = generate_response(user_query)

# Additional Course Info or Welcome Message
st.markdown("---")
st.write("Welcome to the course! Use the sidebar to navigate through the resources.")
