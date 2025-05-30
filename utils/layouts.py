from nicegui import ui, app
from utils.state import set_user_logout_state
from utils.database import PostgresAdapter
from datetime import datetime

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
        with ui.button(on_click=lambda: ui.navigate.to('/home')).classes('no-underline p-0'):
            ui.image('static/favicon.png').classes('h-8 w-8')
            
        # Middle - Navigation buttons for desktop
        with ui.row().classes('max-sm:hidden flex-grow justify-center gap-2'):
            ui.button('Home', icon='home', on_click=lambda: ui.navigate.to('/home')).props('flat color=white')
            ui.button('Chat', icon='chat', on_click=lambda: ui.navigate.to('/chat')).props('flat color=white')
            ui.button('Reports', icon='analytics', on_click=lambda: ui.navigate.to('/reportes')).props('flat color=white')
            
        # Right side - Mobile menu trigger and user menu
        with ui.row().classes('ml-auto items-center gap-2'):
            # Status indicator for both desktop and mobile (optional)
            # ui.icon('circle', color='green').classes('text-sm')
            
            # Desktop user menu
            with ui.element('div').classes('max-sm:hidden'):
                # Create menu first
                with ui.menu().classes('mt-2') as user_menu:
                    with ui.menu_item('Profile'):
                        ui.icon('person')
                    with ui.menu_item('Settings'):
                        ui.icon('settings')
                    ui.separator()
                    with ui.menu_item('Logout', on_click=clearSessionAndRedirect).classes('text-red-500'):
                        ui.icon('logout')
                
                # Then create button that opens the menu
                ui.button(icon='account_circle', on_click=user_menu.open).props('flat color=white')
            
            # Mobile navigation menu
            with ui.element('div').classes('sm:hidden'):
                # Create mobile menu
                with ui.menu().classes('mt-2') as mobile_menu:
                    with ui.menu_item('Home', on_click=lambda: ui.navigate.to('/home')):
                        ui.icon('home')
                    with ui.menu_item('Chat', on_click=lambda: ui.navigate.to('/chat')):
                        ui.icon('chat')
                    with ui.menu_item('Reports', on_click=lambda: ui.navigate.to('/reportes')):
                        ui.icon('analytics')
                    ui.separator()
                    with ui.menu_item('Profile'):
                        ui.icon('person')
                    with ui.menu_item('Settings'):
                        ui.icon('settings')
                    with ui.menu_item('Logout', on_click=clearSessionAndRedirect).classes('text-red-500'):
                        ui.icon('logout')
                
                # Button to open mobile menu
                ui.button(icon='menu', on_click=mobile_menu.open).props('flat color=white')

def create_date_range_selector(container=None, default_start_hour=0, default_end_hour=23):
    """Create a date range selector component
    
    Args:
        container: Optional UI container to place the component in
        default_start_hour: Default hour for start time (0-23)
        default_end_hour: Default hour for end time (0-23)
        
    Returns:
        Tuple of (start_date_input, start_hour, end_date_input, end_hour)
    """
    today = datetime.today().strftime('%Y-%m-%d')
    
    if container is None:
        container = ui
    
    with container.row().classes('w-full gap-4 items-end'):
        # Start date with dropdown calendar
        start_date_input = ui.input('Start Date', value=today).classes('w-1/6')
        start_date_input.props('dense outlined readonly')
        
        with ui.menu().props('no-parent-event') as start_menu:
            with ui.date(value=today).bind_value(start_date_input):
                with ui.row().classes('justify-end q-pa-sm'):
                    ui.button('Done', on_click=start_menu.close).props('flat color=primary')
        
        with start_date_input.add_slot('append'):
            ui.icon('event').on('click', start_menu.open).classes('cursor-pointer')
        
        # Start hour input
        start_hour = ui.number(value=default_start_hour, min=0, max=23, step=1, format='%d').classes('w-1/12')
        start_hour.props('dense outlined label="Hour"')
        
        # End date with dropdown calendar
        end_date_input = ui.input('End Date', value=today).classes('w-1/6')
        end_date_input.props('dense outlined readonly')
        
        with ui.menu().props('no-parent-event') as end_menu:
            with ui.date(value=today).bind_value(end_date_input):
                with ui.row().classes('justify-end q-pa-sm'):
                    ui.button('Done', on_click=end_menu.close).props('flat color=primary')
        
        with end_date_input.add_slot('append'):
            ui.icon('event').on('click', end_menu.open).classes('cursor-pointer')
        
        # End hour input
        end_hour = ui.number(value=default_end_hour, min=0, max=23, step=1, format='%d').classes('w-1/12')
        end_hour.props('dense outlined label="Hour"')
    
    return start_date_input, start_hour, end_date_input, end_hour

def create_user_selector(container=None, width='w-1/3'):
    """Create a user selector component
    
    Args:
        container: Optional UI container to place the component in
        width: CSS width class for the component
        
    Returns:
        Tuple of (user_select, refresh_function)
    """
    user_db = PostgresAdapter()
    
    if container is None:
        container = ui
    
    def load_user_options():
        conn = None
        # Use a dictionary for options (key: value pairs)
        options_dict = {'all': 'All Users'}
        
        try:
            conn = user_db.connection_pool.getconn()
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM fi_users ORDER BY user_id")
                rows = cursor.fetchall()
                
                # Add individual users to dictionary
                for row in rows:
                    user_id = row[0]  # Get the first element of the tuple
                    options_dict[str(user_id)] = f'User {user_id}'
                
            return options_dict
        except Exception as e:
            ui.notify(f'Error loading users: {str(e)}', type='negative')
            return {'error': 'Error loading users'}
        finally:
            if conn:
                try:
                    user_db.connection_pool.putconn(conn)
                except Exception as pool_e:
                    print(f"ERROR putting connection back to pool: {pool_e}")
    
    # Create user select with multi-selection
    user_options_dict = load_user_options()
    user_select = container.select(
        options=user_options_dict, 
        multiple=True,
        value=[]
    ).classes(width)
    user_select.props('dense outlined label="Select Users" clearable use-chips')
    
    def refresh_users():
        new_options_dict = load_user_options()
        user_select.options = new_options_dict
        user_select.value = []  # Reset selection
        ui.notify('User list refreshed', type='positive', position='bottom-right', timeout=1500)
    
    return user_select, refresh_users