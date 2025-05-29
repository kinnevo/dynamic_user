import os
import pyrebase
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv
from nicegui import app
import json
import requests
from typing import Optional

# Load environment variables
load_dotenv()

class FirebaseManager:
    """Singleton Firebase manager to avoid multiple initializations"""
    _instance: Optional['FirebaseManager'] = None
    _auth_instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialize_firebase()
            self._initialized = True
    
    def _verify_firebase_api_key(self):
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

    def _initialize_firebase(self):
        """Initialize Firebase services once"""
        # Debug - print all Firebase environment variables (sanitized)
        print("===== FIREBASE CONFIG DEBUGGING =====")
        api_key = os.getenv("FIREBASE_API_KEY")
        auth_domain = os.getenv("FIREBASE_AUTH_DOMAIN")
        project_id = os.getenv("FIREBASE_PROJECT_ID")

        print(f"FIREBASE_API_KEY: {'[SET]' if api_key else '[MISSING]'}")
        print(f"FIREBASE_AUTH_DOMAIN: {'[SET]' if auth_domain else '[MISSING]'}")
        print(f"FIREBASE_PROJECT_ID: {'[SET]' if project_id else '[MISSING]'}")

        # Verify the API key
        self._verify_firebase_api_key()

        # Firebase configuration dictionary
        config = {
            "apiKey": api_key,
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
                self._auth_instance = None 
            else:
                print(f"Initializing Pyrebase with API key: {api_key[:3]}...{api_key[-3:]} (masked for security)")
                firebase = pyrebase.initialize_app(config)
                print("Pyrebase client initialized successfully")
                self._auth_instance = firebase.auth()
                print("Firebase Auth instance created successfully")
        except Exception as e:
            print(f"Error initializing Pyrebase: {e}")
            # Create a placeholder auth_instance to prevent exceptions
            self._auth_instance = None

        # Check if auth is properly configured
        if not config.get('apiKey'):
            print("WARNING: Firebase API Key is missing. User authentication will not work.")
    
    @property
    def auth_instance(self):
        """Get the Firebase auth instance"""
        return self._auth_instance

# Global firebase manager instance
_firebase_manager = None

def get_firebase_manager() -> FirebaseManager:
    """Get the singleton Firebase manager instance"""
    global _firebase_manager
    if _firebase_manager is None:
        _firebase_manager = FirebaseManager()
    return _firebase_manager

# Legacy function to get auth instance
def get_auth_instance():
    """Get the Firebase auth instance (legacy compatibility)"""
    return get_firebase_manager().auth_instance

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
        if get_auth_instance() is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            # Create user with Firebase Auth
            user = get_auth_instance().create_user_with_email_and_password(email, password)
            print(f"User {email} registered successfully")
            
            # Update display name if provided
            if display_name and user.get('idToken'):
                print(f"Updating display name for {email}: {display_name}")
                get_auth_instance().update_profile(user['idToken'], display_name=display_name)
            
            return {"success": True, "user": user}
        except Exception as e:
            print(f"Error during user registration: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def login_user(email, password):
        """
        Login a user with email and password
        Returns user data or error. The user data from Pyrebase typically includes
        'email', 'idToken', 'refreshToken', 'localId' (UID), etc.
        """
        print(f"Attempting to login user: {email}")
        if get_auth_instance() is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            user = get_auth_instance().sign_in_with_email_and_password(email, password)
            # Pyrebase user object contains: kind, localId, email, displayName, idToken, registered, refreshToken, expiresIn
            print(f"User {user.get('email', email)} logged in successfully. UID: {user.get('localId')}")
            return {"success": True, "user": user} # user is a dict-like object
        except Exception as e:
            # Attempt to parse Firebase error response if possible
            error_message = str(e)
            try:
                error_json = json.loads(str(e).split('Reason: ', 1)[1])
                error_message = error_json.get('error', {}).get('message', str(e))
            except:
                pass # Keep original error message if parsing fails
            print(f"Error during user login for {email}: {error_message}")
            return {"success": False, "error": error_message}

    @staticmethod
    def logout_user():
        """
        Logout the current user by clearing their data from app.storage.
        """
        FirebaseAuth._ensure_user_storage()
        print("Logging out user...")
        
        logged_out = False
        if 'user_email' in app.storage.user:
            del app.storage.user['user_email']
            logged_out = True
        if 'firebase_user_data' in app.storage.user:
            del app.storage.user['firebase_user_data']
            logged_out = True
        if 'active_chat_id' in app.storage.user:
            del app.storage.user['active_chat_id']
            # No need to set logged_out = True again

        # Also clear the old 'user' key if it exists
        if 'user' in app.storage.user: # For backward compatibility cleanup
            del app.storage.user['user']
            logged_out = True

        if logged_out:
            print("User session data cleared. User logged out.")
        else:
            print("No user session data found to clear.")
        return {"success": True}

    @staticmethod
    def get_current_user():
        """
        Get the current user's essential data (email, tokens, uid) from app.storage.
        Returns a dictionary with user data or None if not logged in.
        """
        FirebaseAuth._ensure_user_storage()
        
        firebase_data = app.storage.user.get('firebase_user_data', None)
        user_email = app.storage.user.get('user_email', None)

        if firebase_data and user_email:
            # Ensure the structure is consistent and contains what we need
            current_user_info = {
                'email': user_email,
                'uid': firebase_data.get('localId'), # Firebase User ID
                'idToken': firebase_data.get('idToken'),
                'refreshToken': firebase_data.get('refreshToken'),
                'displayName': firebase_data.get('displayName', '')
            }
            print(f"Current user retrieved from session: {current_user_info.get('email')}")
            return current_user_info
        else:
            # Compatibility: check old 'user' key if new keys are not present
            old_user_data = app.storage.user.get('user', None)
            if old_user_data and old_user_data.get('email') and old_user_data.get('idToken'):
                 print(f"Current user retrieved from session (legacy format): {old_user_data.get('email')}")
                 # It's better to re-store in new format if found in old, but for now just return
                 return {
                    'email': old_user_data.get('email'),
                    'uid': old_user_data.get('localId'),
                    'idToken': old_user_data.get('idToken'),
                    'refreshToken': old_user_data.get('refreshToken'),
                    'displayName': old_user_data.get('displayName', '')
                 }
            print("No current user data (email or firebase_user_data) in session.")
            return None

    @staticmethod
    def refresh_token(refresh_token):
        """
        Refresh the user token
        """
        print(f"Attempting to refresh token")
        if get_auth_instance() is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            user = get_auth_instance().refresh(refresh_token)
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
        if get_auth_instance() is None:
            print("ERROR: Firebase Auth not properly initialized")
            return {"success": False, "error": "Firebase Auth not initialized"}
            
        try:
            get_auth_instance().send_password_reset_email(email)
            print(f"Password reset email sent to {email}")
            return {"success": True}
        except Exception as e:
            print(f"Error sending password reset email: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_token(id_token):
        """
        Verify a Firebase ID token using Firebase Admin SDK.
        """
        if not firebase_admin._DEFAULT_APP_NAME:
            print("Error verifying token: Firebase Admin SDK not initialized.")
            return {"success": False, "error": "Admin SDK not initialized"}
        try:
            decoded_token = auth.verify_id_token(id_token)
            print(f"Token verified successfully for UID: {decoded_token.get('uid')}")
            return {"success": True, "uid": decoded_token.get('uid')}
        except Exception as e:
            print(f"Error verifying token: {e}")
            return {"success": False, "error": str(e)}
