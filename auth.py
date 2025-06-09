import streamlit as st
import bcrypt
from user_management import add_user, get_user, USERS_FILE, update_last_login # Added update_last_login

def initialize_session():
    """Initializes the user session state related to authentication."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = "Guest"  # Default user name
    if 'auth_page' not in st.session_state: # Renamed current_page to auth_page for clarity
        st.session_state.auth_page = "login" # Default to login page

def display_signup_page():
    """Displays the sign-up page."""
    st.title("Sign Up")
    with st.form("signup_form"):
        username = st.text_input("Username")
        email = st.text_input("Email (Optional)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Sign Up")

        if submitted:
            if not username or not password or not confirm_password:
                st.error("Username, Password, and Confirm Password are required.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif get_user(username):
                st.error("Username already exists. Please choose another one.")
            else:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                if add_user(username, hashed_password, email):
                    st.success("Sign up successful! Please Sign In.") # Changed text
                    st.session_state.auth_page = "login" # Kept internal value 'login'
                    st.rerun()
                else:
                    st.error("An error occurred during sign up. Please try again.")

    if st.button("Already have an account? Sign In"): # Changed text
        st.session_state.auth_page = "login" # Kept internal value 'login'
        st.rerun()

def display_login_page():
    """Displays the login page."""
    st.title("Sign In to Smart AI Tutor") # Changed text
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In") # Changed text

        if submitted:
            if not username or not password:
                st.error("Username and Password are required.")
            else:
                user_data = get_user(username)
                if user_data:
                    hashed_password_from_db = user_data['hashed_password'].encode('utf-8')
                    if bcrypt.checkpw(password.encode('utf-8'), hashed_password_from_db):
                        # Update last login time
                        if not update_last_login(username):
                            # Optional: Log an error or display a non-critical error to the user
                            # For now, we'll proceed even if this fails to not block login
                            print(f"Warning: Failed to update last login time for user {username}")
                            # st.warning("Could not update last login time, but proceeding with login.")

                        st.session_state.authenticated = True
                        st.session_state.user_name = username
                        st.session_state.pop('dark_mode_initialized_from_user_preference', None) # Reset flag for new login
                        # No longer setting current_page here, app.py will handle it
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.error("Invalid username or password.")

    # Commenting out "Continue as Guest" for now
    # if st.button("Continue as Guest"):
    #     st.session_state.authenticated = True
    #     st.session_state.user_name = "Guest User"
    #     # No longer setting current_page here
    #     st.rerun()

    if st.button("Don't have an account? Sign Up"):
        st.session_state.auth_page = "signup"
        st.rerun()

    st.markdown("---") # Visual separator
    if st.button("Sign in with Google"):
        handle_google_login()

def handle_google_login():
    """Placeholder for initiating Google Sign-In."""
    st.info("Google Sign-In is not yet implemented.")
    # In a real scenario, this would involve:
    # 1. Generating an OAuth 2.0 authorization URL.
    # 2. Redirecting the user to that URL (e.g., using st.markdown with an HTML redirect, or a JavaScript hack).

def handle_google_callback():
    """Placeholder for handling the OAuth callback from Google."""
    # This function would be the redirect URI.
    # It would:
    # 1. Receive the authorization code from query parameters (st.experimental_get_query_params()).
    # 2. Exchange the code for an access token and ID token with Google.
    # 3. Validate the ID token and get user information.
    # 4. Find or create a user in the local user database.
    # 5. Set session state: st.session_state.authenticated = True, st.session_state.user_name = user_email
    # 6. st.rerun()
    pass

def display_logout_button():
    """Displays a logout button if the user is authenticated."""
    # This button will be displayed in the sidebar by sidebar.py
    if st.button("Logout"): # Changed from st.sidebar.button to st.button for flexibility
        st.session_state.authenticated = False
        st.session_state.user_name = "Guest"
        st.session_state.auth_page = "login" # Redirect to login page
        # Potentially clear other session data related to the user
        st.rerun()
