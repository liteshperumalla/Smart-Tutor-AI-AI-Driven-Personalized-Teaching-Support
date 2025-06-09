import streamlit as st
from user_management import get_user, update_user_profile, change_password, delete_user_account
# import profile_management # For future use - commented out as it's not used yet
import os
from PIL import Image
from datetime import datetime # For formatting last_login
import bcrypt

PROFILE_PICS_DIR = "user_profile_pics"

def render():
    """Renders the user profile page."""
    st.title("User Profile")

    # Authentication Check
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

    # Create profile pictures directory if it doesn't exist
    if not os.path.exists(PROFILE_PICS_DIR):
        try:
            os.makedirs(PROFILE_PICS_DIR)
        except OSError as e:
            st.error(f"Failed to create profile picture directory: {e}")
            st.stop()

    # --- Main Layout ---
    # Left column for Profile Picture, Right column for details and settings
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Profile Picture")
        profile_picture_path = user_data.get('profile_picture_path')
        current_image_placeholder = st.empty()

        if profile_picture_path and os.path.exists(profile_picture_path):
            try:
                image = Image.open(profile_picture_path)
                current_image_placeholder.image(image, caption="Your Profile Picture", width=150)
            except Exception as e:
                current_image_placeholder.warning(f"Could not load image: {e}")
        else:
            current_image_placeholder.info("No profile picture.")

        uploaded_file = st.file_uploader("Upload or change (JPG, PNG)", type=["jpg", "png"], key="profile_pic_uploader")
        if uploaded_file is not None:
            file_extension = os.path.splitext(uploaded_file.name)[1]
            safe_username = "".join(c if c.isalnum() else "_" for c in username)
            new_picture_filename = os.path.join(PROFILE_PICS_DIR, f"{safe_username}_profile{file_extension}")

            try:
                if profile_picture_path and os.path.exists(profile_picture_path) and profile_picture_path != new_picture_filename:
                    os.remove(profile_picture_path)
                with open(new_picture_filename, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                if update_user_profile(username, {'profile_picture_path': new_picture_filename}):
                    st.success("Profile picture updated!")
                    st.rerun()
                else:
                    st.error("Failed to update profile picture in user data.")
                    if os.path.exists(new_picture_filename): os.remove(new_picture_filename)
            except Exception as e:
                st.error(f"Error saving picture: {e}")
                if os.path.exists(new_picture_filename) and new_picture_filename != profile_picture_path:
                    os.remove(new_picture_filename)

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
                st.write(f"**Last Login:** {last_login_str} (Could not parse date)")
        else:
            st.write("**Last Login:** Never")

        st.markdown("---")
        st.subheader("Edit Profile")

        display_name = user_data.get('display_name', '')
        new_display_name = st.text_input("Display Name:", value=display_name)

        phone_number = user_data.get('phone_number', '')
        new_phone_number = st.text_input("Phone Number:", value=phone_number)

        if st.button("Save Profile Information", key="save_profile_info"):
            updates_to_make = {}
            if new_display_name != display_name:
                 updates_to_make['display_name'] = new_display_name
            if new_phone_number != phone_number:
                 updates_to_make['phone_number'] = new_phone_number

            if updates_to_make:
                if update_user_profile(username, updates_to_make):
                    st.success("Profile information updated!")
                    st.rerun()
                else:
                    st.error("Failed to update profile information.")
            else:
                st.info("No changes to save in profile information.")

        st.markdown("---")
        st.subheader("Preferences")
        current_theme = user_data.get('theme', 'light')
        theme_options = ["light", "dark"]
        current_theme_index = theme_options.index(current_theme) if current_theme in theme_options else 0
        new_theme = st.radio("Theme Preference", theme_options, index=current_theme_index, key="theme_radio")

        if new_theme != current_theme:
            if update_user_profile(username, {'theme': new_theme}):
                st.session_state.dark_mode = (new_theme == "dark") # Assuming app.py uses this
                st.success(f"Theme changed to {new_theme}.")
                st.rerun()
            else:
                st.error("Failed to update theme preference.")

    # Sections below the columns
    st.markdown("---")

    with st.expander("My Notes"):
        current_notes = user_data.get('notes', '')
        notes_text_area = st.text_area("Jot down your notes here:", value=current_notes, height=200, key="notes_area")
        if st.button("Save Notes", key="save_notes_button"):
            if notes_text_area != current_notes : # Check if notes actually changed
                if update_user_profile(username, {'notes': notes_text_area}):
                    st.success("Notes saved successfully!")
                    st.rerun()
                else:
                    st.error("Failed to save notes.")
            else:
                st.info("No changes in notes to save.")

    st.markdown("---") # Added separator

    with st.expander("Past Quiz Results"):
        st.info("Your past quiz results and scores will be displayed here once the feature is fully integrated.")
        # TODO: Fetch and display quiz results for the user from quiz_history.py or similar

    with st.expander("Saved Conversations"):
        st.info("Links to your saved chat conversations will appear here.")
        # TODO: Fetch and display links/summaries of saved chats for the user from chat_history or similar

    with st.expander("Feedback History"):
        st.info("A summary of your submitted feedback will be shown here.")
        # TODO: Fetch and display feedback submitted by the user

    st.markdown("---") # Added separator

    with st.expander("Change Password"):
        with st.form("change_password_form"):
            current_password_input = st.text_input("Current Password", type="password")
            new_password_input = st.text_input("New Password", type="password")
            confirm_new_password_input = st.text_input("Confirm New Password", type="password")
            change_password_submitted = st.form_submit_button("Change Password")

            if change_password_submitted:
                if not current_password_input or not new_password_input or not confirm_new_password_input:
                    st.error("All password fields are required.")
                else:
                    stored_hashed_password = user_data.get('hashed_password', '').encode('utf-8')
                    if bcrypt.checkpw(current_password_input.encode('utf-8'), stored_hashed_password):
                        if new_password_input == confirm_new_password_input:
                            if len(new_password_input) < 8 : # Basic password policy example
                                st.error("New password must be at least 8 characters long.")
                            else:
                                new_hashed_bytes = bcrypt.hashpw(new_password_input.encode('utf-8'), bcrypt.gensalt())
                                if change_password(username, new_hashed_bytes.decode('utf-8')):
                                    st.success("Password changed successfully.")
                                else:
                                    st.error("Failed to change password.")
                        else:
                            st.error("New passwords do not match.")
                    else:
                        st.error("Incorrect current password.")

    st.markdown("---")
    with st.expander("Delete Account", expanded=False):
        st.warning("WARNING: This action is irreversible and will permanently delete all your data associated with this account.")
        confirmation_text = st.text_input("To confirm, please type your username:", key="delete_confirm_text")

        # For the delete button, using type="primary" might make it red by default in some Streamlit themes or future versions.
        # Or, one could use st.markdown("<style>...</style>", unsafe_allow_html=True) for custom button color if essential.
        if st.button("Permanently Delete My Account", type="primary", key="delete_account_button"):
            if confirmation_text == username:
                if delete_user_account(username):
                    st.success("Account deleted successfully. You will be logged out.")
                    st.session_state.authenticated = False
                    st.session_state.user_name = None # Or "Guest"
                    st.session_state.auth_page = 'login' # Or 'signup' or a specific "goodbye" page
                    # Potentially clear other user-specific session data here
                    st.rerun()
                else:
                    st.error("Failed to delete account. Please try again or contact support.")
            else:
                st.error("Username confirmation does not match. Account not deleted.")

if __name__ == '__main__':
    # Mock for testing, ensure 'testuser' exists in users.json or mock get_user
    # st.session_state.authenticated = True
    # st.session_state.user_name = "testuser"
    # render()
    pass
