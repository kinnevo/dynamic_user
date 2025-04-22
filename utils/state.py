# Global state variables
logout = False

# The session to use for retrieving messages after a logout
# This is simpler than the previous approach and less prone to errors
post_logout_session_id = None

def get_user_logout_state():
    return logout

def set_user_logout_state(value: bool):
    global logout
    logout = value

def get_post_logout_session():
    """Get the session ID to use for message retrieval after logout"""
    global post_logout_session_id
    return post_logout_session_id

def set_post_logout_session(session_id: str):
    """Set the session ID to use for message retrieval after logout"""
    global post_logout_session_id
    post_logout_session_id = session_id

# User status tracking
def update_user_status(session_id: str, status: str):
    """Update the status of a user in the database"""
    try:
        from utils.database import PostgresAdapter
        db = PostgresAdapter()
        db.update_user_status(session_id, status)
    except Exception as e:
        # Fail silently - don't block the app for status updates
        print(f"Error updating user status: {e}")
        pass
