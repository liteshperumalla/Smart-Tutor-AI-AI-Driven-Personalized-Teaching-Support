import streamlit as st
import bcrypt
import requests
import google.auth.transport.requests
import google.oauth2.id_token
from user_management import add_user, get_user, USERS_FILE, update_last_login, update_user_profile, get_user_dir

def initialize_session():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = "Guest"
    if 'auth_page' not in st.session_state:
        st.session_state.auth_page = "login"

def display_signup_page():
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
                    st.success("Sign up successful! Please Sign In.")
                    st.session_state.auth_page = "login"
                    get_user_dir(st.session_state.user_name)
                    st.rerun()
                else:
                    st.error("An error occurred during sign up. Please try again.")

    if st.button("Already have an account? Sign In"):
        st.session_state.auth_page = "login"
        st.rerun()

def display_login_page():
    if st.session_state.get("authenticated", False):
        if st.session_state.get("from_google", False):
            st.query_params.clear()
            del st.session_state["from_google"]
        return
    
    st.title("Sign In to Smart AI Tutor")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")

        if submitted:
            if not username or not password:
                st.error("Username and Password are required.")
            else:
                user_data = get_user(username)
                if user_data:
                    hashed_password_from_db = user_data['hashed_password'].encode('utf-8')
                    if bcrypt.checkpw(password.encode('utf-8'), hashed_password_from_db):
                        if not update_last_login(username):
                            print(f"Warning: Failed to update last login time for user {username}")

                        st.session_state.authenticated = True
                        get_user_dir(st.session_state.user_name)
                        st.session_state.user_name = username
                        st.session_state.pop('dark_mode_initialized_from_user_preference', None)
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.error("Invalid username or password.")

    if st.button("Don't have an account? Sign Up"):
        st.session_state.auth_page = "signup"
        st.rerun()

    st.markdown("---")
    display_google_signin()


def display_google_signin():
    # Get credentials from Streamlit secrets
    client_id = st.secrets.get("google_oauth", {}).get("client_id")
    client_secret = st.secrets.get("google_oauth", {}).get("client_secret")
    redirect_uri = st.secrets.get("google_oauth", {}).get("redirect_uri")

    if not client_id or not client_secret or not redirect_uri:
        st.warning("Google OAuth credentials missing in st.secrets.")
        return

    # Step 1: Render Google Sign-In Button
    login_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )
    st.markdown(f"""
        <a href="{login_url}" target="_self">
            <button style="background-color:#4285F4;color:white;padding:10px 20px;border:none;border-radius:5px;font-size:16px;">
                Sign in with Google
            </button>
        </a>
    """, unsafe_allow_html=True)

    # Step 2: Handle Google OAuth Redirect
    code = st.query_params.get("code")
    if code:
        # Step 3: Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        resp = requests.post(token_url, data=data)
        if resp.status_code != 200:
            st.error(f"Failed to exchange code for token: {resp.text}")
            return
        tokens = resp.json()
        id_token_str = tokens.get("id_token")
        access_token = tokens.get("access_token")

        if not id_token_str:
            st.error("No id_token received from Google.")
            return

        try:
            # Step 4: Verify id_token and extract user info
            request = google.auth.transport.requests.Request()
            id_info = google.oauth2.id_token.verify_oauth2_token(id_token_str, request, client_id)

            email = id_info.get("email")
            name = id_info.get("name")
            picture = id_info.get("picture")

            if not email:
                st.error("Failed to extract user email from Google.")
                return

            # Step 5: Register or update user in your system
            if not get_user(email):
                add_user(email, hashed_password="", email=email)

            update_user_profile(email, {
                'display_name': name or "",
                'profile_picture_path': picture or ""
            })

            st.session_state.authenticated = True
            st.session_state.user_name = email
            st.session_state.from_google = True
            get_user_dir(st.session_state.user_name)
            st.session_state["user_name"] = email
            st.success(f"Signed in as {name} ({email})")
            st.query_params.clear()  # Clear code from URL
            st.rerun()

        except Exception as e:
            st.error(f"Google Sign-In failed: {e}")


def display_logout_button():
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_name = "Guest"
        st.session_state.auth_page = "login"
        st.rerun()
