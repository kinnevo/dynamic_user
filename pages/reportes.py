from nicegui import ui, app
from utils.layouts import create_navigation_menu
from utils.state import logout

@ui.page('/reportes')
def reportes_page():
    create_navigation_menu('/reportes')
    with ui.column().classes('w-full items-center'):
        ui.label('Reportes y Administración').classes('text-h4 q-mb-md')
        ui.label('Reportes').classes('text.body q-mb-md')
         
        # Just navigate back, the counter is already reset
        ui.button(
            'Volver al inicio', 
            on_click=lambda: clearSessionAndRedirect()
        ).classes('bg-blue-500 text-white')

def clearSessionAndRedirect():
    global logout
    logout = True
    ui.notify('Sesión eliminada correctamente')
    ui.navigate.to('/')
