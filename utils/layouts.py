from utils.database_singleton import get_db
from nicegui import ui, app
from utils.firebase_auth import FirebaseAuth
from utils.auth_middleware import get_user_display_name
from datetime import datetime, timedelta
import pytz

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
    # Use Firebase logout method instead of old state management
    logout_result = FirebaseAuth.logout_user()
    
    if logout_result.get("success"):
        # Clear browser storage and redirect
        ui.run_javascript("""
            // Clear all browser storage
            localStorage.clear();
            sessionStorage.clear();
            
            // Redirect to home page with special parameter
            window.location.href = '/home?newSession=true';
        """)
        
        ui.notify('Session logged out successfully', type='positive')
    else:
        ui.notify('Error logging out', type='negative')
        # Still try to clear browser storage and redirect even if Firebase logout fails
        ui.run_javascript("""
            localStorage.clear();
            sessionStorage.clear();
            window.location.href = '/home?newSession=true';
        """)

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
                    with ui.menu_item('Profile'): #, on_click=lambda: ui.navigate.to('/profile') # TODO: Uncomment this when deploy ready
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
                    with ui.menu_item('Profile', on_click=lambda: ui.navigate.to('/profile')):
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
    
    if container is None:
        container = ui
    
    async def load_user_options():
        # Use a dictionary for options (key: value pairs)
        options_dict = {'all': 'All Users'}
        
        try:
            user_db = await get_db()
            async with user_db.pool.acquire() as conn:
                rows = await conn.fetch("SELECT id FROM users ORDER BY id")
                
                # Add individual users to dictionary
                for row in rows:
                    user_id = row['id']
                    options_dict[str(user_id)] = f'User {user_id}'
                
            return options_dict
        except Exception as e:
            print(f'Error loading users: {str(e)}')  # Use print instead of ui.notify
            return {'error': 'Error loading users'}
    
    # Create user select with multi-selection
    # Start with empty value to avoid rendering issues
    user_select = container.select(
        options={'all': 'All Users'}, 
        multiple=True,
        value=[]  # Start empty, will be set after options load
    ).classes(width)
    user_select.props('dense outlined label="Select Users" clearable use-chips')
    
    async def refresh_users():
        try:
            new_options_dict = await load_user_options()
            
            # Set options first
            user_select.options = new_options_dict
            
            # Small delay to ensure options are rendered before setting value
            import asyncio
            await asyncio.sleep(0.1)
            
            # Then set default selection to only "All Users"
            user_select.value = ['all']  # Only select 'all' option by default
            
        except Exception as e:
            print(f'Error refreshing users: {str(e)}')  # Use print instead of ui.notify
    
    def refresh_users_sync():
        """Wrapper to call async refresh_users from sync context"""
        import asyncio
        asyncio.create_task(refresh_users())
    
    # Load initial options asynchronously
    import asyncio
    asyncio.create_task(refresh_users())
    
    return user_select, refresh_users_sync