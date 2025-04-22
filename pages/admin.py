#!/usr/bin/env python3
import functools
from nicegui import ui
# Use the specific imports from your snippet
from utils.layouts import create_navigation_menu_2, create_date_range_selector, create_user_selector

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

def get_conversation_summaries():
    """Fetches conversation summaries from the database."""
    conn = None
    summaries = []
    try:
        conn = user_db.connection_pool.getconn()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    session_id, 
                    COUNT(*) AS message_count, 
                    MIN(timestamp) AS start_time, 
                    MAX(timestamp) AS last_activity
                FROM 
                    fi_messages 
                GROUP BY 
                    session_id
                ORDER BY 
                    last_activity DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                session_id, message_count, start_time, last_activity = row
                
                # Get the user_id for this session
                cursor.execute("SELECT user_id FROM fi_users WHERE session_id = %s", (session_id,))
                user_result = cursor.fetchone()
                user_id = user_result[0] if user_result else 'Unknown'
                
                summaries.append({
                    'session_id': session_id,
                    'user_id': user_id,
                    'message_count': message_count,
                    'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S") if start_time else 'Unknown',
                    'last_activity': last_activity.strftime("%Y-%m-%d %H:%M:%S") if last_activity else 'Unknown'
                })
                
        return summaries
    except Exception as e:
        ui.notify(f'Error fetching conversation summaries: {str(e)}', type='negative')
        return []
    finally:
        if conn:
            try:
                user_db.connection_pool.putconn(conn)
            except Exception as pool_e:
                print(f"ERROR putting connection back to pool: {pool_e}")

# --- Main Page Definition ---
@ui.page('/admin')
def page_admin():
    # Create navigation using your function
    create_navigation_menu_2()

    # --- Main Content Area ---
    with ui.column().classes('w-full items-center p-4'):
        # Use the title from your snippet
        ui.label('FastInnovation Admin').classes('text-h4 q-mb-md')

        # Create tabs for different admin panels
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('Users Table', icon='people')
            ui.tab('Conversation Summaries', icon='summarize')
        
        # Users Table Tab Panel
        with ui.tab_panels(tabs, value='Users Table').classes('w-full'):
            with ui.tab_panel('Users Table'):
                # --- Controls Row ---
                with ui.row().classes('w-full justify-between items-center mb-4'):
                    # Help text
                    ui.label('Click on any row to view detailed user information and conversation history').classes('text-sm text-gray-600')
                    # Refresh button - Use on_click method
                    users_refresh_button = ui.button('Refresh', icon='refresh', on_click=lambda: update_users_table()).props('flat color=primary')

                # --- Users Table Definition ---
                # Define columns - using name=field convention for easier slot handling
                users_columns = [
                    {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left', 'sortable': True},
                    {'name': 'session_id', 'field': 'session_id', 'label': 'Session ID', 'align': 'left', 'sortable': True},
                    {'name': 'logged', 'field': 'logged', 'label': 'Logged Status', 'align': 'center', 'sortable': True},
                    {'name': 'message_count', 'field': 'message_count', 'label': 'Messages', 'align': 'center', 'sortable': True},
                    {'name': 'start_time', 'field': 'start_time', 'label': 'Started', 'align': 'center', 'sortable': True},
                    {'name': 'last_activity', 'field': 'last_activity', 'label': 'Last Activity', 'align': 'center', 'sortable': True}
                ]

                # Create a standard NiceGUI table
                users_table = ui.table(
                    columns=users_columns,
                    rows=[],
                    pagination={'rowsPerPage': 25, 'page': 1}, 
                    row_key='user_id'  # Set row key for unique identification
                ).classes('w-full')
                
                # Add Quasar-specific props
                users_table.props('flat bordered separator=cell pagination-rows-per-page-options=[10,25,50,100]')

                # Add row-click event handler
                def handle_users_row_click(e):
                    # The event format is: [event, rowData, rowIndex]
                    if isinstance(e.args, list) and len(e.args) >= 2:
                        # The row data is the second element (index 1) in the args list
                        row_data = e.args[1]  
                        show_user_details(row_data)
                    else:
                        ui.notify("Could not retrieve row data", type="negative")
                        
                users_table.on('row-click', handle_users_row_click)
                
                # --- Data Update Function (Using your provided logic) ---
                def update_users_table():
                    """Fetches user data from the database and updates the table rows."""
                    conn = None # Initialize conn to None for the finally block
                    # Fetch user data from database
                    try:
                        # Use your database connection pool
                        conn = user_db.connection_pool.getconn()
                        cursor = conn.cursor()
                        
                        # Get basic user data
                        cursor.execute("SELECT user_id, session_id, logged, last_active FROM fi_users ORDER BY user_id")
                        user_rows = cursor.fetchall()
                        
                        # Data retrieved successfully
                        table_rows = []
                        
                        for row_tuple in user_rows:
                            user_id, session_id, logged, last_active = row_tuple
                            
                            # Get message count and timestamps for each user
                            cursor.execute("""
                                SELECT 
                                    COUNT(*) AS message_count, 
                                    MIN(timestamp) AS start_time, 
                                    MAX(timestamp) AS last_message
                                FROM 
                                    fi_messages 
                                WHERE 
                                    user_id = %s
                            """, (user_id,))
                            
                            msg_data = cursor.fetchone()
                            
                            if msg_data:
                                message_count, start_time, last_message = msg_data
                            else:
                                message_count, start_time, last_message = 0, None, None
                            
                            # Use last_active from users table if available, otherwise use last message timestamp
                            last_activity = last_active if last_active else last_message
                            
                            table_rows.append({
                                'user_id': user_id,
                                'session_id': session_id,
                                'logged': 'Yes' if logged else 'No',
                                'message_count': message_count,
                                'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S") if start_time else 'Never',
                                'last_activity': last_activity.strftime("%Y-%m-%d %H:%M:%S") if last_activity else 'Never'
                            })
                        
                        # Update the table component's rows
                        users_table.rows = table_rows
                        
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

                # Initial Data Load for Users Table
                update_users_table()
                
            # Conversation Summaries Tab Panel
            with ui.tab_panel('Conversation Summaries'):
                with ui.column().classes('w-full p-4'):
                    #ui.label('Conversation Summaries').classes('text-h5 q-mb-md')
                    
                    # Date range and user selection controls - Single row layout
                    ui.label('Selection Criteria').classes('text-subtitle1 q-mb-sm')
                    
                    # Create a single row to hold everything
                    with ui.row().classes('w-full gap-4 items-end'):
                        # Use a custom wrapper for better control
                        with ui.element('div').classes('flex gap-2 items-end flex-grow-1 w-2/3'):
                            # Create date range selectors in the same container
                            start_date_input, start_hour, end_date_input, end_hour = create_date_range_selector()
                        
                        # Create user selector in the same row with proper width
                        user_select, refresh_users = create_user_selector(width='w-1/3')
                    
                    # Control buttons row
                    with ui.row().classes('w-full justify-between mt-4'):
                        # Refresh users button
                        refresh_users_btn = ui.button('Refresh Users', icon='refresh', on_click=lambda: refresh_users()).props('flat')
                        
                        # Generate summaries button
                        generate_btn = ui.button('Generate Summaries', icon='analytics', on_click=lambda: generate_summaries())
                        generate_btn.props('color=primary')
                    
                    # Results container for summaries
                    results_container = ui.column().classes('w-full mt-4 border rounded p-4')
                    
                    # Placeholder text for empty results
                    with results_container:
                        ui.label('Select date range and users, then click "Generate Summaries"').classes('text-gray-500 italic text-center w-full py-8')
                    
                    # Function to generate summaries (will be implemented later)
                    def generate_summaries():
                        # Get selected values
                        start_dt = start_date_input.value
                        start_hr = start_hour.value
                        end_dt = end_date_input.value
                        end_hr = end_hour.value
                        selected_users = user_select.value
                        
                        # Format datetime for display
                        start_formatted = f"{start_dt} {int(start_hr):02d}:00:00" if start_dt else "Not selected"
                        end_formatted = f"{end_dt} {int(end_hr):02d}:00:00" if end_dt else "Not selected"
                        
                        # Clear previous results
                        results_container.clear()
                        
                        # Validate inputs
                        if not start_dt or not end_dt:
                            with results_container:
                                ui.label('Please select both start and end dates').classes('text-negative text-h6')
                            return
                        
                        if not selected_users:
                            with results_container:
                                ui.label('Please select at least one user').classes('text-negative text-h6')
                            return
                        
                        # Add placeholder message for now
                        with results_container:
                            ui.label('Generating summaries...').classes('text-h6 mb-2')
                            ui.separator()
                            
                            # Display selection criteria
                            with ui.column().classes('w-full mt-2'):
                                ui.label('Selection Criteria:').classes('font-bold')
                                ui.label(f'Date Range: {start_formatted} to {end_formatted}')
                                
                                # Format user selection display
                                if selected_users and 'all' in selected_users:
                                    ui.label('Selected Users: All Users')
                                elif selected_users:
                                    user_ids = ', '.join([f"User {uid}" for uid in selected_users])
                                    ui.label(f'Selected Users: {user_ids}')
                                else:
                                    ui.label('Selected Users: None')
                                
                            ui.label('This feature will be implemented in the next phase').classes('text-gray-500 italic mt-4')

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

# --- No ui.run() here, as it's part of an existing app ---