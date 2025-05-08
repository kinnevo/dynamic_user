import os
import pyrebase
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv
from nicegui import app

# Load environment variables
load_dotenv()

# Firebase configuration dictionary
# These values should be stored in .env file
config = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL", "")
}

# Initialize Firebase Admin SDK (for server-side operations)
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
if cred_path and os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        # App already initialized
        pass

# Initialize Pyrebase (for client-side operations)
firebase = pyrebase.initialize_app(config)
auth_instance = firebase.auth()

class FirebaseAuth:
    @staticmethod
    def register_user(email, password, display_name=None):
        """
        Register a new user with email and password
        Returns user data or error
        """
        try:
            # Create user with Firebase Auth
            user = auth_instance.create_user_with_email_and_password(email, password)
            
            # Update display name if provided
            if display_name and user.get('idToken'):
                auth_instance.update_profile(user['idToken'], display_name=display_name)
            
            return {"success": True, "user": user}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def login_user(email, password):
        """
        Login a user with email and password
        Returns user data or error
        """
        try:
            user = auth_instance.sign_in_with_email_and_password(email, password)
            return {"success": True, "user": user}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def logout_user():
        """
        Logout the current user
        """
        # Pyrebase doesn't have a logout method as it's stateless
        # We just clear the session data
        if 'user' in app.storage.user:
            del app.storage.user['user']
        return {"success": True}

    @staticmethod
    def get_current_user():
        """
        Get the current user from session
        """
        return app.storage.user.get('user', None)

    @staticmethod
    def refresh_token(refresh_token):
        """
        Refresh the user token
        """
        try:
            user = auth_instance.refresh(refresh_token)
            return {"success": True, "user": user}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def reset_password(email):
        """
        Send password reset email
        """
        try:
            auth_instance.send_password_reset_email(email)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_token(id_token):
        """
        Verify a Firebase ID token
        """
        try:
            decoded_token = auth.verify_id_token(id_token)
            return {"success": True, "uid": decoded_token.get('uid')}
        except Exception as e:
            return {"success": False, "error": str(e)}
