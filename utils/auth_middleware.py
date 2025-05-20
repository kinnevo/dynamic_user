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
            print(f"Auth middleware: No user found in session, redirecting to login")
            return ui.navigate.to('/login')
        
        # If logged in, check token expiration
        # Firebase tokens expire after 1 hour
        try:
            print(f"Auth middleware: User authenticated, checking token for {user.get('email', 'unknown user')}")
            id_token = user.get('idToken')
            if id_token:
                # Verify the token
                verification = FirebaseAuth.verify_token(id_token)
                if not verification['success']:
                    print(f"Auth middleware: Token verification failed, attempting refresh")
                    # If token verification fails, try to refresh it
                    refresh_token = user.get('refreshToken')
                    if refresh_token:
                        refresh_result = FirebaseAuth.refresh_token(refresh_token)
                        if refresh_result['success']:
                            # Update the stored user data with new tokens
                            app.storage.user['user'] = refresh_result['user']
                            print(f"Auth middleware: Token refreshed successfully")
                        else:
                            # If refresh fails, redirect to login
                            print(f"Auth middleware: Token refresh failed, redirecting to login")
                            return ui.navigate.to('/login')
                    else:
                        # No refresh token, redirect to login
                        print(f"Auth middleware: No refresh token available, redirecting to login")
                        return ui.navigate.to('/login')
            else:
                # No ID token, redirect to login
                print(f"Auth middleware: No ID token found, redirecting to login")
                return ui.navigate.to('/login')
        except Exception as e:
            # Any error, redirect to login
            print(f"Auth middleware: Exception during authentication check: {e}")
            return ui.navigate.to('/login')
        
        # Everything is fine, proceed to the page
        print(f"Auth middleware: Authentication successful, proceeding to protected page")
        
        # Execute the original page function
        result = page_function(*args, **kwargs)
        return result
    
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
