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

def create_navigation_menu_2():
    with ui.header().classes('items-center justify-between'):
        with ui.button(on_click=lambda: ui.navigate.to('/')):
            ui.avatar('favorite_border')
        #with ui.link('/'):
        #    ui.avatar('favorite_border')
        with ui.row().classes('max-sm:hidden'):
            ui.button('Shop', icon='shopping_cart').props('flat color=white')
            ui.button('Blog', icon='feed', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            ui.button('Contact', icon='perm_phone_msg').props('flat color=white')
        with ui.row().classes('sm:hidden'):
            ui.button(icon='shopping_cart').props('flat color=white')
            ui.button(icon='feed', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            ui.button(icon='perm_phone_msg').props('flat color=white')
        ui.button(icon='menu').props('flat color=white')
