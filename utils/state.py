# Global state variables
logout = False

def get_user_logout_state():
    return logout

def set_user_logout_state(value: bool):
    global logout
    logout = value


# User status tracking
def update_user_status(identifier: str, status: str, is_email: bool = False):
    """Update the status of a user in the database.
       If is_email is False, identifier is treated as a legacy session_id.
    """
    from utils.database import PostgresAdapter
    db = PostgresAdapter()
    db.update_user_status(identifier, status, is_email=is_email)
