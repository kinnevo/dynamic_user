from nicegui import ui, app
from utils.layouts import create_navigation_menu
from utils.state import set_logout_state

@ui.page('/reportes')
def reportes_page():
    create_navigation_menu('/reportes')
    
    with ui.column().classes('w-full p-4'):
        ui.label('Reportes y Administración').classes('text-h4 q-mb-md')
        ui.button(
            'Volver al inicio', 
            on_click=lambda: clearSessionAndRedirect()
        ).classes('bg-blue-500 text-white')

def clearSessionAndRedirect():
    set_logout_state(True)  # Use the global state setter
    ui.notify('Sesión eliminada correctamente')
    ui.navigate.to('/')