from nicegui import ui, app
from utils.layouts import create_navigation_menu
from utils.state import set_user_logout_state, get_user_logout_state

@ui.page('/reportes')
def reportes_page():
    create_navigation_menu('/reportes')
    
    with ui.column().classes('w-full p-4'):
        ui.label('Reportes y Administración').classes('text-h4 q-mb-md')
