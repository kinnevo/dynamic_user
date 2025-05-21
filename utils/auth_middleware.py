from nicegui import app, ui
from utils.firebase_auth import FirebaseAuth
from functools import wraps
import inspect # Import inspect module

def auth_required(page_function):
    """
    Decorator to enforce authentication for protected pages.
    Redirects to login page if user is not authenticated or token is invalid/expired.
    Relies on app.storage.user holding 'user_email' and 'firebase_user_data'.
    """
    @wraps(page_function)
    async def wrapper(*args, **kwargs): # Changed to async def
        FirebaseAuth._ensure_user_storage() # Ensure app.storage.user exists
            
        current_user_details = FirebaseAuth.get_current_user()
        
        if not current_user_details or not current_user_details.get('email') or not current_user_details.get('idToken'):
            print(f"Auth middleware: No authenticated user found (missing email or idToken), redirecting to login.")
            return ui.navigate.to('/login')
        
        user_email = current_user_details['email']
        id_token = current_user_details['idToken']
        
        try:
            print(f"Auth middleware: User {user_email} authenticated, verifying token...")
            verification = FirebaseAuth.verify_token(id_token)
            
            if not verification['success']:
                print(f"Auth middleware: Token verification failed for {user_email}. Attempting refresh.")
                refresh_token = current_user_details.get('refreshToken')
                
                if refresh_token:
                    refresh_result = FirebaseAuth.refresh_token(refresh_token)
                    if refresh_result['success'] and refresh_result.get('user'):
                        # Update stored firebase_user_data with new tokens
                        app.storage.user['firebase_user_data'] = refresh_result['user']
                        # Email should remain the same, but good to re-affirm if present in refresh_result['user']
                        if refresh_result['user'].get('email'):
                           app.storage.user['user_email'] = refresh_result['user'].get('email') 
                        print(f"Auth middleware: Token refreshed successfully for {user_email}.")
                    else:
                        print(f"Auth middleware: Token refresh failed for {user_email}. Error: {refresh_result.get('error')}. Redirecting to login.")
                        FirebaseAuth.logout_user() # Clear potentially corrupted session data
                        return ui.navigate.to('/login')
                else:
                    print(f"Auth middleware: No refresh token available for {user_email}. Redirecting to login.")
                    FirebaseAuth.logout_user()
                    return ui.navigate.to('/login')
            else:
                print(f"Auth middleware: Token for {user_email} verified successfully (UID: {verification.get('uid')}).")

        except Exception as e:
            print(f"Auth middleware: Exception during token check for {user_email}: {e}. Redirecting to login.")
            FirebaseAuth.logout_user()
            return ui.navigate.to('/login')
        
        print(f"Auth middleware: Authentication successful for {user_email}, proceeding to protected page.")
        
        # Await the page_function if it's a coroutine
        if inspect.iscoroutinefunction(page_function):
            return await page_function(*args, **kwargs)
        else:
            return page_function(*args, **kwargs)
    
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
