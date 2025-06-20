import streamlit as st
import os
import bcrypt
import json
from PIL import Image
from datetime import datetime
from user_management import get_user, update_user_profile, change_password, delete_user_account, save_user_profile_pic, get_user_dir

def render():
    st.title("User Profile")

    if not st.session_state.get('authenticated', False):
        st.error("Please login to view your profile.")
        st.stop()

    username = st.session_state.get("user_name")
    if not username:
        st.error("User not identified. Please login again.")
        st.stop()

    user_data = get_user(username)
    if not user_data:
        st.error("Could not retrieve user data.")
        st.stop()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Profile Picture")
        current_image_placeholder = st.empty()

        # Display current profile picture using new logic
        user_dir = get_user_dir(username)
        profile_pic_found = False
        
        for ext in [".png", ".jpg", ".jpeg"]:
            pic_path = os.path.join(user_dir, f"profile_pic{ext}")
            if os.path.exists(pic_path):
                try:
                    image = Image.open(pic_path)
                    current_image_placeholder.image(image, caption="Your Profile Picture", width=150)
                    profile_pic_found = True
                    break
                except Exception as e:
                    current_image_placeholder.warning(f"Could not load image: {e}")
        
        if not profile_pic_found:
            current_image_placeholder.info("No profile picture.")

        # Upload new profile picture using new logic
        uploaded_file = st.file_uploader("Upload or change (JPG, PNG)", type=["jpg", "png", "jpeg"], key="profile_pic_uploader")
        if uploaded_file:
            try:
                ext = os.path.splitext(uploaded_file.name)[1]
                pic_path = save_user_profile_pic(username, uploaded_file.getbuffer(), ext)
                
                if pic_path:
                    st.success("Profile picture updated!")
                    st.session_state["profile_pic_updated"] = True
                    st.rerun()
                else:
                    st.error("Failed to update profile picture.")
            except Exception as e:
                st.error(f"Error saving picture: {e}")

    with col2:
        st.subheader("Account Information")
        st.write(f"**Username:** {username}")
        st.write(f"**Email:** {user_data.get('email', 'Not set')}")
        st.write(f"**Role:** {user_data.get('role', 'User')}")

        last_login_str = user_data.get('last_login')
        if last_login_str:
            try:
                last_login_dt = datetime.fromisoformat(last_login_str)
                st.write(f"**Last Login:** {last_login_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            except ValueError:
                st.write(f"**Last Login:** {last_login_str} (unparsed)")
        else:
            st.write("**Last Login:** Never")

        st.markdown("---")
        st.subheader("Edit Profile")

        display_name = user_data.get('display_name', '')
        phone_number = user_data.get('phone_number', '')

        new_display_name = st.text_input("Display Name:", value=display_name or "")
        new_phone_number = st.text_input("Phone Number:", value=phone_number or "")

        if st.button("Save Profile Information", key="save_profile_info"):
            updates_to_make = {}
            if new_display_name.strip() != display_name:
                updates_to_make['display_name'] = new_display_name.strip()[:100]
            if new_phone_number.strip() != phone_number:
                updates_to_make['phone_number'] = new_phone_number.strip()[:20]

            if updates_to_make:
                if update_user_profile(username, updates_to_make):
                    st.success("Profile information updated!")
                    st.rerun()
                else:
                    st.error("Failed to update profile information.")
            else:
                st.info("No changes detected.")

        st.markdown("---")
        st.subheader("Preferences")
        current_theme = user_data.get('theme', 'light')
        new_theme = st.radio("Theme Preference", ["light", "dark"], index=(0 if current_theme != "dark" else 1), key="theme_radio")

        if new_theme != current_theme:
            if update_user_profile(username, {'theme': new_theme}):
                st.session_state["dark_mode"] = (new_theme == "dark")
                st.success(f"Theme changed to {new_theme}.")
                st.rerun()
            else:
                st.error("Failed to update theme preference.")

    st.markdown("---")
    with st.expander("My Notes"):
        notes_dir = os.path.join(get_user_dir(username), "notes")
        os.makedirs(notes_dir, exist_ok=True)
        notes_path = os.path.join(notes_dir, "notes.txt")

        # Load current notes from file
        if os.path.exists(notes_path):
            with open(notes_path, "r", encoding="utf-8") as f:
                current_notes = f.read()
        else:
            current_notes = ""

        notes_text_area = st.text_area("Jot down your notes here:", value=current_notes, height=200, key="notes_area")
        if st.button("Save Notes", key="save_notes_button"):
            if notes_text_area.strip() != current_notes.strip():
                try:
                    with open(notes_path, "w", encoding="utf-8") as f:
                        f.write(notes_text_area.strip())
                    st.success("Notes saved successfully!")
                    st.rerun()
                except Exception:
                    st.error("Failed to save notes.")
            else:
                st.info("No changes in notes.")
        # --- Render Appointments ---
    st.markdown("---")
    with st.expander("📅 My Appointments"):
        appointments_dir = os.path.join(get_user_dir(username), "appointments")
        appointments = []
        if os.path.exists(appointments_dir):
            for fname in sorted(os.listdir(appointments_dir), reverse=True):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(appointments_dir, fname), "r", encoding="utf-8") as f:
                            appointments.append(json.load(f))
                    except Exception:
                        continue
        if appointments:
            for appt in appointments:
                st.write(f"**Date:** {appt.get('date', 'N/A')}")
                st.write(f"**Time:** {appt.get('time', 'N/A')}")
                st.write(f"**With:** {appt.get('with', 'N/A')}")
                st.write(f"**Reason:** {appt.get('reason', 'N/A')}")
                st.markdown("---")
        else:
            st.info("No appointments found.")

    # --- Render Quiz Results ---
    with st.expander("📝 My Quiz Results"):
        quiz_dir = os.path.join(get_user_dir(username), "quiz")
        quiz_results = []
        if os.path.exists(quiz_dir):
            for fname in sorted(os.listdir(quiz_dir), reverse=True):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(quiz_dir, fname), "r", encoding="utf-8") as f:
                            quiz_results.append(json.load(f))
                    except Exception:
                        continue
        if quiz_results:
            for result in quiz_results:
                ts = result.get("timestamp", "")
                try:
                    ts_fmt = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    ts_fmt = ts
                st.write(f"**Date:** {ts_fmt}")
                st.write(f"**Score:** {result.get('score', 'N/A')}/{result.get('total_questions', 'N/A')} ({result.get('percentage', 0):.1f}%)")
                st.write(f"**Folders:** {', '.join(result.get('selected_folders', []))}")
                st.markdown("---")
        else:
            st.info("No quiz results found.")

    # --- Render Feedback ---
    with st.expander("💬 My Feedback"):
        feedback_dir = os.path.join(get_user_dir(username), "feedback")
        feedbacks = []
        if os.path.exists(feedback_dir):
            for fname in sorted(os.listdir(feedback_dir), reverse=True):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(feedback_dir, fname), "r", encoding="utf-8") as f:
                            feedbacks.append(json.load(f))
                    except Exception:
                        continue
        if feedbacks:
            for fb in feedbacks:
                ts = fb.get("timestamp", "")
                try:
                    ts_fmt = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    ts_fmt = ts
                st.write(f"**Date:** {ts_fmt}")
                st.write(f"**Type:** {fb.get('type', 'N/A')}")
                st.write(f"**Message:** {fb.get('message', 'N/A')}")
                st.markdown("---")
        else:
            st.info("No feedback found.")
            
    st.markdown("---")
    with st.expander("Change Password"):
        with st.form("change_password_form"):
            current_pw = st.text_input("Current Password", type="password")
            new_pw = st.text_input("New Password", type="password")
            confirm_pw = st.text_input("Confirm New Password", type="password")
            submitted = st.form_submit_button("Change Password")

            if submitted:
                if not current_pw or not new_pw or not confirm_pw:
                    st.error("All fields are required.")
                elif new_pw != confirm_pw:
                    st.error("New passwords do not match.")
                elif len(new_pw) < 8:
                    st.error("New password must be at least 8 characters.")
                else:
                    raw_hashed_pw = user_data.get('hashed_password')
                    if not raw_hashed_pw:
                        st.error("Password not set. Contact support.")
                    elif bcrypt.checkpw(current_pw.encode(), raw_hashed_pw.encode()):
                        new_hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                        if change_password(username, new_hashed):
                            st.success("Password changed successfully.")
                        else:
                            st.error("Failed to change password.")
                    else:
                        st.error("Incorrect current password.")

    st.markdown("---")
    with st.expander("Delete Account"):
        st.warning("This will permanently delete your account. Type your username to confirm.")
        confirm_username = st.text_input("Type your username to confirm:", key="delete_confirm_text")
        if st.button("Delete Account", key="delete_account_button"):
            if confirm_username == username:
                if delete_user_account(username):
                    st.success("Account deleted. Logging out...")
                    st.session_state.authenticated = False
                    st.session_state.user_name = None
                    st.session_state.auth_page = 'login'
                    st.rerun()
                else:
                    st.error("Failed to delete account.")
            else:
                st.error("Username confirmation does not match.")