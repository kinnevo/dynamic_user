import firebase_admin
from utils.database_singleton import get_db
from utils.firebase_auth import FirebaseAuth
from nicegui import ui, app
from functools import wraps
import json
import inspect

def auth_required(func):
    """
    Decorator that requires authentication for accessing pages.
    Checks Firebase token validity and ensures user exists in database.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if user is logged in
        current_user_email = app.storage.user.get('user_email')
        firebase_user_data = app.storage.user.get('firebase_user_data')
        
        if not current_user_email or not firebase_user_data:
            print("No current user data (email or firebase_user_data) in session.")
            ui.navigate.to('/login')
            return
        
        print(f"Current user retrieved from session: {current_user_email}")
        
        # Try to verify the current token
        id_token = app.storage.user.get('id_token')
        if not id_token:
            print("No ID token found in session.")
            ui.navigate.to('/login')
            return
        
        try:
            print(f"Auth middleware: User {current_user_email} authenticated, verifying token...")
            
            # Verify the Firebase ID token
            decoded_token = firebase_admin.auth.verify_id_token(id_token)
            firebase_uid = decoded_token['uid']
            
            print(f"Auth middleware: Token verified successfully for {current_user_email}")
            
        except firebase_admin.auth.ExpiredIdTokenError:
            print(f"Error verifying token: Token expired")
            print(f"Auth middleware: Token verification failed for {current_user_email}. Attempting refresh.")
            
            # Try to refresh the token
            refresh_token = app.storage.user.get('refresh_token')
            if refresh_token:
                try:
                    print("Attempting to refresh token")
                    # Refresh the token using Firebase REST API
                    import requests
                    import os
                    
                    refresh_url = f"https://securetoken.googleapis.com/v1/token?key={os.getenv('FIREBASE_API_KEY')}"
                    refresh_data = {
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                    
                    response = requests.post(refresh_url, data=refresh_data)
                    if response.status_code == 200:
                        new_tokens = response.json()
                        app.storage.user['id_token'] = new_tokens['id_token']
                        app.storage.user['refresh_token'] = new_tokens['refresh_token']
                        
                        # Verify the new token
                        decoded_token = firebase_admin.auth.verify_id_token(new_tokens['id_token'])
                        firebase_uid = decoded_token['uid']
                        
                        print("Token refreshed successfully")
                        print(f"Auth middleware: Token refreshed successfully for {current_user_email}.")
                    else:
                        print(f"Failed to refresh token: {response.status_code}")
                        ui.navigate.to('/login')
                        return
                        
                except Exception as refresh_error:
                    print(f"Error refreshing token: {refresh_error}")
                    ui.navigate.to('/login')
                    return
            else:
                print("No refresh token available")
                ui.navigate.to('/login')
                return
                
        except Exception as e:
            print(f"Error verifying token: {e}")
            ui.navigate.to('/login')
            return
        
        # Ensure user exists in database using singleton instance
        db_adapter = await get_db()
        user_id = await db_adapter.get_or_create_user_by_email(
            email=current_user_email,
            firebase_uid=firebase_uid,
            display_name=firebase_user_data.get('displayName', current_user_email.split('@')[0])
        )
        
        if user_id:
            print(f"Auth middleware: User {current_user_email} ensured in database with Firebase UID {firebase_uid}")
        else:
            print(f"Failed to ensure user {current_user_email} in database")
        
        print(f"Auth middleware: Authentication successful for {current_user_email}, proceeding to protected page.")
        
        # Await the page_function if it's a coroutine
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    return wrapper

def get_user_display_name():
    """
    Get the display name of the current user.
    Returns None if user is not logged in or display name is not set.
    """
    FirebaseAuth._ensure_user_storage()
    current_user = FirebaseAuth.get_current_user()

    if current_user:
        # Pyrebase user object might store display name in 'displayName'
        # The user object from get_current_user() should also have it.
        display_name = current_user.get('displayName')
        if display_name:
            return display_name
        # Fallback to email if display name is not set
        return current_user.get('email', 'Usuario') 
    return 'Usuario' # Default if no user
