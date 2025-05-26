import streamlit as st
import smtplib # For sending emails
from email.message import EmailMessage # For constructing email messages
import logging # For logging errors
from utils import render_footer # Assuming render_footer is in utils.py
import auth
auth.initialize_session()

def render():
    """Renders the appointment scheduling page."""
    st.title("📅 Schedule an Appointment")
    st.markdown("Request an appointment with the professor or a TA.")

    if 'appointment_form_submitted' not in st.session_state:
        st.session_state.appointment_form_submitted = False

    # --- Appointment Form ---
    with st.form(key='appointment_form', clear_on_submit=True):
        st.subheader("Your Information")
        user_name = st.text_input("👤 Your Name", key="appt_user_name", placeholder="Enter your full name")
        user_email = st.text_input("📧 Your Email", key="appt_user_email", placeholder="Enter your email address")
        
        st.subheader("Appointment Details")
        appointment_with = st.selectbox(
            "🗓️ Schedule with:", 
            ["Professor (Dr. Chen)", "Teaching Assistant (TA)"], 
            key="appt_with"
        )
        preferred_date = st.date_input("📅 Preferred Date", key="appt_date")
        preferred_time = st.time_input("⏰ Preferred Time", key="appt_time")
        
        reason_options = [
            "Discuss course material/concepts",
            "Questions about an assignment",
            "Project discussion/guidance",
            "Career advice/mentorship",
            "Other (please specify below)"
        ]
        primary_reason = st.selectbox("📝 Primary Reason for Appointment:", reason_options, key="appt_primary_reason")
        
        additional_details = ""
        if primary_reason == "Other (please specify below)":
            additional_details = st.text_area(
                "💬 Please specify other reason or add more details:", 
                key="appt_details_other",
                placeholder="Provide a brief description of what you'd like to discuss."
            )
        else:
            additional_details = st.text_area(
                "💬 Additional Details/Questions (Optional):", 
                key="appt_details_optional",
                placeholder="Any specific questions or topics you want to cover?"
            )

        submitted = st.form_submit_button("➡️ Submit Appointment Request")

    # --- Form Submission Logic ---
    if submitted:
        # Basic validation
        if not user_name.strip():
            st.error("⚠️ Please enter your name.")
        elif not user_email.strip() or '@' not in user_email or '.' not in user_email: # Simple email validation
            st.error("⚠️ Please enter a valid email address.")
        elif not preferred_date or not preferred_time:
            st.error("⚠️ Please select a preferred date and time.")
        else:
            try:
                # Email configuration (should be in st.secrets)
                # Ensure your secrets.toml has:
                # [email_config]
                # sender_email = "your_sender_email@example.com"
                # sender_password = "your_email_password"
                # recipient_email = "professor_or_admin_email@example.com" (or dynamically set based on appointment_with)
                # smtp_server = "smtp.example.com"
                # smtp_port = 587 (or 465 for SSL)

                sender = st.secrets.get("email_config", {}).get("sender_email")
                password = st.secrets.get("email_config", {}).get("sender_password")
                # Determine recipient based on selection
                if appointment_with == "Professor (Dr. Chen)":
                    recipient = st.secrets.get("email_config", {}).get("professor_email", "default_prof_recipient@example.com")
                else: # TA
                    recipient = st.secrets.get("email_config", {}).get("ta_email", "default_ta_recipient@example.com")
                
                smtp_server = st.secrets.get("email_config", {}).get("smtp_server")
                smtp_port = st.secrets.get("email_config", {}).get("smtp_port", 587) # Default to 587 for TLS

                if not all([sender, password, recipient, smtp_server]):
                    st.error("Email configuration is missing in secrets.toml. Cannot send request.")
                    logging.error("Email configuration missing for appointment request.")
                    return

                # Compose Email
                msg = EmailMessage()
                msg['Subject'] = f'New Appointment Request: {user_name} - Smart AI Tutor'
                msg['From'] = sender
                msg['To'] = recipient 
                # Optional: CC the student
                # msg['Cc'] = user_email 

                email_body = f"""
                A new appointment has been requested via the Smart AI Tutor platform:

                👤 Requester Name: {user_name}
                📧 Requester Email: {user_email}

                🗓️ Requested For: {appointment_with}
                📅 Preferred Date: {preferred_date.strftime('%A, %B %d, %Y')}
                ⏰ Preferred Time: {preferred_time.strftime('%I:%M %p')}

                📝 Primary Reason: {primary_reason}
                """
                if additional_details.strip():
                    email_body += f"\n💬 Additional Details:\n{additional_details}"
                
                email_body += "\n\n---\nPlease reply to the student directly at their email address to confirm or reschedule."
                msg.set_content(email_body)

                # Send Email
                # Use try-except for SMTP connection and sending
                with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                    server.starttls() # Use TLS encryption
                    server.login(sender, password)
                    server.send_message(msg)
                
                st.session_state.appointment_form_submitted = True # Mark as submitted
                st.success('🎉 Your appointment request has been submitted successfully! We will contact you via email.')
                st.balloons()

            except smtplib.SMTPAuthenticationError:
                st.error("SMTP Authentication Error: Incorrect email username or password in secrets.toml.")
                logging.error("SMTP Authentication Error for appointment email.")
            except smtplib.SMTPException as e_smtp:
                st.error(f"⚠️ Failed to send appointment request due to an SMTP error: {e_smtp}")
                logging.exception(e_smtp) # Log the full exception
            except Exception as e:
                st.error(f"⚠️ An unexpected error occurred: {e}")
                logging.exception(e) # Log the full exception
    
    # Display if form was already submitted in this session
    # This simple flag might reset if the user navigates away and back in some Streamlit setups.
    # For more robust "already submitted" message, you might need more persistent state management.
    elif st.session_state.appointment_form_submitted:
        st.info('✅ You have already submitted an appointment request in this session. Please check your email for confirmation.')

    render_footer()
