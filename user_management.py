
import json
import os
from datetime import datetime
from pathlib import Path
import os
import json
import uuid
from datetime import datetime
from utils import make_session_title
USER_DATA_ROOT = "user_data"

def sanitize_user_id(user_id):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in user_id)

def get_user_dir(user_id):
    user_dir = os.path.join(USER_DATA_ROOT, sanitize_user_id(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_chats_dir(user_id):
    chats_dir = os.path.join(get_user_dir(user_id), "chats")
    os.makedirs(chats_dir, exist_ok=True)
    return chats_dir


def load_chat(user_id, chat_id):
    chats_dir = get_user_chats_dir(user_id)
    chat_path = os.path.join(chats_dir, f"{chat_id}.json")
    if os.path.exists(chat_path):
        with open(chat_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_user_file(user_id, filename, data):
    """Save data to a user-specific file."""
    user_dir = get_user_dir(user_id)
    file_path = os.path.join(user_dir, filename)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving user file {filename} for user {user_id}: {e}")
        return False

def load_user_file(user_id, filename, default=None):
    """Load data from a user-specific file."""
    user_dir = get_user_dir(user_id)
    file_path = os.path.join(user_dir, filename)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading user file {filename} for user {user_id}: {e}")
            return default if default is not None else {}
    
    return default if default is not None else {}

def save_new_chat(user_id, chat_id, title=None):
    """Save a new chat for a user with the given chat_id."""
    chats_dir = get_user_chats_dir(user_id)
    timestamp = datetime.utcnow().isoformat()
    chat_filename = f"{chat_id}.json"
    chat_path = os.path.join(chats_dir, chat_filename)
    
    # Create empty chat data
    chat_data = []
    
    with open(chat_path, "w", encoding="utf-8") as f:
        json.dump(chat_data, f, indent=2, ensure_ascii=False)
    
    # Update index
    index_path = os.path.join(chats_dir, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []
    
    # Check if chat already exists in index
    chat_exists = any(chat.get("id") == chat_id or chat.get("chat_id") == chat_id for chat in index)
    
    if not chat_exists:
        index.append({
            "id": chat_id,
            "chat_id": chat_id,  # Keep both for backward compatibility
            "filename": chat_filename,
            "title": title or f"New Chat",
            "timestamp": timestamp
        })
        
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    
    return chat_id

def list_user_chats(user_id):
    chats_dir = get_user_chats_dir(user_id)
    chat_list = []

    if not os.path.exists(chats_dir):
        return chat_list

    for fname in os.listdir(chats_dir):
        if fname.endswith(".json") and fname != "index.json":
            fpath = os.path.join(chats_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    chat_data = json.load(f)

                chat_id = fname.replace(".json", "")

                # 🧠 Determine message list
                if isinstance(chat_data, list):
                    messages = chat_data
                elif isinstance(chat_data, dict):
                    messages = chat_data.get("messages", [])
                else:
                    messages = []

                # 📝 Ensure there's a title
                title = chat_data.get("title") or make_session_title(messages)

                timestamp = chat_data.get(
                    "timestamp",
                    datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
                )

                chat_list.append({
                    "id": chat_id,
                    "chat_id": chat_id,
                    "title": title,
                    "timestamp": timestamp
                })

            except Exception as e:
                print(f"⚠️ Error reading chat {fname}: {e}")

    chat_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return chat_list

def save_user_profile_pic(user_id, image_buffer, file_extension):
    """Save a user's profile picture to their user directory."""
    user_dir = get_user_dir(user_id)
    
    # Remove any existing profile pictures first
    for ext in [".png", ".jpg", ".jpeg"]:
        old_pic_path = os.path.join(user_dir, f"profile_pic{ext}")
        if os.path.exists(old_pic_path):
            try:
                os.remove(old_pic_path)
            except Exception as e:
                print(f"Warning: Could not remove old profile picture {old_pic_path}: {e}")
    
    # Save the new profile picture
    pic_filename = f"profile_pic{file_extension.lower()}"
    pic_path = os.path.join(user_dir, pic_filename)
    
    try:
        with open(pic_path, "wb") as f:
            f.write(image_buffer)
        return pic_path
    except Exception as e:
        print(f"Error saving profile picture for user {user_id}: {e}")
        return None
    

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
    """Adds a new user to the system with an expanded data structure and creates user folders."""
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

    # --- Create user directory and subfolders ---
    user_dir = get_user_dir(username)
    subfolders = ["chats", "appointments", "feedback", "quiz", "code_files", "notes", "resources"]
    for folder in subfolders:
        os.makedirs(os.path.join(user_dir, folder), exist_ok=True)
    # -------------------------------------------

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

