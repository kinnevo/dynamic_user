from nicegui import ui, app
from typing import Optional
import uuid
from utils.layouts import create_navigation_menu, create_navigation_menu_2
from utils.database import create_user
from pages.reportes import reportes_page
from utils.state import init_global_state, get_logout_state, set_logout_state


#logout = False

@app.on_startup
def on_startup():
    print("Starting up...")
    init_global_state()  # Initialize the global state


@app.on_shutdown
def on_shutdown():
    print("Shutting down...")

def get_user_logout() -> bool:
    return False
# Initialize visit counter cookie
def get_visit_count() -> int:
    if ('visits' in app.storage.browser and get_user_logout() == True) or ('visits' not in app.storage.browser):
        app.storage.browser['visits'] = 0
        app.storage.browser['session_id'] = str(uuid.uuid4())
        app.storage.browser['user_id'] = create_user(app.storage.browser['session_id'])
    app.storage.browser['visits'] += 1
    return app.storage.browser['visits']

@ui.page('/')
def home():
    if get_logout_state():  # Check the global state
        # Handle logout logic here
        set_logout_state(False)  # Reset the logout flag
    create_navigation_menu_2()
    with ui.header().classes('items-center justify-between'):
        ui.label('Reto a resolver').classes('text-h3')
    
    with ui.row():
        ui.label('Usuario: jorge')
        visit_count = get_visit_count()
        ui.label(f'Visits: {visit_count}')
        ui.label(f'Logout: {logout}')

    ui.button('Ir a Reportes', on_click=lambda: ui.navigate.to('/reportes')).classes('bg-blue-500 text-white')

# Use a fixed secret key for development
secret_key = 'development_secret_key_1234567890'
ui.run(title='User Creation', port=8080, favicon='static/favicon.svg', storage_secret=secret_key) 
