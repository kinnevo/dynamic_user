#!/usr/bin/env python3
from nicegui import ui
from datetime import datetime
import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import httpx
import os
from dotenv import load_dotenv
import asyncio

# Use the specific imports from your snippet
from utils.layouts import create_navigation_menu_2 #, create_date_range_selector, create_user_selector # Removed unused imports

# Load environment variables
load_dotenv()

# # API Configuration
# API_BASE_URL = "https://fireportes-production.up.railway.app/api/v1"
API_BASE_URL = "http://localhost:8000/api/v1/"
API_KEY = os.getenv("FI_ANALYTICS_API_KEY")

if not API_KEY:
    print("ERROR: FI_ANALYTICS_API_KEY not found in environment variables.")
    # Handle missing API key appropriately, maybe raise an error or show a message
    # For now, we'll allow it to proceed but API calls will likely fail.
    
API_HEADERS = {"X-API-Key": API_KEY}

# --- Helper Function for API Calls ---
async def api_request(method: str, endpoint: str, client=None, params: dict = None, json_data: dict = None) -> dict | None:
    """Makes an asynchronous API request and uses client for notifications if provided."""
    # Explicitly check for API_KEY before making the call
    if not API_KEY:
         print("Aborting API call: FI_ANALYTICS_API_KEY is missing or empty in environment.")
         # Use client JS if available
         if client and client.has_socket_connection:
             js_command = "Quasar.plugins.Notify.create({ message: 'API Key is missing. Cannot fetch data.', type: 'negative' })"
             client.run_javascript(js_command)
         else: # Fallback if no client
             try: ui.notify("API Key is missing. Cannot fetch data.", type='negative')
             except Exception: pass # Avoid error if notify fails here too
         return None
         
    # Recreate headers here
    headers = {"X-API-Key": API_KEY}
    
    async with httpx.AsyncClient(base_url=API_BASE_URL, headers=headers, timeout=30.0) as http_client:
        try:
            print(f"--> Making API request: {method} {http_client.build_request(method, endpoint, params=params, json=json_data).url}") # Log the request URL
            response = await http_client.request(method, endpoint, params=params, json=json_data)
            print(f"<-- Received API response: {response.status_code}") # Log the status code
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()
        except httpx.RequestError as exc:
            print(f"A network error occurred while requesting {exc.request.url!r}: {exc}") 
            # Use client JS if available
            if client and client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Network error contacting API: {str(exc).replace('\'', '\\\'')}', type: 'negative' }})" # Basic escaping
                client.run_javascript(js_command)
            else:
                try: ui.notify(f"Network error contacting API: {exc}", type='negative')
                except Exception: pass
            return None
        except httpx.HTTPStatusError as exc:
            print(f"HTTP error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
            # Use client JS if available
            if client and client.has_socket_connection:
                error_message = exc.response.text[:100].replace('\'', '\\\'').replace('`', '\\`') # Basic escaping
                js_command = f"Quasar.plugins.Notify.create({{ message: 'API Error ({exc.response.status_code}): {error_message}...', type: 'negative' }})"
                client.run_javascript(js_command)
            else:
                try: ui.notify(f"API Error ({exc.response.status_code}): {exc.response.text[:100]}...", type='negative')
                except Exception: pass
            return None
        except Exception as e:
            import traceback
            print(f"An unexpected error occurred during API call: {e}")
            print(traceback.format_exc())
            # Use client JS if available
            if client and client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Unexpected API error: {str(e).replace('\'', '\\\'')}', type: 'negative' }})" # Basic escaping
                client.run_javascript(js_command)
            else:
                try: ui.notify(f"Unexpected API error: {e}", type='negative')
                except Exception: pass
            return None

# --- Dialog Handler Function ---
async def show_user_details(user_data, client=None):
    """Creates and shows a dialog with user details and conversation history."""
    # Extract user data
    if isinstance(user_data, dict):
        session_id = user_data.get('session_id', 'N/A')
        user_id = user_data.get('user_id', 'N/A')
        logged = user_data.get('logged', 'N/A')
    else:
        # Unexpected data format
        return
    
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
        with ui.column().classes('w-full h-[500px] overflow-y-auto p-4 gap-2 border rounded mx-4') as messages_container:
            # Show loading state initially
            with messages_container:
                ui.spinner(size='lg').classes('mx-auto')
        
        # Footer with close button
        with ui.row().classes('w-full justify-end p-4'):
            ui.button('Close', on_click=dialog.close).props('flat')
    
    dialog.open()

    # Fetch messages asynchronously after opening the dialog
    messages_data = await api_request('GET', f'/sessions/{session_id}/recent-messages', client=client, params={'limit': 20})
    
    # Clear loading spinner and populate messages
    messages_container.clear()
    
    if messages_data and isinstance(messages_data, list):
        if not messages_data:
            with messages_container:
                ui.label("No messages found for this session").classes('text-gray-500 italic')
        else:
            messages_data.sort(key=lambda x: x.get('timestamp', '')) # Sort by timestamp if needed (API might return sorted)
            with messages_container:
                for msg in messages_data:
                    role = msg.get('role')
                    content = msg.get('content')
                    timestamp_str = msg.get('timestamp')
                    
                    # Parse timestamp safely
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else None
                        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "Unknown time"
                    except ValueError:
                        time_str = timestamp_str if timestamp_str else "Invalid time format" # Display raw string if parsing fails

                    if role == 'user':
                        with ui.element('div').classes('self-end bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                            ui.label(f"{time_str}").classes('text-xs opacity-70 mb-1')
                            ui.markdown(content)
                    elif role == 'assistant' or role == 'ai': # Handle potential 'ai' role
                         with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                            ui.label(f"{time_str}").classes('text-xs opacity-70 mb-1')
                            ui.markdown(content)
                    else: # Handle unknown roles if necessary
                        with ui.element('div').classes('self-center bg-yellow-100 p-3 rounded-lg max-w-[80%]'):
                             ui.label(f"{time_str} - Role: {role}").classes('text-xs opacity-70 mb-1')
                             ui.markdown(content)

    elif messages_data is None: # API call failed
        with messages_container:
            ui.label(f"Error fetching messages. Check API connection.").classes('text-red-500')
    else: # Unexpected data format
        with messages_container:
            ui.label(f"Unexpected data format received for messages.").classes('text-orange-500')

# --- Admin Page Manager Class --- 
class AdminPageManager:
    def __init__(self):
        # Initialize pagination with rowsNumber = 0 (will be updated after fetch)
        self.pagination_state = {'page': 1, 'rowsPerPage': 25, 'rowsNumber': 0, 'sortBy': 'user_id', 'descending': False}
        self.users_table = None  
        self.analysis_container = None 
        self.client = None

    async def handle_users_row_click(self, e):
        """Handles row clicks, showing user details."""
        print(f"Row selected: {e}")
        if isinstance(e, dict):  # Check if we got row data
            await show_user_details(e, client=self.client)
        elif e is None: pass # Handle deselection if needed
        else: 
            if self.client and self.client.has_socket_connection:
                 js_command = "Quasar.plugins.Notify.create({ message: 'Could not interpret row click event data', type: 'negative' })"
                 self.client.run_javascript(js_command)

    async def get_users_page(self, props=None): # props is not strictly needed anymore, but keep for compatibility if called differently
        """Fetches ALL user data from the API endpoint and updates the table for client-side pagination."""
        if not self.users_table: return
            
        print(f"--> Requesting ALL users from paginated endpoint...")
        # Fetch data from the endpoint. No skip/limit needed as it returns all.
        # !!! UPDATE '/users/paginated' if the final endpoint path is different !!!
        response_data = await api_request('GET', '/users/paginated', client=self.client) # Remove params for skip/limit

        table_rows = []
        total_users = 0

        if response_data and isinstance(response_data, dict) and 'users' in response_data and 'total_users' in response_data:
            users_data = response_data['users'] # Get all users from the response
            total_users = response_data['total_users']
            print(f"<-- Received {len(users_data)} users (total: {total_users})")

            # Process all received users
            for user in users_data:
                # Format last_active safely
                last_active_str = 'Never'
                raw_last_active = user.get('last_active')
                if raw_last_active:
                    try:
                        last_active_str = datetime.fromisoformat(raw_last_active).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        last_active_str = raw_last_active
                
                table_rows.append({
                    'user_id': user.get('user_id'),
                    'session_id': user.get('session_id'),
                    'logged': 'Yes' if user.get('logged', False) else 'No',
                    'message_count': user.get('message_count', 0), # Get message_count directly
                    'start_time': 'Never', # Still default or get from API if available
                    'last_activity': last_active_str
                })
            
            # Update table rows - provide ALL rows to the table
            self.users_table.rows = table_rows
            
            # Update table pagination state - crucial for client-side pagination controls
            # Set rowsNumber to the total count received from the API
            # Keep the current page and rowsPerPage settings.
            current_pagination = self.users_table.pagination # Get the current state from the table component
            new_pagination = dict(current_pagination) # Create a mutable copy
            new_pagination['rowsNumber'] = total_users # Set the total count
            # Ensure current page is valid if total_users is less than (page-1)*rowsPerPage
            if total_users > 0 and new_pagination['page'] > (total_users + new_pagination['rowsPerPage'] - 1) // new_pagination['rowsPerPage']: # Calculate max page and check
                 new_pagination['page'] = 1 # Reset to first page if current page is out of bounds
                 if self.client and self.client.has_socket_connection:
                     js_command = "Quasar.plugins.Notify.create({ message: 'Page out of bounds, resetting to page 1.', type: 'warning', position: 'bottom' })"
                     self.client.run_javascript(js_command)

            self.users_table.pagination = new_pagination 
            self.pagination_state.update(new_pagination) # Keep internal state sync

            # Send notification
            if self.client and self.client.has_socket_connection:
                 js_command = f"Quasar.plugins.Notify.create({{ message: 'Loaded {len(table_rows)} of {total_users} users.', type: 'positive', position: 'bottom-right', timeout: 1500 }})"
                 self.client.run_javascript(js_command)
        else:
            print("ERROR: Invalid response format from users endpoint or API error.")
            self.users_table.rows = []
            # Reset pagination on error
            self.users_table.pagination = {'page': 1, 'rowsPerPage': 25, 'rowsNumber': 0}
            self.pagination_state.update(self.users_table.pagination)
            
            # Notification handled by api_request now

    async def initial_load(self):
        """Performs the initial data load by fetching all users."""
        print("Performing initial user load...")
        # Call get_users_page to fetch all data
        await self.get_users_page()
        
    async def generate_macro_analysis(self, max_summaries_input, tabs_ref): # Pass UI elements if needed
        """Handles the macro analysis generation."""
        if not self.analysis_container: return
        
        # Force the tab to stay on Macro Analysis
        tabs_ref.set_value("Macro Analysis")
        
        limit = int(max_summaries_input.value)
        top_n_questions = 15
        self.analysis_container.clear()

        with self.analysis_container:
            ui.label('Fetching and visualizing analysis data...').classes('text-h6 mb-2')
            ui.spinner('dots', size='lg').classes('text-primary')
        tabs_ref.set_value("Macro Analysis")

        print(f"\n=== FETCHING VISUALIZATION DATA (limit={limit}) ===")
        results = await asyncio.gather(
            api_request('GET', '/visualizations/topic-heatmap', client=self.client, params={'limit': limit}),
            api_request('GET', '/visualizations/satisfaction-chart', client=self.client, params={'limit': limit}),
            api_request('GET', '/visualizations/conversation-types-chart', client=self.client, params={'limit': limit}),
            api_request('GET', '/visualizations/questions-table', client=self.client, params={'limit': limit, 'top_n': top_n_questions}),
            return_exceptions=True
        )
        
        topic_heatmap_data, satisfaction_chart_data, types_chart_data, questions_table_data = results
        errors = []
        if isinstance(topic_heatmap_data, Exception) or topic_heatmap_data is None: errors.append(f"Topic Heatmap: {topic_heatmap_data or 'No data'}"); topic_heatmap_data = None
        if isinstance(satisfaction_chart_data, Exception) or satisfaction_chart_data is None: errors.append(f"Satisfaction Chart: {satisfaction_chart_data or 'No data'}"); satisfaction_chart_data = None
        if isinstance(types_chart_data, Exception) or types_chart_data is None: errors.append(f"Conversation Types Chart: {types_chart_data or 'No data'}"); types_chart_data = None
        if isinstance(questions_table_data, Exception) or questions_table_data is None: errors.append(f"Questions Table: {questions_table_data or 'No data'}"); questions_table_data = None
            
        self.analysis_container.clear()
        tabs_ref.set_value("Macro Analysis")

        with self.analysis_container:
            ui.label('Macro Analysis Results').classes('text-h5 mb-4')
            if errors:
                with ui.card().classes('w-full mb-4 p-4 bg-red-100'):
                    ui.label('Errors Fetching Data:').classes('text-h6 text-negative mb-2')
                    for error in errors: ui.label(f"- {error}").classes('text-negative')
                # Use client.run_javascript to trigger notification
                if self.client and self.client.has_socket_connection:
                    js_command = f"Quasar.plugins.Notify.create({{ message: 'Some analysis data failed to load.', type: 'warning' }})"
                    self.client.run_javascript(js_command)
            
            with ui.card().classes('w-full mb-4 p-4'):
                ui.label('Analysis Parameters').classes('text-h6 mb-2')
                with ui.row().classes('w-full justify-between'):
                    ui.label(f'Max Conversations Analyzed: {limit}').classes('text-subtitle1')
            tabs_ref.set_value("Macro Analysis")

            print("\n=== GENERATING VISUALIZATIONS FROM API DATA ===")
            # --- Generate Visualizations (using Plotly as before) ---
            # Heatmap
            try:
                if topic_heatmap_data:
                    with ui.card().classes('w-full mb-4 p-4'):
                        ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                        fig = go.Figure(data=go.Heatmap(
                            z=topic_heatmap_data.get('counts', []), x=topic_heatmap_data.get('sentiments', []),
                            y=topic_heatmap_data.get('topics', []), colorscale='Viridis',
                            text = [[f"Importance: {imp}<br>Count: {cnt}" for imp, cnt in zip(imp_row, cnt_row)] for imp_row, cnt_row in zip(topic_heatmap_data.get('importance_values', []), topic_heatmap_data.get('counts', []))],
                            hoverinfo='text'
                        ))
                        fig.update_layout(title='Topic Sentiment Heatmap (Counts)', xaxis_title="Sentiment", yaxis_title="Topic", autosize=True, margin=dict(l=100, r=50, t=80, b=50), height=500)
                        ui.plotly(fig).classes('w-full').props('responsive=true').style('height: 500px; max-width: 100%; overflow: visible;')
                else:
                    with ui.card().classes('w-full mb-4 p-4'): ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2'); ui.label('Data not available.').classes('text-gray-500 italic')
            except Exception as e: print(f"Error generating topic heatmap: {e}"); ui.label(f'Error: {str(e)}').classes('text-negative')
            # Satisfaction / Types Charts
            with ui.row().classes('w-full flex flex-col md:flex-row gap-4 my-4'):
                try:
                    if satisfaction_chart_data:
                        with ui.card().classes('w-full md:w-1/2 p-4'):
                            ui.label('User Satisfaction').classes('text-h6 mb-2')
                            fig_satisfaction = go.Figure(data=[go.Bar(x=satisfaction_chart_data.get('satisfaction_levels', []), y=satisfaction_chart_data.get('counts', []), marker_color='#1f77b4')])
                            fig_satisfaction.update_layout(title='User Satisfaction Distribution', xaxis_title="Satisfaction Level (1-5)", yaxis_title="Number of Conversations", autosize=True, margin=dict(l=30, r=30, t=50, b=50), height=350)
                            ui.plotly(fig_satisfaction).classes('w-full').props('responsive=true').style('height: 350px; max-width: 100%; overflow: visible;')
                    else: 
                        with ui.card().classes('w-full md:w-1/2 p-4'): ui.label('User Satisfaction').classes('text-h6 mb-2'); ui.label('Data not available.').classes('text-gray-500 italic')
                except Exception as e: print(f"Error generating satisfaction chart: {e}"); ui.label(f'Error: {str(e)}').classes('text-negative')
                try:
                    if types_chart_data:
                        with ui.card().classes('w-full md:w-1/2 p-4'):
                            ui.label('Conversation Types').classes('text-h6 mb-2')
                            fig_types = go.Figure(data=[go.Pie(labels=types_chart_data.get('types', []), values=types_chart_data.get('counts', []), hole=.3)])
                            fig_types.update_layout(title='Distribution of Conversation Types', autosize=True, margin=dict(l=30, r=30, t=50, b=50), height=350, legend_title_text='Types')
                            ui.plotly(fig_types).classes('w-full').props('responsive=true').style('height: 350px; max-width: 100%; overflow: visible;')
                    else: 
                        with ui.card().classes('w-full md:w-1/2 p-4'): ui.label('Conversation Types').classes('text-h6 mb-2'); ui.label('Data not available.').classes('text-gray-500 italic')
                except Exception as e: print(f"Error generating types chart: {e}"); ui.label(f'Error: {str(e)}').classes('text-negative')
            # Questions Table
            try:
                if questions_table_data:
                    with ui.card().classes('w-full mb-4 p-4'):
                        ui.label('Top User Questions').classes('text-h6 mb-2')
                        fig_table = go.Figure(data=[go.Table(
                            header=dict(values=['Rank', 'Question', 'Count', 'Category'], fill_color='paleturquoise', align='left'),
                            cells=dict(values=[
                                list(range(1, len(questions_table_data.get('questions', [])) + 1)),
                                questions_table_data.get('questions', []),
                                questions_table_data.get('counts', []),
                                questions_table_data.get('categories', []) or ['N/A'] * len(questions_table_data.get('questions', []))
                            ], fill_color='lavender', align='left'))
                        ])
                        fig_table.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), height=550)
                        ui.plotly(fig_table).classes('w-full').props('responsive=true').style('height: auto; min-height: 550px; max-width: 100%; overflow: visible;')
                else: 
                    with ui.card().classes('w-full mb-4 p-4'): ui.label('Top User Questions').classes('text-h6 mb-2'); ui.label('Data not available.').classes('text-gray-500 italic')
            except Exception as e: print(f"Error generating questions table: {e}"); ui.label(f'Error: {str(e)}').classes('text-negative')
            
            print("All visualizations complete")
            # Use client.run_javascript to trigger notification
            if self.client and self.client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Analysis visualization complete!', type: 'positive', timeout: 3000 }})"
                self.client.run_javascript(js_command)
            with ui.row().classes('justify-end mt-4'):
                # Need to wrap the call in a lambda or partial to pass arguments correctly
                ui.button('Run New Analysis', icon='refresh', 
                          on_click=lambda: self.generate_macro_analysis(max_summaries_input, tabs_ref)).props('color=primary')

    def build_ui(self):
        """Builds the NiceGUI elements for the admin page."""
        from nicegui import ui
        # Store client reference using ui.context.client
        self.client = ui.context.client # Correctly capture the client context
        
        create_navigation_menu_2() # Assumes global definition

        with ui.column().classes('w-full items-center p-4'):
            ui.label('FastInnovation Admin').classes('text-h4 q-mb-md')

            with ui.tabs().classes('w-full').props('no-swipe-select keep-alive active-class="bg-primary text-white"') as tabs:
                ui.tab('Users Table', icon='people')
                ui.tab('Macro Analysis', icon='analytics')
            tabs.set_value('Users Table')

            with ui.tab_panels(tabs, value='Users Table').classes('w-full').props('animated keep-alive'):
                # --- Users Table Panel --- 
                with ui.tab_panel('Users Table'):
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        ui.label('Click row for details').classes('text-sm text-gray-600')
                        # Refresh button triggers initial_load again
                        ui.button('Refresh', icon='refresh', on_click=lambda: asyncio.create_task(self.initial_load())).props('flat color=primary')

                    users_columns = [
                         {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left', 'sortable': True}, # Enable sorting if API supports it
                         {'name': 'session_id', 'field': 'session_id', 'label': 'Session ID', 'align': 'left', 'sortable': False},
                         {'name': 'logged', 'field': 'logged', 'label': 'Logged', 'align': 'center', 'sortable': False},
                         {'name': 'message_count', 'field': 'message_count', 'label': 'Messages', 'align': 'center', 'sortable': True}, # Enable sorting
                         {'name': 'start_time', 'field': 'start_time', 'label': 'Started', 'align': 'center', 'sortable': False}, # Or True if API supports
                         {'name': 'last_activity', 'field': 'last_activity', 'label': 'Last Activity', 'align': 'center', 'sortable': True} # Enable sorting
                    ]

                    # Create the table, binding pagination to the class state
                    self.users_table = ui.table(
                        columns=users_columns, rows=[], row_key='user_id',
                        pagination=self.pagination_state, # Bind to the reactive dict
                        on_select=lambda e: asyncio.create_task(self.handle_users_row_click(e)),
                    ).classes('w-full')
                    # REMOVE server-side pagination props and event handler
                    # The table will handle pagination and sorting client-side with all data
                    self.users_table.props('flat bordered separator=cell loading=false') 
                    # REMOVE self.users_table.on('request', ...) call
                    
                    # Schedule initial load
                    ui.timer(0.1, lambda: asyncio.create_task(self.initial_load()), once=True)

                # --- Macro Analysis Panel --- 
                with ui.tab_panel('Macro Analysis'):
                    with ui.column().classes('w-full p-4'):
                        ui.label('Conversation Macro Analysis').classes('text-h5 q-mb-md')
                        with ui.row().classes('w-full mt-4 items-center'):
                            ui.label('Analysis Options:').classes('mr-4')
                            with ui.card().classes('w-full p-4'):
                                with ui.row().classes('items-center justify-between w-full'): # Ensure row takes full width
                                    max_summaries_input_el = ui.number(value=100, min=10, max=1000, label='Max Conversations').classes('w-40')
                                    max_summaries_input_el.props('outlined')
                                    
                                    # Lambda for analyze button
                                    analyze_btn = ui.button('Generate Analysis', icon='analytics', 
                                                            on_click=lambda: asyncio.create_task(self.generate_macro_analysis(max_summaries_input_el, tabs)))
                                analyze_btn.props('color=primary size=lg')
                    
                        # Define the analysis container and store reference in class
                        self.analysis_container = ui.column().classes('w-full mt-4 border rounded p-4 min-h-[500px]')
                        with self.analysis_container:
                            ui.label('Select options and click "Generate Analysis"').classes('text-gray-500 italic text-center w-full py-8')
                        
                    with ui.expansion('How to use Macro Analysis', icon='help').classes('w-full mt-4'):
                        ui.markdown("""
                        ### Understanding Macro Analysis
                             ... (Existing help text)
                             This tool provides aggregated insights across multiple conversations using data fetched directly from the analysis API.
                             **Key Visualizations:** ... 
                             **How to use:** ...
                             *Note: Data is fetched directly from pre-computed analysis endpoints.*
                             """)

        # Add CSS/JS
        ui.add_head_html(r'''
        <style> .q-table tbody tr { cursor: pointer; } ... </style>
        <script> /* ... existing script ... */ </script>
        ''') # Keep existing styles/scripts

@ui.page('/admin')
async def page_admin():
    # Instantiate the manager and build the UI
    manager = AdminPageManager()
    manager.build_ui() # This creates the UI and schedules the initial load

# --- No ui.run() ---