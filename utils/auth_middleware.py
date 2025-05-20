from nicegui import app, ui
from utils.firebase_auth import FirebaseAuth
from functools import wraps

def auth_required(page_function):
    """
    Decorator to enforce authentication for protected pages
    Redirects to login page if user is not authenticated
    """
    @wraps(page_function)
    def wrapper(*args, **kwargs):
        # Ensure user storage is initialized
        if not hasattr(app.storage, 'user'):
            app.storage.user = {}
            
        # Check if user is logged in
        user = FirebaseAuth.get_current_user()
        
        if not user:
            # If not logged in, redirect to login page
            return ui.navigate.to('/login')
        
        # If logged in, check token expiration
        # Firebase tokens expire after 1 hour
        try:
            id_token = user.get('idToken')
            if id_token:
                # Verify the token
                verification = FirebaseAuth.verify_token(id_token)
                if not verification['success']:
                    # If token verification fails, try to refresh it
                    refresh_token = user.get('refreshToken')
                    if refresh_token:
                        refresh_result = FirebaseAuth.refresh_token(refresh_token)
                        if refresh_result['success']:
                            # Update the stored user data with new tokens
                            app.storage.user['user'] = refresh_result['user']
                        else:
                            # If refresh fails, redirect to login
                            return ui.navigate.to('/login')
                    else:
                        # No refresh token, redirect to login
                        return ui.navigate.to('/login')
            else:
                # No ID token, redirect to login
                return ui.navigate.to('/login')
        except Exception:
            # Any error, redirect to login
            return ui.navigate.to('/login')
        
        # Everything is fine, proceed to the page
        return page_function(*args, **kwargs)
    
    return wrapper

def get_user_display_name():
    """
    Get the display name of the current user
    Returns None if user is not logged in
    """
    # Ensure user storage is initialized
    if not hasattr(app.storage, 'user'):
        app.storage.user = {}
        
    user = FirebaseAuth.get_current_user()
    if user:
        # Try to get display name from token or user info
        try:
            # Firebase might store display name in different places
            # depending on which auth method was used
            return user.get('displayName') or 'Usuario'
        except Exception:
            return 'Usuario'
    return None
