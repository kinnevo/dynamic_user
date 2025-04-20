#!/usr/bin/env python3
import functools
from nicegui import ui
# Use the specific imports from your snippet
from utils.layouts import create_navigation_menu_2

# Database connection
from utils.database import PostgresAdapter
user_db = PostgresAdapter()

# --- Dialog Handler Function ---
def show_user_details(user_data):
    """Creates and shows a dialog with user details and conversation history."""
    # Extract user data
    if isinstance(user_data, dict):
        session_id = user_data.get('session_id', 'N/A')
        user_id = user_data.get('user_id', 'N/A')
        logged = user_data.get('logged', 'N/A')
    else:
        # Unexpected data format
        return
    
    # Create a new dialog each time
    with ui.dialog() as dialog, ui.card().classes('w-[50vw] max-w-[75vw]').style('max-width: 75vw !important'):
        # Header
        with ui.row().classes('w-full bg-primary text-white p-4'):
            ui.label(f"Details for User: {user_id}").classes('text-h6')
        
        # User details section
        with ui.column().classes('p-4'):
            ui.label(f"User ID: {user_id}")
            ui.label(f"Session ID: {session_id}")
            ui.label(f"Logged Status: {logged}")
        
        # Messages section header
        ui.label('Recent Conversation').classes('text-h6 p-4 pt-0')
        
        # Messages container
        with ui.column().classes('w-full h-[500px] overflow-y-auto p-4 gap-2 border rounded mx-4'):
            # Fetch messages
            conn = None
            try:
                conn = user_db.connection_pool.getconn()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT role, content, timestamp FROM fi_messages WHERE session_id = %s ORDER BY timestamp DESC LIMIT 20",
                        (session_id,)
                    )
                    messages = cursor.fetchall()
                    messages.reverse()  # Show oldest messages first
                    
                    if not messages:
                        ui.label("No messages found for this session").classes('text-gray-500 italic')
                    
                    for role, content, timestamp in messages:
                        time_str = timestamp.strftime("%H:%M:%S") if timestamp else "Unknown time"
                        if role == 'user':
                            with ui.element('div').classes('self-end bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                                ui.label(f"{time_str}").classes('text-xs opacity-70 mb-1')
                                ui.markdown(content)
                        else:
                            with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                                ui.label(f"{time_str}").classes('text-xs opacity-70 mb-1') 
                                ui.markdown(content)
            except Exception as e:
                ui.label(f"Error fetching messages: {str(e)}").classes('text-red-500')
            finally:
                if conn:
                    try:
                        user_db.connection_pool.putconn(conn)
                    except Exception:
                        pass
        
        # Footer with close button
        with ui.row().classes('w-full justify-end p-4'):
            ui.button('Close', on_click=dialog.close).props('flat')
    
    dialog.open()

# --- Main Page Definition ---
@ui.page('/admin')
def page_admin():
    # Create navigation using your function
    create_navigation_menu_2()

    # --- Main Content Area ---
    with ui.column().classes('w-full items-center p-4'):
        # Use the title from your snippet
        ui.label('FastInnovation Admin').classes('text-h4 q-mb-md')

        # --- Controls Row ---
        with ui.row().classes('w-full justify-between items-center mb-4'):
            # Help text
            ui.label('Click on any row to view detailed user information and conversation history').classes('text-sm text-gray-600')
            # Refresh button - Use on_click method
            refresh_button = ui.button('Refresh', icon='refresh', on_click=lambda: update_table()).props('flat color=primary')

        # --- Table Definition ---
        # Define columns - using name=field convention for easier slot handling
        columns = [
            {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left', 'sortable': True},
            {'name': 'session_id', 'field': 'session_id', 'label': 'Session ID', 'align': 'left', 'sortable': True},
            {'name': 'logged', 'field': 'logged', 'label': 'Logged Status', 'align': 'center', 'sortable': True}
        ]

        # Create a standard NiceGUI table
        table = ui.table(
            columns=columns,
            rows=[],
            row_key='user_id'  # Set row key for unique identification
        ).classes('w-full')
        
        # Add Quasar-specific props
        table.props('flat bordered dense row-click pagination')

        # Add row-click event handler
        def handle_row_click(e):
            # The event format is: [event, rowData, rowIndex]
            if isinstance(e.args, list) and len(e.args) >= 2:
                # The row data is the second element (index 1) in the args list
                row_data = e.args[1]  
                show_user_details(row_data)
            else:
                ui.notify("Could not retrieve row data", type="negative")
                
        table.on('row-click', handle_row_click)
        
        # Add CSS classes to make rows appear clickable
        ui.add_head_html('''
        <style>
            .q-table tbody tr {
                cursor: pointer;
                transition: background-color 0.2s;
            }
            .q-table tbody tr:hover {
                background-color: rgba(59, 130, 246, 0.1);
            }
        </style>
        ''')
        
        # --- Data Update Function (Using your provided logic) ---
        def update_table():
            """Fetches user data from the database and updates the table rows."""
            conn = None # Initialize conn to None for the finally block
            # Fetch user data from database
            try:
                # Use your database connection pool
                conn = user_db.connection_pool.getconn()
                cursor = conn.cursor()
                # Use your SQL query
                cursor.execute("SELECT user_id, session_id, logged FROM fi_users ORDER BY user_id") # Added ORDER BY
                rows = cursor.fetchall()
                # Data retrieved successfully

                table_rows = []
                for row_tuple in rows: # Iterate through the tuples from fetchall
                    # Convert tuple to dictionary matching column fields
                    # This structure matches the user's snippet logic
                    table_rows.append({
                        'user_id': row_tuple[0],
                        'session_id': row_tuple[1],
                        'logged': 'Yes' if row_tuple[2] else 'No' # Convert boolean
                    })
                # Process complete

                # Update the table component's rows
                table.rows = table_rows
                
                # Show subtle notification
                if len(table_rows) > 0:
                    ui.notify(f"Loaded {len(table_rows)} users", type='positive', position='bottom-right', timeout=1500)

            except Exception as e:
                # Log the error and notify user
                # Use your notification style
                ui.notify(f'Error loading users: {str(e)}', type='negative', position='top-right')
            finally:
                # Ensure connection is returned to the pool using your logic
                if conn:
                    try:
                        user_db.connection_pool.putconn(conn)
                    except Exception as pool_e:
                        print(f"ERROR putting connection back to pool: {pool_e}")

        # No need for another helpful message, moved to above the table

        # --- Initial Data Load ---
        # Populate the table when the page is first loaded
        update_table()

# --- No ui.run() here, as it's part of an existing app ---