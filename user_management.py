import json
import os
from datetime import datetime

USERS_FILE = 'users.json'

def load_users():
    """Loads user data from the JSON file."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # If file is corrupted or not valid JSON, return empty dict
            return {}
    return {}

def save_users(users_data):
    """Saves user data to the JSON file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=4)

def add_user(username, hashed_password, email=None):
    """Adds a new user to the system with an expanded data structure."""
    users = load_users()
    if username in users:
        return False  # Username already exists

    users[username] = {
        'hashed_password': hashed_password.decode('utf-8') if isinstance(hashed_password, bytes) else hashed_password,
        'email': email,
        'display_name': "",
        'phone_number': "",
        'role': "User",
        'last_login': "",
        'theme': "light",
        'notes': "",
        'profile_picture_path': ""
    }
    save_users(users)
    return True

def get_user(username):
    """Retrieves a user's data."""
    users = load_users()
    return users.get(username)

def update_user_profile(username, profile_data):
    """Updates specified fields in a user's profile."""
    users = load_users()
    if username not in users:
        return False

    for key, value in profile_data.items():
        if key in users[username]: # Only update existing keys in the user's data structure
            users[username][key] = value
        # else: consider logging a warning or error if key is unexpected

    save_users(users)
    return True

def update_last_login(username):
    """Updates the last_login field for a user to the current UTC time."""
    users = load_users()
    if username not in users:
        return False

    users[username]['last_login'] = datetime.utcnow().isoformat()
    save_users(users)
    return True

def change_password(username, new_hashed_password):
    """Changes a user's password."""
    users = load_users()
    if username not in users:
        return False

    users[username]['hashed_password'] = new_hashed_password.decode('utf-8') if isinstance(new_hashed_password, bytes) else new_hashed_password
    save_users(users)
    return True

def delete_user_account(username):
    """Deletes a user account from the system."""
    users = load_users()
    if username not in users:
        return False # User not found

    del users[username]
    save_users(users)
    return True
