from nicegui import ui

def create_navigation_menu(current_page: str):
    """Create consistent navigation menu for all pages
    Args:
        current_page: Current page path to highlight active menu item
    """
    with ui.header().classes('bg-blue-500 text-white'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Mi Aplicación').classes('text-h6')
            
            with ui.row().classes('items-center'):
                # Home button
                with ui.button(on_click=lambda: ui.navigate.to('/')).classes(
                    'text-white ' + ('bg-blue-700' if current_page == '/' else '')
                ):
                    ui.icon('home')
                    ui.label('Inicio')
                
                # Reports button
                with ui.button(on_click=lambda: ui.navigate.to('/reportes')).classes(
                    'text-white ' + ('bg-blue-700' if current_page == '/reportes' else '')
                ):
                    ui.icon('analytics')
                    ui.label('Reportes')

# https://github.com/zauberzeug/nicegui/discussions/1715 
# icons library https://fonts.google.com/icons?icon.size=24&icon.color=%23e3e3e3

def create_navigation_menu_2():
    with ui.header().classes('items-center justify-between'):
        with ui.button(on_click=lambda: ui.navigate.to('/home')):
            ui.image('static/favicon.png').classes('h-8 w-8')
        with ui.row().classes('max-sm:hidden'):
            ui.button('Home', icon='home', on_click=lambda: ui.navigate.to('/home')).props('flat color=white')
            ui.button('Chat', icon='chat', on_click=lambda: ui.navigate.to('/chat')).props('flat color=white')
            ui.button('Reports', icon='analytics', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            ui.button('Admin', icon='analytics', on_click=lambda: ui.navigate.to('/admin')).props('flat color=white')
        with ui.row().classes('sm:hidden'):
            ui.button(icon='home', on_click=lambda: ui.navigate.to('/home')).props('flat color=white')
            ui.button(icon='chat', on_click=lambda: ui.navigate.to('/chat')).props('flat color=white')
            ui.button(icon='analytics', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            ui.button(icon='analytics', on_click=lambda: ui.navigate.to('/admin')).props('flat color=white')
        ui.button(icon='menu').props('flat color=white')
