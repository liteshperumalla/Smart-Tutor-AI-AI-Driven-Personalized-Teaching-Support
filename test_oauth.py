#!/usr/bin/env python3
"""
Test script to verify Google OAuth credentials
"""
import requests

# Read credentials from secrets.toml
try:
    import toml
    with open('.streamlit/secrets.toml', 'r') as f:
        secrets = toml.load(f)

    client_id = secrets['google_oauth']['client_id']
    client_secret = secrets['google_oauth']['client_secret']
    redirect_uri = secrets['google_oauth']['redirect_uri']

    print("✓ Credentials loaded successfully from secrets.toml")
    print(f"  Client ID: {client_id}")
    print(f"  Client Secret: {client_secret[:10]}...{client_secret[-4:]}")
    print(f"  Redirect URI: {redirect_uri}")
    print()

    # Test if we can construct a valid OAuth URL
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )

    print("✓ OAuth URL constructed successfully")
    print(f"  URL: {auth_url[:80]}...")
    print()
    print("Next steps:")
    print("1. Make sure OAuth Consent Screen is configured")
    print("2. Add yourself as a test user (if app is in Testing mode)")
    print("3. Try the Google Sign-In button in your app")

except FileNotFoundError:
    print("✗ secrets.toml file not found!")
except KeyError as e:
    print(f"✗ Missing key in secrets.toml: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
