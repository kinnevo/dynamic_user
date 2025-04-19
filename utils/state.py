# Global state variables
from nicegui import app

def init_global_state():
    if 'logout' not in app.storage.global_:
        app.storage.global_['logout'] = False

def get_logout_state():
    return app.storage.global_.get('logout', False)

def set_logout_state(value: bool):
    app.storage.global_['logout'] = value