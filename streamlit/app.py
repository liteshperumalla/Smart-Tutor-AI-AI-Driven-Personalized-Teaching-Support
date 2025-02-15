import streamlit as st

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
    search_query = st.text_input("Enter your query", placeholder="Type here...")
    if st.button("Search"):
        # In a real app, you would call your search or query function here.
        st.write(f"Results for: **{search_query}**")

# Additional Course Info or Welcome Message
st.markdown("---")
st.write("Welcome to the course! Use the sidebar to navigate through the resources.")
