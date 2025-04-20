from nicegui import ui, app
from typing import Optional
import uuid
from utils.layouts import create_navigation_menu, create_navigation_menu_2
from utils.database import create_user
from pages.reportes import reportes_page
from pages.admin import page_admin
from utils.state import  get_user_logout_state, set_user_logout_state


#logout = False

@app.on_startup
def on_startup():
    print("Starting up...")


@app.on_shutdown
def on_shutdown():
    print("Shutting down...")


# Initialize visit counter cookie
def get_visit_count() -> tuple[int, int]:
    if ('visits' in app.storage.browser and get_user_logout_state() == True) or ('visits' not in app.storage.browser):
        app.storage.browser['visits'] = 0
        app.storage.browser['session_id'] = str(uuid.uuid4())
        app.storage.browser['user_id'] = create_user(app.storage.browser['session_id'],True)
        set_user_logout_state(False)
        print(f'User created with id: {app.storage.browser["user_id"]}')

    app.storage.browser['visits'] += 1
    return app.storage.browser['user_id'], app.storage.browser['visits']

@ui.page('/')
def home():
    create_navigation_menu_2()
    with ui.header().classes('items-center justify-between'):
        ui.label('Reto a resolver').classes('text-h3')
    
    with ui.row():
        user_id, visits = get_visit_count()
        ui.label(f'Usuario: {user_id}')
        ui.label(f'Visits: {visits}')
        ui.label(f'Logout: {get_user_logout_state()}')

    ui.button('Ir a Reportes', on_click=lambda: ui.navigate.to('/reportes')).classes('bg-blue-500 text-white')

# Use a fixed secret key for development
secret_key = 'development_secret_key_1234567890'
ui.run(title='User Creation', port=8080, favicon='static/favicon.svg', storage_secret=secret_key) 
