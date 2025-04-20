# Global state variables
logout = False

def get_user_logout_state():
    return logout

def set_user_logout_state(value: bool):
    global logout
    logout = value


# User status tracking
def update_user_status(session_id: str, status: str):
    """Update the status of a user in the database"""
    from utils.database import PostgresAdapter
    db = PostgresAdapter()
    db.update_user_status(session_id, status)
