import streamlit as st
import datetime # For timestamping feedback and bug reports
import os # For file operations
from utils import render_footer # Assuming render_footer is in utils.py
import auth
auth.initialize_session()

# Define paths for storing feedback and bug reports
FEEDBACK_LOG_FILE = "feedback_log.txt"
BUG_REPORTS_LOG_FILE = "bug_reports_log.txt"

def render():
    """Renders the Feedback and Bug Report page."""
    st.title("📣 Feedback and Bug Report")
    st.markdown("We value your input! Help us improve the **Smart AI Tutor** by sharing your feedback or reporting any issues you encounter.")

    tab1, tab2 = st.tabs(["📝 Give General Feedback", "🐛 Report a Bug"])

    # --- General Feedback Tab ---
    with tab1:
        st.subheader("Share Your Thoughts")
        st.markdown("What do you like? What could be better? Any features you'd love to see?")
        
        with st.form(key="feedback_form", clear_on_submit=True):
            feedback_name = st.text_input("Your Name (Optional)", key="feedback_name_input", placeholder="Let us know who you are")
            feedback_email = st.text_input("Your Email (Optional for follow-up)", key="feedback_email_input", placeholder="your.email@example.com")
            
            feedback_category = st.selectbox(
                "Feedback Category:",
                ["General Usability", "Feature Request", "Content Quality", "Performance", "Other"],
                key="feedback_category_select"
            )
            
            feedback_text = st.text_area(
                "Your Detailed Feedback:", 
                height=200, 
                key="feedback_text_area",
                placeholder="Please be as specific as possible."
            )
            
            submit_feedback_button = st.form_submit_button("✉️ Submit Feedback")

            if submit_feedback_button:
                if feedback_text.strip():
                    try:
                        with open(FEEDBACK_LOG_FILE, "a", encoding="utf-8") as f:
                            f.write(f"\n--- Feedback Entry ---\n")
                            f.write(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"Name: {feedback_name if feedback_name else 'Anonymous'}\n")
                            f.write(f"Email: {feedback_email if feedback_email else 'Not provided'}\n")
                            f.write(f"Category: {feedback_category}\n")
                            f.write(f"Feedback:\n{feedback_text}\n")
                            f.write(f"--- End of Entry ---\n")
                        st.success("✅ Thank you for your valuable feedback! It has been submitted.")
                    except Exception as e:
                        st.error(f"⚠️ An error occurred while saving your feedback: {e}")
                        # Optionally, log this error to a more private log file for the admin
                else:
                    st.error("⚠️ Please provide some feedback before submitting.")

    # --- Bug Report Tab ---
    with tab2:
        st.subheader("Report an Issue")
        st.markdown("Encountered a glitch or something not working as expected? Please let us know!")

        with st.form(key="bug_report_form", clear_on_submit=True):
            bug_reporter_name = st.text_input("Your Name (Optional)", key="bug_name_input", placeholder="So we can credit you or follow up")
            bug_reporter_email = st.text_input("Your Email (Optional for updates)", key="bug_email_input", placeholder="your.email@example.com")
            
            bug_page_feature = st.text_input(
                "Page or Feature Affected:", 
                key="bug_page_input",
                placeholder="e.g., Chat page, Quiz Generator, Document Upload"
            )
            
            bug_severity = st.selectbox(
                "Severity of the Bug:",
                ["Low (Minor inconvenience)", "Medium (Affects functionality but workaround exists)", "High (Blocks functionality, no workaround)", "Critical (System crash, data loss)"],
                key="bug_severity_select"
            )

            bug_description = st.text_area(
                "Detailed Description of the Bug:", 
                height=200, 
                key="bug_description_area",
                placeholder="What happened? What did you expect to happen?"
            )
            
            steps_to_reproduce = st.text_area(
                "Steps to Reproduce the Bug (if possible):",
                height=150,
                key="bug_steps_area",
                placeholder="1. Navigated to...\n2. Clicked on...\n3. Observed that..."
            )
            
            submit_bug_button = st.form_submit_button("🐞 Submit Bug Report")

            if submit_bug_button:
                if bug_description.strip() and bug_page_feature.strip():
                    try:
                        with open(BUG_REPORTS_LOG_FILE, "a", encoding="utf-8") as f:
                            f.write(f"\n--- Bug Report Entry ---\n")
                            f.write(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"Reporter Name: {bug_reporter_name if bug_reporter_name else 'Anonymous'}\n")
                            f.write(f"Reporter Email: {bug_reporter_email if bug_reporter_email else 'Not provided'}\n")
                            f.write(f"Page/Feature: {bug_page_feature}\n")
                            f.write(f"Severity: {bug_severity}\n")
                            f.write(f"Description:\n{bug_description}\n")
                            if steps_to_reproduce.strip():
                                f.write(f"Steps to Reproduce:\n{steps_to_reproduce}\n")
                            f.write(f"--- End of Entry ---\n")
                        st.success("✅ Thank you for reporting the bug! We'll look into it.")
                    except Exception as e:
                        st.error(f"⚠️ An error occurred while saving your bug report: {e}")
                else:
                    st.error("⚠️ Please provide the page/feature affected and a description of the bug.")
    
    st.markdown("---")
    st.info("Your feedback and bug reports are logged locally in text files (`feedback_log.txt`, `bug_reports_log.txt`). In a production environment, this data would typically be sent to a dedicated logging service or database.")

    render_footer()
