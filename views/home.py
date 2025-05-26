import streamlit as st
from utils import render_footer # Assuming render_footer is in utils.py
import auth
auth.initialize_session()

def render():
    """Renders the home page."""
    st.markdown(
        "<div style='text-align:center;margin-bottom:10px;'>"
        "<h3>Welcome to Smart AI Tutor</h3>"
        "<div class='main-title'>INFO 5731 - Computational Methods</div>"
        "<div class='subtitle'>UNT | Fall 2025</div></div><hr>", # Assuming current year or relevant year
        unsafe_allow_html=True
    )
    c1, c2 = st.columns([3, 1], gap="large")
    with c1:
        st.markdown(
            """
            <div class='announcement-card'>
                <strong>📢 Latest Announcements</strong><br><br>
                <p><strong>April 8, 2025:</strong> Assignment 3 released. Due by April 15.</p>
                <p style='color:#d50000;'><strong>[Reminder]</strong> Extra Credit Opportunity – Health Informatics Lecture Series: <em>Cybersecurity in Modern Healthcare</em> <strong>[April 9, 2025]</strong></p>
                <p><strong>April 5, 2025:</strong> Lecture notes updated.</p>
            </div>
            """, unsafe_allow_html=True)
        st.markdown(
            """
            <div class='topics-card'>
                <h4 class='course-topics' style='margin-top:0;'>Course Topics</h4>
                <ul class='course-topics'>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-1-lecture-materials?module_item_id=7518917" target="_blank">Intro to Python</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-2-lecture-materials?module_item_id=7518922" target="_blank">Python Basics 1</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-3-lecture-materials?module_item_id=7518928" target="_blank">Python Basics 2</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-4-lecture-materials?module_item_id=7518935" target="_blank">Web scraping using python</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-5-lecture-materials?module_item_id=7518942" target="_blank">Data Cleaning and Data Quality</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-6-lecture-materials?module_item_id=7518949" target="_blank">Feature Extraction</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-7-lecture-materials?module_item_id=7815101" target="_blank">Word Embedding and Transformer</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-10-lecture-materials-2?module_item_id=7518962" target="_blank">Topic Modeling</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-12-lecture-materials?module_item_id=7518972" target="_blank">Sentiment Analysis</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-13-lecture-materials?module_item_id=7518976" target="_blank">Text Classification</a></li>
                    <li><a href="https://unt.instructure.com/courses/117821/pages/week-14-lecture-materials?module_item_id=7518981" target="_blank">Generative AI in Natural Language Processing</a></li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
    with c2:
        st.markdown(
            """
            <div class='professor-card'>
                <h4 class='professor-title'>Professor</h4>
                <p class='professor-name' style='font-size:20px; text-align:center;'>Dr. Haihua Chen</p>
                <p><a href='https://www.linkedin.com/in/haihua-chen/' target='_blank'>LinkedIn</a><br>
                <a href='https://scholar.google.com/citations?user=URmnWAQAAAAJ' target='_blank'>Google Scholar</a></p>
            </div>
            """, unsafe_allow_html=True)
    
    render_footer()
