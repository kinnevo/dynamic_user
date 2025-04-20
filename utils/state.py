# Global state variable
logout = False

def get_user_logout_state():
    return logout

def set_user_logout_state(value: bool):
    global logout
    logout = value