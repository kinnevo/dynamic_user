#!/usr/bin/env python3
import functools
from nicegui import ui
from datetime import datetime
import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from collections import Counter

# Use the specific imports from your snippet
from utils.layouts import create_navigation_menu_2, create_date_range_selector, create_user_selector
from utils.summary_analyzer import SummaryAnalyzer

# Database connection
from utils.database import PostgresAdapter
user_db = PostgresAdapter()

# Initialize the summary analyzer
summary_analyzer = SummaryAnalyzer(model_name="gpt-4o")

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

        # Create tabs for different admin panels with persistent visibility
        with ui.tabs().classes('w-full').props('no-swipe-select keep-alive') as tabs:
            ui.tab('Users Table', icon='people')
            ui.tab('Conversation Summaries', icon='summarize')
            ui.tab('Macro Analysis', icon='analytics')
        
        # Store the current tab value in a shared state for persistence
        def on_tab_change(new_tab):
            print(f"Tab changed to: {new_tab}")
        
        tabs.on('update:model-value', on_tab_change)
        
        # Users Table Tab Panel
        with ui.tab_panels(tabs, value='Users Table').classes('w-full').props('animated keep-alive'):
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
                    
                    # Date range and user selection controls
                    ui.label('Selection Criteria').classes('text-subtitle1 q-mb-sm')
                    
                    # Create a custom implementation that uses the same building blocks
                    with ui.row().classes('w-full items-end'):
                        # Get today's date for default values
                        from datetime import datetime
                        today = datetime.today().strftime('%Y-%m-%d')
                        
                        # First date components - following same pattern as in layouts.py
                        start_date_input = ui.input('Start Date', value=today).classes('w-24 md:w-32')
                        start_date_input.props('dense outlined readonly')
                        
                        with ui.menu().props('no-parent-event') as start_menu:
                            with ui.date(value=today).bind_value(start_date_input):
                                with ui.row().classes('justify-end q-pa-sm'):
                                    ui.button('Done', on_click=start_menu.close).props('flat color=primary')
                        
                        with start_date_input.add_slot('append'):
                            ui.icon('event').on('click', start_menu.open).classes('cursor-pointer')
                            
                        # Start hour
                        start_hour = ui.number(value=0, min=0, max=23, step=1, format='%d').classes('w-16')
                        start_hour.props('dense outlined label="Hour"')
                        
                        # Separator
                        ui.label('to').classes('mx-2')
                        
                        # End date components
                        end_date_input = ui.input('End Date', value=today).classes('w-24 md:w-32')
                        end_date_input.props('dense outlined readonly')
                        
                        with ui.menu().props('no-parent-event') as end_menu:
                            with ui.date(value=today).bind_value(end_date_input):
                                with ui.row().classes('justify-end q-pa-sm'):
                                    ui.button('Done', on_click=end_menu.close).props('flat color=primary')
                        
                        with end_date_input.add_slot('append'):
                            ui.icon('event').on('click', end_menu.open).classes('cursor-pointer')
                            
                        # End hour
                        end_hour = ui.number(value=23, min=0, max=23, step=1, format='%d').classes('w-16')
                        end_hour.props('dense outlined label="Hour"')
                        
                        # User selection - use the function from layouts.py
                        user_select, refresh_users = create_user_selector(width='w-64 md:w-80 ml-auto')
                    
                    # Control buttons row
                    with ui.row().classes('w-full justify-between mt-4'):
                        # Refresh users button
                        #refresh_users_btn = ui.button('Refresh Users', icon='refresh', on_click=lambda: refresh_users()).props('flat')
                        
                        # Generate summaries button
                        generate_btn = ui.button('Generate Summaries', icon='analytics', on_click=lambda: generate_summaries())
                        generate_btn.props('color=primary')
                    
                    # Results container for summaries
                    results_container = ui.column().classes('w-full mt-4 border rounded p-4')
                    
                    # Placeholder text for empty results
                    with results_container:
                        ui.label('Select date range and users, then click "Generate Summaries"').classes('text-gray-500 italic text-center w-full py-8')
                    
                    # Function to generate summaries
                    def generate_summaries():
                        # Get selected values
                        start_dt = start_date_input.value
                        start_hr = int(start_hour.value)
                        end_dt = end_date_input.value
                        end_hr = int(end_hour.value)
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
                        
                        # Initialize progress_label to None (important for cleanup later)
                        progress_label = None
                        
                        # Add placeholder message for UI
                        with results_container:
                            ui.label('Fetching conversations...').classes('text-h6 mb-2')
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
                            
                            # Add progress indicator    
                            progress_label = ui.label('Processing...').classes('text-primary mt-4')
                        
                        try:
                            # Fetch conversations from database using new method
                            print(f"\n=== FETCHING CONVERSATIONS ===")
                            print(f"Date Range: {start_formatted} to {end_formatted}")
                            print(f"Selected Users: {selected_users}")
                            
                            # Get conversations with at least 2 messages (1 user + 1 assistant)
                            conversations = user_db.get_conversations_by_date_and_users(
                                start_date=start_dt,
                                start_hour=start_hr,
                                end_date=end_dt,
                                end_hour=end_hr,
                                user_ids=selected_users,
                                min_messages=2  # Only include conversations with at least 2 messages
                            )
                            
                            if not conversations:
                                results_container.clear()
                                with results_container:
                                    ui.label('No conversations found for the selected criteria').classes('text-h6 mt-4')
                                return
                            
                            # Update progress indicator
                            progress_label.text = f'Found {len(conversations)} conversations. Generating summaries...'
                            
                            # Get existing summaries for these sessions
                            session_ids = [conv['session_id'] for conv in conversations]
                            existing_summaries = user_db.get_summaries_for_sessions(session_ids)
                            
                            # Process each conversation
                            total_processed = 0
                            new_summaries = 0
                            already_summarized = len(existing_summaries)
                            
                            # Clear and rebuild results
                            results_container.clear()
                            # Set progress_label to None since it was removed when clearing the container
                            progress_label = None
                            
                            with results_container:
                                ui.label('Conversation Summaries').classes('text-h6 mb-2')
                                ui.separator()
                                
                                # Selection criteria display
                                with ui.column().classes('w-full mt-2 mb-4'):
                                    ui.label('Selection Criteria:').classes('font-bold')
                                    ui.label(f'Date Range: {start_formatted} to {end_formatted}')
                                    
                                    # Format user selection display
                                    if selected_users and 'all' in selected_users:
                                        ui.label('Selected Users: All Users')
                                    elif selected_users:
                                        user_ids = ', '.join([f"User {uid}" for uid in selected_users])
                                        ui.label(f'Selected Users: {user_ids}')
                                        
                                # Create a new progress label that won't be cleared
                                progress_label = ui.label('Processing...').classes('text-primary mt-4')
                                
                                # Process all conversations and generate summaries
                                for i, conv in enumerate(conversations):
                                    session_id = conv['session_id']
                                    user_id = conv['user_id']
                                    
                                    # Update progress on each iteration
                                    if progress_label:
                                        progress_label.text = f'Processing conversation {i+1} of {len(conversations)}...'
                                    
                                    # Check if summary exists already
                                    summary_text = None
                                    is_new_summary = False
                                    
                                    if session_id in existing_summaries:
                                        summary_text = existing_summaries[session_id]
                                        print(f"Using existing summary for session {session_id}")
                                    else:
                                        # Generate new summary
                                        print(f"Generating new summary for session {session_id}")
                                        summary_text = user_db.create_conversation_summary(session_id, user_id)
                                        if summary_text:
                                            new_summaries += 1
                                            is_new_summary = True
                                    
                                    if summary_text:
                                        total_processed += 1
                                        
                                        # Create a card for each summary
                                        with ui.card().classes('w-full mb-4'):
                                            with ui.row().classes('w-full justify-between items-center'):
                                                ui.label(f"User {user_id} - {conv['start_time'].strftime('%Y-%m-%d %H:%M')}").classes('text-subtitle1 font-bold')
                                                if is_new_summary:
                                                    ui.label('NEW').classes('bg-green-500 text-white text-xs px-2 py-1 rounded')
                                            
                                            ui.separator()
                                            
                                            with ui.column().classes('w-full p-2'):
                                                # Conversation metadata
                                                with ui.row().classes('text-xs text-gray-500 justify-between w-full'):
                                                    ui.label(f"Session ID: {session_id[:8]}...")
                                                    ui.label(f"Messages: {conv['message_count']}")
                                                
                                                # Summary content
                                                ui.markdown(summary_text).classes('w-full mt-2')
                                                
                                                # View details button
                                                with ui.row().classes('w-full justify-end'):
                                                    ui.button('View Details', icon='visibility',
                                                              on_click=lambda conv=conv: view_conversation_details(conv)).props('flat dense')
                            
                                # Summary statistics
                                ui.separator()
                                ui.label(f'Summary: {total_processed} conversations processed').classes('text-subtitle1 mt-4 font-bold')
                                ui.label(f'{new_summaries} new summaries generated, {already_summarized} existing summaries retrieved').classes('text-sm')
                                
                                # Remove progress label at the end by replacing its text
                                # (don't use delete() as it may already be removed from parent)
                                if progress_label:
                                    progress_label.text = f'Completed: {total_processed} conversations processed'
                            
                        except Exception as e:
                            # Print error to terminal
                            print(f"\nERROR generating summaries: {str(e)}")
                            
                            # Set progress_label to None since we're clearing container
                            progress_label = None
                            
                            # Show error in UI
                            results_container.clear()
                            with results_container:
                                ui.label(f'Error: {str(e)}').classes('text-negative')
                    
                    # Function to view conversation details in a dialog
                    def view_conversation_details(conversation):
                        """Show conversation details in a dialog."""
                        session_id = conversation['session_id']
                        user_id = conversation['user_id']
                        
                        with ui.dialog() as dialog, ui.card().classes('w-[60vw] max-w-[800px]'):
                            # Header
                            with ui.row().classes('w-full bg-primary text-white p-4'):
                                ui.label(f"Conversation Details - User {user_id}").classes('text-h6')
                            
                            # Metadata
                            with ui.column().classes('p-4'):
                                ui.label(f"Session ID: {session_id}")
                                start_time = conversation['start_time'].strftime('%Y-%m-%d %H:%M:%S')
                                end_time = conversation['end_time'].strftime('%Y-%m-%d %H:%M:%S')
                                ui.label(f"Time Range: {start_time} to {end_time}")
                                ui.label(f"Messages: {conversation['message_count']}")
                            
                            # Messages
                            ui.label('Messages').classes('text-h6 pl-4')
                            with ui.column().classes('w-full p-4 max-h-[400px] overflow-y-auto'):
                                for msg in conversation['messages']:
                                    time_str = msg['timestamp'].strftime("%H:%M:%S") if 'timestamp' in msg else ""
                                    
                                    if msg['role'] == 'user':
                                        with ui.element('div').classes('self-end bg-blue-100 p-3 rounded-lg my-2 max-w-[80%]'):
                                            ui.label(f"{time_str} - User").classes('text-xs opacity-70 mb-1')
                                            ui.markdown(msg['content'])
                                    else:
                                        with ui.element('div').classes('self-start bg-gray-100 p-3 rounded-lg my-2 max-w-[80%]'):
                                            ui.label(f"{time_str} - Assistant").classes('text-xs opacity-70 mb-1')
                                            ui.markdown(msg['content'])
                            
                            # Summary section
                            ui.label('Summary').classes('text-h6 pl-4')
                            with ui.column().classes('w-full p-4 bg-gray-50 rounded-lg mx-4 mb-4'):
                                # Get the summary
                                summaries = user_db.get_summaries_for_sessions([session_id])
                                summary = summaries.get(session_id, "No summary available")
                                ui.markdown(summary)
                            
                            # Footer with close button
                            with ui.row().classes('w-full justify-end p-4'):
                                ui.button('Close', on_click=dialog.close).props('flat color=primary')
                        
                        dialog.open()

            # Macro Analysis Tab Panel
            with ui.tab_panel('Macro Analysis'):
                with ui.column().classes('w-full p-4'):
                    ui.label('Conversation Macro Analysis').classes('text-h5 q-mb-md')
                    
                    # Date range and user selection controls
                    ui.label('Analysis Parameters').classes('text-subtitle1 q-mb-sm')
                    
                    with ui.row().classes('w-full items-end'):
                        # Get today's date for default values
                        today = datetime.today().strftime('%Y-%m-%d')
                        
                        # First date components - following same pattern as in layouts.py
                        start_date_input_macro = ui.input('Start Date', value=today).classes('w-24 md:w-32')
                        start_date_input_macro.props('dense outlined readonly')
                        
                        with ui.menu().props('no-parent-event') as start_menu_macro:
                            with ui.date(value=today).bind_value(start_date_input_macro):
                                with ui.row().classes('justify-end q-pa-sm'):
                                    ui.button('Done', on_click=start_menu_macro.close).props('flat color=primary')
                        
                        with start_date_input_macro.add_slot('append'):
                            ui.icon('event').on('click', start_menu_macro.open).classes('cursor-pointer')
                            
                        # Start hour
                        start_hour_macro = ui.number(value=0, min=0, max=23, step=1, format='%d').classes('w-16')
                        start_hour_macro.props('dense outlined label="Hour"')
                        
                        # Separator
                        ui.label('to').classes('mx-2')
                        
                        # End date components
                        end_date_input_macro = ui.input('End Date', value=today).classes('w-24 md:w-32')
                        end_date_input_macro.props('dense outlined readonly')
                        
                        with ui.menu().props('no-parent-event') as end_menu_macro:
                            with ui.date(value=today).bind_value(end_date_input_macro):
                                with ui.row().classes('justify-end q-pa-sm'):
                                    ui.button('Done', on_click=end_menu_macro.close).props('flat color=primary')
                        
                        with end_date_input_macro.add_slot('append'):
                            ui.icon('event').on('click', end_menu_macro.open).classes('cursor-pointer')
                            
                        # End hour
                        end_hour_macro = ui.number(value=23, min=0, max=23, step=1, format='%d').classes('w-16')
                        end_hour_macro.props('dense outlined label="Hour"')
                        
                        # User selection - use the function from layouts.py
                        user_select_macro, refresh_users_macro = create_user_selector(width='w-64 md:w-80 ml-auto')
                    
                    # Analysis options
                    with ui.row().classes('w-full mt-4 items-center'):
                        ui.label('Analysis Options:').classes('mr-4')
                        
                        with ui.card().classes('w-full p-4'):
                            with ui.row().classes('items-center justify-between'):
                                max_summaries_macro = ui.number(value=50, min=1, max=200, label='Max Summaries').classes('w-40')
                                max_summaries_macro.props('outlined')
                                
                                model_select_macro = ui.select(
                                    options=['gpt-4o', 'gpt-3.5-turbo'], 
                                    value='gpt-4o',
                                    label='Model'
                                ).classes('w-40')
                                
                                # Define generate_analysis function in advance 
                                async def generate_macro_analysis():
                                    try:
                                        # Get selected values
                                        start_dt = start_date_input_macro.value
                                        start_hr = int(start_hour_macro.value)
                                        end_dt = end_date_input_macro.value
                                        end_hr = int(end_hour_macro.value)
                                        selected_users = user_select_macro.value
                                        max_items = int(max_summaries_macro.value)
                                        model = model_select_macro.value
                                        
                                        # Force the tab to stay on Macro Analysis
                                        tabs.set_value("Macro Analysis")
                                        
                                        # Clear previous results
                                        analysis_container.clear()
                                        
                                        # Validate inputs
                                        if not start_dt or not end_dt:
                                            with analysis_container:
                                                ui.label('Please select both start and end dates').classes('text-negative text-h6')
                                            return
                                        
                                        if not selected_users:
                                            with analysis_container:
                                                ui.label('Please select at least one user').classes('text-negative text-h6')
                                            return
                                        
                                        # Show loading state
                                        with analysis_container:
                                            ui.label('Fetching and analyzing conversation summaries...').classes('text-h6 mb-2')
                                            loading_spinner = ui.spinner('dots', size='lg').classes('text-primary')
                                        
                                        # Configure the analyzer with the selected model
                                        global summary_analyzer
                                        summary_analyzer = SummaryAnalyzer(model_name=model)
                                        
                                        # Fetch summaries from database
                                        print("\n=== FETCHING SUMMARIES FOR ANALYSIS ===")
                                        print(f"Date Range: {start_dt} {start_hr}:00 to {end_dt} {end_hr}:00")
                                        print(f"Selected Users: {selected_users}")
                                        print(f"Max Items: {max_items}")
                                        print(f"Model: {model}")
                                        
                                        summaries = user_db.get_summaries_by_date_range(
                                            start_date=start_dt,
                                            start_hour=start_hr,
                                            end_date=end_dt,
                                            end_hour=end_hr,
                                            user_ids=selected_users,
                                            limit=max_items
                                        )
                                        
                                        print(f"Found {len(summaries)} summaries to analyze")
                                        
                                        if not summaries:
                                            analysis_container.clear()
                                            with analysis_container:
                                                ui.label('No conversation summaries found for the selected criteria').classes('text-h6 mt-4 text-center')
                                            return
                                        
                                        # Update UI to show progress
                                        analysis_container.clear()
                                        with analysis_container:
                                            ui.label(f'Found {len(summaries)} summaries. Starting analysis...').classes('text-h6 mb-2')
                                            loading_spinner = ui.spinner('dots', size='lg').classes('text-primary')
                                        
                                        # Analyze summaries
                                        print("\n=== STARTING ANALYSIS ===")
                                        analyzed_data = []
                                        
                                        for i, summary in enumerate(summaries):
                                            try:
                                                print(f"Analyzing summary {i+1}/{len(summaries)}: ID {summary.get('summary_id', 'unknown')}")
                                                analysis_container.clear()
                                                with analysis_container:
                                                    ui.label(f'Analyzing summary {i+1} of {len(summaries)}...').classes('text-h6 mb-2')
                                                    loading_spinner = ui.spinner('dots', size='lg').classes('text-primary')
                                                
                                                # Add to analyzed data
                                                result = summary_analyzer.analyze_summary(summary.get('summary', ''))
                                                print(f"  ✓ Analysis complete for summary {i+1}")
                                                
                                                analyzed_data.append({
                                                    **summary,
                                                    'analysis': result.model_dump()
                                                })
                                            except Exception as e:
                                                print(f"  ✗ Error analyzing summary {i+1}: {e}")
                                        
                                        print(f"Successfully analyzed {len(analyzed_data)}/{len(summaries)} summaries")
                                        
                                        # Save analysis results to database
                                        print("\n=== SAVING ANALYSIS RESULTS ===")
                                        analysis_results = []
                                        for item in analyzed_data:
                                            analysis_results.append({
                                                'summary_id': item['summary_id'], 
                                                'analysis': json.dumps(item['analysis'])
                                            })
                                        
                                        success = user_db.save_analysis_results(analysis_results)
                                        print(f"Saved analysis results to database: {'Success' if success else 'Failed'}")
                                        
                                        # Update UI with progress
                                        analysis_container.clear()
                                        with analysis_container:
                                            ui.label('Analysis complete. Generating visualizations...').classes('text-h6 mb-2')
                                            loading_spinner = ui.spinner('dots', size='lg').classes('text-primary')
                                        
                                        # Generate visualizations
                                        print("\n=== GENERATING VISUALIZATIONS ===")
                                        
                                        # Clear loading state and display results
                                        analysis_container.clear()
                                        
                                        # Display analysis summary
                                        with analysis_container:
                                            ui.label('Macro Analysis Results').classes('text-h5 mb-4')
                                            
                                            # Summary stats
                                            print("Generating summary statistics...")
                                            with ui.card().classes('w-full mb-4 p-4'):
                                                ui.label('Summary Statistics').classes('text-h6 mb-2')
                                                
                                                with ui.row().classes('w-full justify-between'):
                                                    ui.label(f'Total Conversations: {len(analyzed_data)}').classes('text-subtitle1')
                                                    ui.label(f'Date Range: {start_dt} to {end_dt}').classes('text-subtitle1')
                                                    ui.label(f'Analysis Model: {model}').classes('text-subtitle1')
                                            
                                            # Display visualizations with error handling for each
                                            try:
                                                # Display topic heatmap
                                                print("Generating topic heatmap...")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                                                    topic_heatmap = summary_analyzer.generate_topic_heatmap(analyzed_data)
                                                    print(f"Topic heatmap generated: {type(topic_heatmap)}")
                                                    ui.plotly(topic_heatmap).classes('w-full h-[400px]')
                                            except Exception as e:
                                                print(f"Error generating topic heatmap: {e}")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                                                    ui.label(f'Error generating visualization: {str(e)}').classes('text-negative')
                                            
                                            try:
                                                # Display satisfaction chart
                                                print("Generating satisfaction chart...")
                                                with ui.row().classes('w-full gap-4'):
                                                    with ui.card().classes('w-1/2 p-4'):
                                                        ui.label('User Satisfaction').classes('text-h6 mb-2')
                                                        satisfaction_chart = summary_analyzer.generate_satisfaction_chart(analyzed_data)
                                                        print(f"Satisfaction chart generated: {type(satisfaction_chart)}")
                                                        ui.plotly(satisfaction_chart).classes('w-full h-[350px]')
                                                    
                                                    with ui.card().classes('w-1/2 p-4'):
                                                        ui.label('Conversation Types').classes('text-h6 mb-2')
                                                        types_chart = summary_analyzer.generate_conversation_types_chart(analyzed_data)
                                                        print(f"Conversation types chart generated: {type(types_chart)}")
                                                        ui.plotly(types_chart).classes('w-full h-[350px]')
                                            except Exception as e:
                                                print(f"Error generating charts: {e}")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Charts').classes('text-h6 mb-2')
                                                    ui.label(f'Error generating charts: {str(e)}').classes('text-negative')
                                            
                                            try:
                                                # Display top questions table
                                                print("Generating questions table...")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Top User Questions').classes('text-h6 mb-2')
                                                    questions_table = summary_analyzer.generate_top_questions_table(analyzed_data, top_n=15)
                                                    print(f"Questions table generated: {type(questions_table)}")
                                                    ui.plotly(questions_table).classes('w-full')
                                            except Exception as e:
                                                print(f"Error generating questions table: {e}")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Top User Questions').classes('text-h6 mb-2')
                                                    ui.label(f'Error generating questions table: {str(e)}').classes('text-negative')
                                            
                                            # Force the tab to stay on Macro Analysis
                                            tabs.set_value("Macro Analysis")
                                            
                                            print("All visualizations complete")
                                            ui.notify("Analysis complete!", type="positive", timeout=5000)
                                        
                                    except Exception as e:
                                        import traceback
                                        print(f"\n=== ERROR GENERATING ANALYSIS ===")
                                        print(f"Error: {str(e)}")
                                        print(traceback.format_exc())
                                        
                                        analysis_container.clear()
                                        with analysis_container:
                                            ui.label('Error Generating Analysis').classes('text-h6 text-negative')
                                            ui.markdown(f"**Error message:** {str(e)}").classes('text-negative')
                                            ui.label('Please check the console for more details.').classes('text-sm mt-2')
                                            
                                            # Add a retry button
                                            ui.button('Try Again', icon='refresh', on_click=generate_macro_analysis).props('color=primary mt-4')
                                        
                                        # Force the tab to stay on Macro Analysis even on error
                                        tabs.set_value("Macro Analysis")
                                        
                                        # Show error notification
                                        ui.notify("Error generating analysis. See details in the panel.",
                                                type="negative",
                                                position="top-right",
                                                timeout=5000)
                                
                                # Generate analysis button
                                analyze_btn = ui.button('Generate Analysis', icon='analytics', on_click=generate_macro_analysis)
                                analyze_btn.props('color=primary size=lg')
                    
                    # Results container for analysis with minimum height to prevent collapse
                    analysis_container = ui.column().classes('w-full mt-4 border rounded p-4 min-h-[500px]')
                    
                    # Placeholder text for empty results
                    with analysis_container:
                        ui.label('Select date range and users, then click "Generate Analysis"').classes('text-gray-500 italic text-center w-full py-8')
                    
                    # Add help information about the Macro Analysis feature
                    with ui.expansion('How to use Macro Analysis', icon='help').classes('w-full mt-4'):
                        ui.markdown("""
                        ### Understanding Macro Analysis
                        
                        This tool provides aggregated insights across multiple conversations to identify patterns and trends.
                        
                        **Key Features:**
                        - **Topic Sentiment Analysis**: Visualizes common topics and associated sentiments
                        - **User Satisfaction**: Measures overall satisfaction levels across conversations
                        - **Conversation Types**: Categorizes conversations by their primary purpose
                        - **Key Questions**: Identifies the most frequent questions asked by users
                        - **Action Items**: Highlights the most common next steps or action items
                        
                        **How to use:**
                        1. Select a date range and user(s)
                        2. Set the maximum number of summaries to analyze
                        3. Choose the AI model (GPT-4o recommended for best results)
                        4. Click "Generate Analysis"
                        5. Explore the visualizations and tables to understand conversation patterns
                        
                        The analysis is saved to the database, so you can quickly retrieve it in the future.
                        """)
        
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