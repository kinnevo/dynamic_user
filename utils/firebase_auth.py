import os
import pyrebase
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv
from nicegui import app
import json
import requests

# Load environment variables
load_dotenv()

def verify_firebase_api_key():
    """Simple test to verify that the Firebase API key is valid"""
    api_key = os.getenv("FIREBASE_API_KEY")
    if not api_key:
        print("Cannot verify Firebase API key - it is not set")
        return False
    
    try:
        # Use a simple API endpoint that requires the API key
        test_url = f"https://identitytoolkit.googleapis.com/v1/accounts:createAuthUri?key={api_key}"
        payload = {"continueUri": "https://example.com", "providerId": "google.com"}
        
        print(f"Testing Firebase API key (first 3 chars: {api_key[:3]}...)")
        response = requests.post(test_url, json=payload)
        
        if response.status_code == 400:
            # A 400 response is expected for this API call without all required fields
            # But it confirms the API key is valid
            print("✅ Firebase API key is valid! (Verified with test request)")
            return True
        else:
            print(f"❌ Firebase API key verification gave unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error while verifying Firebase API key: {e}")
        return False

# Debug - print all Firebase environment variables (sanitized)
print("===== FIREBASE CONFIG DEBUGGING =====")
api_key = os.getenv("FIREBASE_API_KEY")
auth_domain = os.getenv("FIREBASE_AUTH_DOMAIN")
project_id = os.getenv("FIREBASE_PROJECT_ID")

print(f"FIREBASE_API_KEY: {'[SET]' if api_key else '[MISSING]'}")
print(f"FIREBASE_AUTH_DOMAIN: {'[SET]' if auth_domain else '[MISSING]'}")
print(f"FIREBASE_PROJECT_ID: {'[SET]' if project_id else '[MISSING]'}")

# Verify the API key
verify_firebase_api_key()

# Firebase configuration dictionary
# These values should be stored in .env file
config = {
    "apiKey": api_key,  # Using the variable to easily debug
    "authDomain": auth_domain,
    "projectId": project_id,
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL", "")
}

# Explicit check for API key before proceeding
if not api_key:
    print("ERROR: FIREBASE_API_KEY is not set in environment variables!")
    print("User authentication will not work without an API key.")
    print("Please set FIREBASE_API_KEY in your .env file and restart the application.")

# Print Firebase config for debugging (excluding API key for security)
# print("Firebase Config - Checking if configured properly:")
# for key, value in config.items():
#     if key == 'apiKey':
#         # Show only if API key exists, but not the actual key
#         print(f"  {key}: {'[SET]' if value else '[MISSING - Required for user auth]'}")
#     else:
#         # Show if value exists for other config items
#         print(f"  {key}: {'[SET]' if value else '[MISSING]'}")

# Initialize Firebase Admin SDK (for server-side operations)
service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
cred = None
if service_account_json:
    try:
        print("Loading Firebase Admin SDK with credentials from environment...")
        cred_dict = json.loads(service_account_json)
        # Fix for escaped newlines in private_key
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cred_dict)
        print("Firebase Admin SDK credentials successfully loaded from environment")
    except Exception as e:
        print(f"Error loading FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
else:
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if cred_path and os.path.exists(cred_path):
        print(f"Loading Firebase Admin SDK with credentials from file: {cred_path}")
        cred = credentials.Certificate(cred_path)
        print("Firebase Admin SDK credentials successfully loaded from file")
    else:
        print("No Firebase credentials found (neither in environment nor file)")

if cred:
    try:
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialization successful")
    except ValueError as e:
        # App already initialized
        print(f"Firebase Admin SDK already initialized: {e}")
else:
    print("WARNING: Firebase Admin SDK initialization skipped - no credentials")

# Initialize Pyrebase (for client-side operations)
try:
    if not api_key:
        print("CRITICAL ERROR: Cannot initialize Pyrebase without API key")
        # Create placeholder auth instance
        auth_instance = None 
    else:
        print(f"Initializing Pyrebase with API key: {api_key[:3]}...{api_key[-3:]} (masked for security)")
        firebase = pyrebase.initialize_app(config)
        print("Pyrebase client initialized successfully")
        auth_instance = firebase.auth()
        print("Firebase Auth instance created successfully")
except Exception as e:
    print(f"Error initializing Pyrebase: {e}")
    # Create a placeholder auth_instance to prevent exceptions
    auth_instance = None

# Check if auth is properly configured
if not config.get('apiKey'):
    print("WARNING: Firebase API Key is missing. User authentication will not work.")

class FirebaseAuth:
    @staticmethod
    def _ensure_user_storage():
        """Ensure user storage is initialized"""
        if not hasattr(app.storage, 'user'):
            app.storage.user = {}

    @staticmethod
    def register_user(email, password, display_name=None):
        """
        Register a new user with email and password
        Returns user data or error
        """
        print(f"Attempting to register user: {email} with display name: {display_name}")
        if auth_instance is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            # Create user with Firebase Auth
            user = auth_instance.create_user_with_email_and_password(email, password)
            print(f"User {email} registered successfully")
            
            # Update display name if provided
            if display_name and user.get('idToken'):
                print(f"Updating display name for {email}: {display_name}")
                auth_instance.update_profile(user['idToken'], display_name=display_name)
            
            return {"success": True, "user": user}
        except Exception as e:
            print(f"Error during user registration: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def login_user(email, password):
        """
        Login a user with email and password
        Returns user data or error
        """
        print(f"Attempting to login user: {email}")
        if auth_instance is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            user = auth_instance.sign_in_with_email_and_password(email, password)
            print(f"User {email} logged in successfully")
            return {"success": True, "user": user}
        except Exception as e:
            print(f"Error during user login: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def logout_user():
        """
        Logout the current user
        """
        # Ensure user storage exists
        FirebaseAuth._ensure_user_storage()
        print("Logging out user")
        
        # Pyrebase doesn't have a logout method as it's stateless
        # We just clear the session data
        if 'user' in app.storage.user:
            del app.storage.user['user']
            print("User logged out successfully")
        return {"success": True}

    @staticmethod
    def get_current_user():
        """
        Get the current user from session
        """
        # Ensure user storage exists
        FirebaseAuth._ensure_user_storage()
        
        user = app.storage.user.get('user', None)
        if user:
            print(f"Current user found in session: {user.get('email', 'Unknown email')}")
        else:
            print("No current user in session")
        return user

    @staticmethod
    def refresh_token(refresh_token):
        """
        Refresh the user token
        """
        print(f"Attempting to refresh token")
        if auth_instance is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            user = auth_instance.refresh(refresh_token)
            print("Token refreshed successfully")
            return {"success": True, "user": user}
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def reset_password(email):
        """
        Send password reset email
        """
        print(f"Attempting to send password reset email to: {email}")
        if auth_instance is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            auth_instance.send_password_reset_email(email)
            print(f"Password reset email sent to {email}")
            return {"success": True}
        except Exception as e:
            print(f"Error sending password reset email: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_token(id_token):
        """
        Verify a Firebase ID token
        """
        try:
            decoded_token = auth.verify_id_token(id_token)
            print(f"Token verified successfully for UID: {decoded_token.get('uid')}")
            return {"success": True, "uid": decoded_token.get('uid')}
        except Exception as e:
            print(f"Error verifying token: {e}")
            return {"success": False, "error": str(e)}
