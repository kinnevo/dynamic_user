from nicegui import ui, app
from utils.state import set_user_logout_state

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

def clearSessionAndRedirect():
    # Setting the logout state is fine as it's server-side
    set_user_logout_state(True)
    
    # Instead of trying to clear storage directly, use client-side JavaScript
    ui.run_javascript("""
        // Clear all browser storage
        localStorage.clear();
        sessionStorage.clear();
        
        // Redirect to home page with special parameter
        window.location.href = '/home?newSession=true';
    """)

    
    # This notification might not show since we're redirecting
    ui.notify('Sesión eliminada correctamente')

def create_navigation_menu_2():
    with ui.header().classes('items-center justify-between'):
        # Left side - Logo
        with ui.button(on_click=lambda: ui.navigate.to('/home')):
            ui.image('static/favicon.png').classes('h-8 w-8')
            
        # Middle - Navigation buttons
        with ui.row().classes('max-sm:hidden flex-grow justify-center'):
            ui.button('Home', icon='home', on_click=lambda: ui.navigate.to('/home')).props('flat color=white')
            ui.button('Chat', icon='chat', on_click=lambda: ui.navigate.to('/chat')).props('flat color=white')
            ui.button('Reports', icon='analytics', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            #ui.button('Admin', icon='supervisor_account', on_click=lambda: ui.navigate.to('/admin')).props('flat color=white')
            
        # Small screen navigation
        with ui.row().classes('sm:hidden'):
            ui.button(icon='home', on_click=lambda: ui.navigate.to('/home')).props('flat color=white')
            ui.button(icon='chat', on_click=lambda: ui.navigate.to('/chat')).props('flat color=white')
            ui.button(icon='analytics', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            #ui.button(icon='supervisor_account', on_click=lambda: ui.navigate.to('/admin')).props('flat color=white')
        
        # Right side - User menu with alignment fix
        with ui.element('div').classes('ml-auto'):
            # Create menu first
            with ui.menu().classes('mt-2') as menu:
                with ui.menu_item('Profile'):
                    ui.icon('person')
                with ui.menu_item('Settings'):
                    ui.icon('settings')
                ui.separator()
                with ui.menu_item('Logout', on_click=clearSessionAndRedirect).classes('text-red-500'):
                    ui.icon('logout')
            
            # Then create button that opens the menu
            ui.button(icon='menu', on_click=menu.open).props('flat color=white')