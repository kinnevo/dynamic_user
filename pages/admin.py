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

# API Configuration
API_BASE_URL = "https://fireportes-production.up.railway.app/api/v1"
API_KEY = os.getenv("FI_ANALYTICS_API_KEY")

if not API_KEY:
    print("ERROR: FI_ANALYTICS_API_KEY not found in environment variables.")
    # Handle missing API key appropriately, maybe raise an error or show a message
    # For now, we'll allow it to proceed but API calls will likely fail.
    
API_HEADERS = {"X-API-Key": API_KEY}

# --- Helper Function for API Calls ---
async def api_request(method: str, endpoint: str, params: dict = None, json_data: dict = None) -> dict | None:
    """Makes an asynchronous API request."""
    # Explicitly check for API_KEY before making the call
    if not API_KEY:
         print("Aborting API call: FI_ANALYTICS_API_KEY is missing or empty in environment.")
         ui.notify("API Key is missing. Cannot fetch data.", type='negative')
         return None
         
    # Recreate headers here to ensure the key is included if it was loaded
    headers = {"X-API-Key": API_KEY}
    
    async with httpx.AsyncClient(base_url=API_BASE_URL, headers=headers, timeout=30.0) as client:
        try:
            print(f"--> Making API request: {method} {client.build_request(method, endpoint, params=params, json=json_data).url}") # Log the request URL
            response = await client.request(method, endpoint, params=params, json=json_data)
            print(f"<-- Received API response: {response.status_code}") # Log the status code
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()
        except httpx.RequestError as exc:
            # Log the actual exception details
            print(f"A network error occurred while requesting {exc.request.url!r}: {exc}") 
            ui.notify(f"Network error contacting API: {exc}", type='negative')
            return None
        except httpx.HTTPStatusError as exc:
            # Log the response body for HTTP errors too
            print(f"HTTP error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
            ui.notify(f"API Error ({exc.response.status_code}): {exc.response.text[:100]}...", type='negative') # Truncate long error messages
            return None
        except Exception as e:
            import traceback
            print(f"An unexpected error occurred during API call: {e}")
            print(traceback.format_exc()) # Print full traceback for unexpected errors
            ui.notify(f"Unexpected API error: {e}", type='negative')
            return None

# --- Dialog Handler Function ---
async def show_user_details(user_data):
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
    messages_data = await api_request('GET', f'/sessions/{session_id}/recent-messages', params={'limit': 20})
    
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

# --- Main Page Definition ---
@ui.page('/admin')
async def page_admin():
    # Create navigation using your function
    create_navigation_menu_2()

    # --- Main Content Area ---
    with ui.column().classes('w-full items-center p-4'):
        # Use the title from your snippet
        ui.label('FastInnovation Admin').classes('text-h4 q-mb-md')

        # Create tabs for different admin panels with persistent visibility
        with ui.tabs().classes('w-full').props('no-swipe-select keep-alive active-class="bg-primary text-white"') as tabs:
            ui.tab('Users Table', icon='people')
            # ui.tab('Conversation Summaries', icon='summarize') # Removed tab
            ui.tab('Macro Analysis', icon='analytics')
        
        # Create a local variable to track the tab
        current_tab = 'Users Table'
        
        # Store the current tab value in a shared state for persistence
        def on_tab_change(new_tab):
            print(f"Tab changed to: {new_tab}")
            nonlocal current_tab
            current_tab = new_tab
            
        # Set initial tab to first tab
        tabs.set_value('Users Table')
        
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
                async def handle_users_row_click(e):
                    # The event format is: [event, rowData, rowIndex]
                    if isinstance(e.args, list) and len(e.args) >= 2:
                        # The row data is the second element (index 1) in the args list
                        row_data = e.args[1]
                        await show_user_details(row_data)
                    else:
                        ui.notify("Could not retrieve row data", type="negative")
                        
                users_table.on('row-click', handle_users_row_click)
                
                # --- Data Update Function (Using API) ---
                async def update_users_table():
                    """Fetches user data from the API and updates the table rows."""
                    # Fetch user data from API
                    users_data = await api_request('GET', '/users/', params={'limit': 500}) # Increase limit? Add pagination later?

                    if users_data is None:
                        ui.notify('Error loading users from API', type='negative', position='top-right')
                        users_table.rows = [] # Clear table on error
                        return
                    
                    if not isinstance(users_data, list):
                        ui.notify('Unexpected data format for users from API', type='negative', position='top-right')
                        users_table.rows = [] # Clear table on error
                        return

                    table_rows = []
                    
                    # Prepare tasks for fetching message counts concurrently
                    message_count_tasks = {}
                    for user in users_data:
                        session_id = user.get('session_id')
                        if session_id:
                             # Store the task, but don't await yet
                             message_count_tasks[session_id] = asyncio.create_task(
                                 api_request('GET', f'/sessions/{session_id}/message-count')
                             )

                    # Wait for all message count tasks to complete
                    await asyncio.gather(*message_count_tasks.values(), return_exceptions=True)

                    # Now process users and their fetched message counts
                    for user in users_data:
                        user_id = user.get('user_id')
                        session_id = user.get('session_id')
                        logged = user.get('logged', False)
                        last_active_str = user.get('last_active')
                        
                        message_count = 0 # Default
                        start_time_str = 'Never' # Default
                        last_activity_str = 'Never' # Default

                        # Get message count result for this session
                        if session_id in message_count_tasks:
                            try:
                                count_result = message_count_tasks[session_id].result() # Get result from completed task
                                if isinstance(count_result, int):
                                    message_count = count_result
                                else:
                                    print(f"WARN: Unexpected message count format for session {session_id}: {count_result}")
                            except Exception as e:
                                print(f"ERROR fetching message count for session {session_id}: {e}")
                                # Keep default message_count = 0

                        # Fetch message timestamps if message_count > 0 (optional, could be slow)
                        # For now, we'll rely on user's last_active. 
                        # If needed, fetch messages to get min/max timestamps.
                        # Example (would add more API calls):
                        # if message_count > 0:
                        #     messages = await api_request('GET', f'/sessions/{session_id}/messages')
                        #     if messages and isinstance(messages, list):
                        #         timestamps = [m['timestamp'] for m in messages if 'timestamp' in m]
                        #         if timestamps:
                        #             start_time_str = min(timestamps) # Format appropriately
                        #             last_activity_str = max(timestamps) # Format appropriately

                        # Format last_active timestamp safely
                        if last_active_str:
                             try:
                                last_active_dt = datetime.fromisoformat(last_active_str)
                                last_activity_str = last_active_dt.strftime("%Y-%m-%d %H:%M:%S")
                             except (ValueError, TypeError):
                                last_activity_str = last_active_str # Keep raw string if format is wrong

                        table_rows.append({
                            'user_id': user_id,
                            'session_id': session_id,
                            'logged': 'Yes' if logged else 'No',
                            'message_count': message_count,
                            'start_time': start_time_str, # Using default for now
                            'last_activity': last_activity_str
                        })

                    # Update the table component's rows
                    users_table.rows = table_rows

                    # Show subtle notification
                    if len(table_rows) > 0:
                        ui.notify(f"Loaded {len(table_rows)} users via API", type='positive', position='bottom-right', timeout=1500)
                    else:
                        ui.notify("No users found via API", type='info', position='bottom-right', timeout=1500)

                # Initial Data Load for Users Table
                await update_users_table()
                
            # Macro Analysis Tab Panel
            with ui.tab_panel('Macro Analysis'):
                with ui.column().classes('w-full p-4'):
                    ui.label('Conversation Macro Analysis').classes('text-h5 q-mb-md')
                    
                    # Analysis options
                    with ui.row().classes('w-full mt-4 items-center'):
                        ui.label('Analysis Options:').classes('mr-4')
                        
                        with ui.card().classes('w-full p-4'):
                            with ui.row().classes('items-center justify-between'):
                                max_summaries_macro = ui.number(value=100, min=10, max=1000, label='Max Conversations').classes('w-40') # Renamed label
                                max_summaries_macro.props('outlined')
                                
                                # Define generate_analysis function in advance 
                                async def generate_macro_analysis():
                                    # Force the tab to stay on Macro Analysis right at the beginning
                                    tabs.set_value("Macro Analysis")
                                    
                                    # Get selected values
                                    limit = int(max_summaries_macro.value)
                                    top_n_questions = 15 # Keep this configurable if needed later

                                    # Clear previous results
                                    analysis_container.clear()

                                    # Show loading state
                                    with analysis_container:
                                        ui.label('Fetching and visualizing analysis data...').classes('text-h6 mb-2')
                                        loading_spinner = ui.spinner('dots', size='lg').classes('text-primary')
                                    
                                    # Force tab again after showing loading state
                                    tabs.set_value("Macro Analysis")

                                    # --- Fetch data from API endpoints --- 
                                    print(f"\n=== FETCHING VISUALIZATION DATA (limit={limit}) ===")
                                    
                                    # Use asyncio.gather to fetch all visualization data concurrently
                                    results = await asyncio.gather(
                                        api_request('GET', '/visualizations/topic-heatmap', params={'limit': limit}),
                                        api_request('GET', '/visualizations/satisfaction-chart', params={'limit': limit}),
                                        api_request('GET', '/visualizations/conversation-types-chart', params={'limit': limit}),
                                        api_request('GET', '/visualizations/questions-table', params={'limit': limit, 'top_n': top_n_questions}),
                                        return_exceptions=True # Return exceptions instead of raising them
                                    )
                                    
                                    # Unpack results, checking for errors
                                    topic_heatmap_data, satisfaction_chart_data, types_chart_data, questions_table_data = results
                                    
                                    # --- Check for errors in API calls ---
                                    errors = []
                                    if isinstance(topic_heatmap_data, Exception) or topic_heatmap_data is None:
                                        errors.append(f"Topic Heatmap: {topic_heatmap_data or 'No data returned'}")
                                        topic_heatmap_data = None # Set to None if error
                                    if isinstance(satisfaction_chart_data, Exception) or satisfaction_chart_data is None:
                                        errors.append(f"Satisfaction Chart: {satisfaction_chart_data or 'No data returned'}")
                                        satisfaction_chart_data = None
                                    if isinstance(types_chart_data, Exception) or types_chart_data is None:
                                        errors.append(f"Conversation Types Chart: {types_chart_data or 'No data returned'}")
                                        types_chart_data = None
                                    if isinstance(questions_table_data, Exception) or questions_table_data is None:
                                        errors.append(f"Questions Table: {questions_table_data or 'No data returned'}")
                                        questions_table_data = None
                                        
                                    # Clear loading state and display results/errors
                                    analysis_container.clear()
                                    tabs.set_value("Macro Analysis") # Ensure tab stays active

                                    with analysis_container:
                                        ui.label('Macro Analysis Results').classes('text-h5 mb-4')
                                        
                                        # Display errors if any
                                        if errors:
                                            with ui.card().classes('w-full mb-4 p-4 bg-red-100'):
                                                ui.label('Errors Fetching Data:').classes('text-h6 text-negative mb-2')
                                                for error in errors:
                                                    ui.label(f"- {error}").classes('text-negative')
                                            ui.notify("Some analysis data failed to load. Check errors.", type="warning")

                                        # Display summary stats (using limit)
                                        with ui.card().classes('w-full mb-4 p-4'):
                                            ui.label('Analysis Parameters').classes('text-h6 mb-2')
                                            with ui.row().classes('w-full justify-between'):
                                                ui.label(f'Max Conversations Analyzed: {limit}').classes('text-subtitle1')
                                                # ui.label(f'Date Range: N/A').classes('text-subtitle1') # Removed date range
                                                # ui.label(f'Analysis Model: API Default').classes('text-subtitle1') # Removed model
                                        
                                        tabs.set_value("Macro Analysis")

                                        # --- Generate Visualizations from API Data ---
                                        print("\n=== GENERATING VISUALIZATIONS FROM API DATA ===")

                                        # Display topic heatmap
                                        try:
                                            if topic_heatmap_data:
                                                print("Generating topic heatmap...")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                                                    
                                                    # Create heatmap using API data structure
                                                    fig = go.Figure(data=go.Heatmap(
                                                        z=topic_heatmap_data.get('counts', []), # Use counts for intensity
                                                        x=topic_heatmap_data.get('sentiments', []),
                                                        y=topic_heatmap_data.get('topics', []),
                                                        colorscale='Viridis', 
                                                        # Custom text: Importance Value: X, Count: Y
                                                        text = [
                                                            [f"Importance: {imp}<br>Count: {cnt}" 
                                                             for imp, cnt in zip(imp_row, cnt_row)] 
                                                            for imp_row, cnt_row in zip(topic_heatmap_data.get('importance_values', []), topic_heatmap_data.get('counts', []))
                                                        ],
                                                        hoverinfo='text'
                                                    ))
                                                    
                                                    fig.update_layout(
                                                        title='Topic Sentiment Heatmap (Counts)',
                                                        xaxis_title="Sentiment",
                                                        yaxis_title="Topic",
                                                        autosize=True,
                                                        margin=dict(l=100, r=50, t=80, b=50),
                                                        height=500 # Increased height
                                                    )
                                                    
                                                    plot_container = ui.plotly(fig).classes('w-full')
                                                    plot_container.props('responsive=true')
                                                    plot_container.style('height: 500px; max-width: 100%; overflow: visible;')
                                            else:
                                                print("Skipping topic heatmap due to missing data.")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                                                    ui.label('Data not available.').classes('text-gray-500 italic')
                                            tabs.set_value("Macro Analysis")
                                        except Exception as e:
                                            print(f"Error generating topic heatmap: {e}")
                                            with ui.card().classes('w-full mb-4 p-4'):
                                                ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                                                ui.label(f'Error generating visualization: {str(e)}').classes('text-negative')
                                            tabs.set_value("Macro Analysis")

                                        # Display satisfaction and conversation types charts side-by-side
                                        with ui.row().classes('w-full flex flex-col md:flex-row gap-4 my-4'):
                                            # Satisfaction Chart
                                            try:
                                                if satisfaction_chart_data:
                                                    print("Generating satisfaction chart...")
                                                    with ui.card().classes('w-full md:w-1/2 p-4'):
                                                        ui.label('User Satisfaction').classes('text-h6 mb-2')
                                                        
                                                        # Create bar chart using API data
                                                        fig_satisfaction = go.Figure(data=[go.Bar(
                                                            x=satisfaction_chart_data.get('satisfaction_levels', []),
                                                            y=satisfaction_chart_data.get('counts', []),
                                                            marker_color='#1f77b4' # Example color
                                                        )])
                                                        fig_satisfaction.update_layout(
                                                            title='User Satisfaction Distribution',
                                                            xaxis_title="Satisfaction Level (1-5)",
                                                            yaxis_title="Number of Conversations",
                                                            autosize=True,
                                                            margin=dict(l=30, r=30, t=50, b=50),
                                                            height=350
                                                        )
                                                        
                                                        plot_container = ui.plotly(fig_satisfaction).classes('w-full')
                                                        plot_container.props('responsive=true')
                                                        plot_container.style('height: 350px; max-width: 100%; overflow: visible;')
                                                else:
                                                    print("Skipping satisfaction chart due to missing data.")
                                                    with ui.card().classes('w-full md:w-1/2 p-4'):
                                                        ui.label('User Satisfaction').classes('text-h6 mb-2')
                                                        ui.label('Data not available.').classes('text-gray-500 italic')
                                            except Exception as e:
                                                print(f"Error generating satisfaction chart: {e}")
                                                with ui.card().classes('w-full md:w-1/2 p-4'):
                                                    ui.label('User Satisfaction').classes('text-h6 mb-2')
                                                    ui.label(f'Error generating chart: {str(e)}').classes('text-negative')
                                                
                                            # Conversation Types Chart
                                            try:
                                                if types_chart_data:
                                                    print("Generating conversation types chart...")
                                                    with ui.card().classes('w-full md:w-1/2 p-4'):
                                                        ui.label('Conversation Types').classes('text-h6 mb-2')
                                                        
                                                        # Create pie chart using API data
                                                        fig_types = go.Figure(data=[go.Pie(
                                                            labels=types_chart_data.get('types', []),
                                                            values=types_chart_data.get('counts', []),
                                                            hole=.3 # Optional: make it a donut chart
                                                        )])
                                                        fig_types.update_layout(
                                                            title='Distribution of Conversation Types',
                                                            autosize=True,
                                                            margin=dict(l=30, r=30, t=50, b=50),
                                                            height=350,
                                                            legend_title_text='Types'
                                                        )
                                                        
                                                        plot_container = ui.plotly(fig_types).classes('w-full')
                                                        plot_container.props('responsive=true')
                                                        plot_container.style('height: 350px; max-width: 100%; overflow: visible;')
                                                else:
                                                    print("Skipping conversation types chart due to missing data.")
                                                    with ui.card().classes('w-full md:w-1/2 p-4'):
                                                        ui.label('Conversation Types').classes('text-h6 mb-2')
                                                        ui.label('Data not available.').classes('text-gray-500 italic')
                                            except Exception as e:
                                                print(f"Error generating types chart: {e}")
                                                with ui.card().classes('w-full md:w-1/2 p-4'):
                                                    ui.label('Conversation Types').classes('text-h6 mb-2')
                                                    ui.label(f'Error generating chart: {str(e)}').classes('text-negative')
                                            
                                        tabs.set_value("Macro Analysis")

                                        # Display top questions table
                                        try:
                                            if questions_table_data:
                                                print("Generating questions table...")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Top User Questions').classes('text-h6 mb-2')
                                                    
                                                    # Create table using API data
                                                    fig_table = go.Figure(data=[go.Table(
                                                        header=dict(values=['Rank', 'Question', 'Count', 'Category'],
                                                                    fill_color='paleturquoise',
                                                                    align='left'),
                                                        cells=dict(values=[
                                                            list(range(1, len(questions_table_data.get('questions', [])) + 1)), # Rank
                                                            questions_table_data.get('questions', []),
                                                            questions_table_data.get('counts', []),
                                                            questions_table_data.get('categories', []) or ['N/A'] * len(questions_table_data.get('questions', [])) # Handle null categories
                                                        ],
                                                                   fill_color='lavender',
                                                                   align='left'))
                                                    ])
                                                    
                                                    fig_table.update_layout(
                                                        autosize=True,
                                                        margin=dict(l=10, r=10, t=50, b=10),
                                                        height=550
                                                    )
                                                    
                                                    plot_container = ui.plotly(fig_table).classes('w-full')
                                                    plot_container.props('responsive=true')
                                                    plot_container.style('height: auto; min-height: 550px; max-width: 100%; overflow: visible;')
                                            else:
                                                print("Skipping questions table due to missing data.")
                                                with ui.card().classes('w-full mb-4 p-4'):
                                                    ui.label('Top User Questions').classes('text-h6 mb-2')
                                                    ui.label('Data not available.').classes('text-gray-500 italic')
                                            tabs.set_value("Macro Analysis")
                                        except Exception as e:
                                            print(f"Error generating questions table: {e}")
                                            with ui.card().classes('w-full mb-4 p-4'):
                                                ui.label('Top User Questions').classes('text-h6 mb-2')
                                                ui.label(f'Error generating questions table: {str(e)}').classes('text-negative')
                                            tabs.set_value("Macro Analysis")

                                        # Final tab force at the end
                                        tabs.set_value("Macro Analysis")
                                        
                                        print("All visualizations complete")
                                        ui.notify("Analysis visualization complete!", type="positive", timeout=3000)
                                        
                                        # Add buttons to restart
                                        with ui.row().classes('justify-end mt-4'):
                                            ui.button('Run New Analysis', icon='refresh', on_click=generate_macro_analysis).props('color=primary')
                                
                                # Generate analysis button (initial trigger)
                                analyze_btn = ui.button('Generate Analysis', icon='analytics', on_click=generate_macro_analysis)
                                analyze_btn.props('color=primary size=lg')
                    
                    # Results container for analysis with minimum height to prevent collapse
                    analysis_container = ui.column().classes('w-full mt-4 border rounded p-4 min-h-[500px]')
                    
                    # Placeholder text for empty results
                    with analysis_container:
                        ui.label('Select analysis options and click "Generate Analysis"').classes('text-gray-500 italic text-center w-full py-8')
                    
                    # Add help information about the Macro Analysis feature
                    with ui.expansion('How to use Macro Analysis', icon='help').classes('w-full mt-4'):
                        ui.markdown("""
                        ### Understanding Macro Analysis
                        
                        This tool provides aggregated insights across multiple conversations using data fetched directly from the analysis API.
                        
                        **Key Visualizations:**
                        - **Topic Sentiment Heatmap**: Visualizes common topics and associated sentiments based on counts and importance.
                        - **User Satisfaction Chart**: Measures overall satisfaction levels across recent conversations.
                        - **Conversation Types Chart**: Categorizes recent conversations by their primary purpose.
                        - **Top User Questions Table**: Identifies the most frequent questions asked by users.
                        
                        **How to use:**
                        1. Set the maximum number of recent conversations to include in the analysis (default is 100).
                        2. Click "Generate Analysis".
                        3. Explore the visualizations and tables to understand conversation patterns.
                        
                        *Note: Data is fetched directly from pre-computed analysis endpoints. Date/user filtering is not currently applied here.*
                        """)
        
        # Add CSS classes to make rows appear clickable and JS to ensure tabs persist
        ui.add_head_html(r'''
        <style>
            .q-table tbody tr {
                cursor: pointer;
                transition: background-color 0.2s;
            }
            .q-table tbody tr:hover {
                background-color: rgba(59, 130, 246, 0.1);
            }
            /* Make active tab more visible */
            .q-tab--active {
                font-weight: bold;
                border-bottom: 2px solid currentColor;
            }
            /* Fix for Plotly charts to ensure they don't overflow */
            .js-plotly-plot, .plotly, .plot-container {
                max-width: 100% !important;
                height: auto !important;
                overflow: visible !important;
            }
            .js-plotly-plot .plot-container .main-svg {
                max-width: 100% !important;
                height: auto !important;
            }
            /* Ensure cards have proper spacing and sizing */
            .q-card {
                overflow: visible !important;
                margin-bottom: 1rem;
            }
            /* Allow grid layout for better visualization spacing */
            .grid-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 1rem;
            }
            /* Responsive cards and layouts */
            @media (max-width: 768px) {
                .md\:w-1\/2 {
                    width: 100% !important;
                    margin-bottom: 1rem;
                }
                .md\:flex-row {
                    flex-direction: column !important;
                }
            }
        </style>
        <script>
            // Helper function to ensure tab visibility
            document.addEventListener('DOMContentLoaded', () => {
                // Use MutationObserver to watch for changes to the DOM
                const observer = new MutationObserver((mutations) => {
                    // Find the active tab panel
                    const activeTab = document.querySelector('.q-tab--active');
                    if (activeTab && activeTab.textContent.includes('Macro Analysis')) {
                        // Get corresponding tab panel
                        const tabPanels = document.querySelectorAll('.q-tab-panel');
                        tabPanels.forEach(panel => {
                            if (panel.innerHTML.includes('Macro Analysis')) {
                                // Force it to be visible
                                panel.style.display = 'block';
                            }
                        });
                    }
                });
                
                // Start observing the document with the configured parameters
                observer.observe(document.body, { 
                    childList: true, 
                    subtree: true 
                });
            });
        </script>
        ''')

# --- No ui.run() here, as it's part of an existing app ---