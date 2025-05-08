from nicegui import ui, app


@ui.page('/')
def home():
    """Home page with navigation and basic user info"""
    create_navigation_menu_2()
    with ui.header().classes('items-center justify-between'):
        ui.label('Reto a resolver').classes('text-h3')
    
    with ui.row():
        ui.label('Usuario: jorge')
        visit_count = get_visit_count()
        ui.label(f'Visits: {visit_count}')
        ui.label(f'Logout: {logout}')

    # Navigation buttons
    ui.button('Ir a Reportes', on_click=lambda: ui.navigate.to('/reportes')).classes('bg-blue-500 text-white')
    # Add button to navigate to chat page
    ui.button('Chat con Langflow', on_click=lambda: ui.navigate.to('/chat')).classes('bg-green-500 text-white')
