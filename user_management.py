import json
import os

USERS_FILE = 'users.json'

def load_users():
    """Loads user data from the JSON file."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}  # Return empty dict on decoding error
    return {}

def save_users(users_data):
    """Saves user data to the JSON file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=4)

def add_user(username, hashed_password, email=None):
    """Adds a new user to the system."""
    users = load_users()
    if username in users:
        return False  # Username already exists
    users[username] = {
        'hashed_password': hashed_password.decode('utf-8'),  # Store as string
        'email': email
    }
    save_users(users)
    return True

def get_user(username):
    """Retrieves a user's data."""
    users = load_users()
    return users.get(username)
