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
from utils.layouts import create_navigation_menu_2, create_date_range_selector, create_user_selector # Re-added imports

# Load environment variables
load_dotenv()

# # API Configuration
API_BASE_URL = "https://fireportes-production.up.railway.app/api/v1"
# API_BASE_URL = "http://localhost:8000/api/v1/"  # for local development
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
    """Creates and shows a dialog with user details and conversation history in a chat UI."""
    # Extract user data
    if not isinstance(user_data, dict) or not client or not client.has_socket_connection:
        return
    
    session_id = user_data.get('session_id', 'N/A')
    user_id = user_data.get('user_id', 'N/A')
    logged = user_data.get('logged', 'N/A')
    
    # Create a placeholder element to avoid the UI context issue
    placeholder_id = f"user_modal_{user_id}"
    
    # Create modal using JavaScript with improved width and layout
    js_code = f"""
    // Create modal container if it doesn't exist
    let modalContainer = document.getElementById("{placeholder_id}");
    if (!modalContainer) {{
        modalContainer = document.createElement('div');
        modalContainer.id = "{placeholder_id}";
        modalContainer.classList.add('fixed', 'inset-0', 'bg-black', 'bg-opacity-30', 
            'flex', 'items-center', 'justify-center', 'z-50');
        modalContainer.style.display = 'flex';
        
        // Create modal content - increased width
        let modalContent = document.createElement('div');
        modalContent.classList.add('bg-white', 'rounded-lg', 'shadow-xl', 'w-3/5', 
            'max-w-3xl', 'max-h-[90vh]', 'overflow-y-auto', 'flex', 'flex-col');
        
        // Header
        let header = document.createElement('div');
        header.classList.add('bg-primary', 'text-white', 'p-4', 'flex', 'justify-between', 'items-center', 'sticky', 'top-0', 'z-10', 'w-full');
        let title = document.createElement('h3');
        title.textContent = "Details for User: " + {user_id};
        title.classList.add('text-lg', 'font-bold', 'flex-grow');
        let closeBtn = document.createElement('button');
        closeBtn.textContent = "×";
        closeBtn.classList.add('text-xl', 'font-bold', 'ml-4');
        closeBtn.onclick = function() {{
            document.body.removeChild(modalContainer);
        }};
        header.appendChild(title);
        header.appendChild(closeBtn);
        
        // User details section
        let details = document.createElement('div');
        details.classList.add('p-4', 'w-full');
        details.innerHTML = `
            <p class="mb-2"><strong>User ID:</strong> {user_id}</p>
            <p class="mb-2"><strong>Session ID:</strong> {session_id}</p>
            <p class="mb-2"><strong>Logged Status:</strong> {logged}</p>
        `;
        
        // Messages section
        let messagesHeader = document.createElement('h4');
        messagesHeader.textContent = 'Recent Conversation';
        messagesHeader.classList.add('font-bold', 'p-4', 'pt-0', 'text-lg');
        
        let messagesContainer = document.createElement('div');
        messagesContainer.id = "messages_{user_id}";
        messagesContainer.classList.add('w-auto', 'mx-4', 'h-[40vh]', 'overflow-y-auto', 'p-4', 
            'gap-2', 'border', 'rounded', 'bg-white', 'mb-4', 'overflow-x-hidden');
        
        // Enhanced loading spinner
        messagesContainer.innerHTML = `
            <div class="flex flex-col justify-center items-center h-full">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-3"></div>
                <p class="text-gray-600 font-medium">Loading conversation history...</p>
                <p class="text-gray-500 text-sm mt-1">This may take a moment</p>
            </div>
        `;
        
        // Footer
        let footer = document.createElement('div');
        footer.classList.add('p-4', 'flex', 'justify-end', 'sticky', 'bottom-0', 'bg-white', 'border-t', 'w-full');
        let closeButton = document.createElement('button');
        closeButton.textContent = "Close";
        closeButton.classList.add('px-4', 'py-2', 'bg-primary', 'text-white', 'rounded');
        closeButton.onclick = function() {{
            document.body.removeChild(modalContainer);
        }};
        footer.appendChild(closeButton);
        
        // Assemble modal
        modalContent.appendChild(header);
        modalContent.appendChild(details);
        modalContent.appendChild(messagesHeader);
        modalContent.appendChild(messagesContainer);
        modalContent.appendChild(footer);
        
        modalContainer.appendChild(modalContent);
        document.body.appendChild(modalContainer);
    }}
    """
    
    await client.run_javascript(js_code)
    
    # Add a loading state indicator before updating messages
    update_js = f"""
    let messagesContainer = document.getElementById("messages_{user_id}");
    if (messagesContainer) {{
        // Show loading spinner first
        messagesContainer.innerHTML = `
            <div class="flex flex-col justify-center items-center h-full">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-3"></div>
                <p class="text-gray-600 font-medium">Loading conversation history...</p>
                <p class="text-gray-500 text-sm mt-1">This may take a moment</p>
            </div>
        `;
    }}
    """
    await client.run_javascript(update_js)
    
    # Fetch messages asynchronously
    messages_data = await api_request('GET', f'/sessions/{session_id}/recent-messages', client=client, params={'limit': 20})
    
    # Format and display messages
    messages_html = ""
    if messages_data and isinstance(messages_data, list):
        if not messages_data:
            messages_html = '<p class="text-gray-500 italic text-center w-full">No messages found for this session</p>'
        else:
            messages_data.sort(key=lambda x: x.get('timestamp', ''))
            for msg in messages_data:
                role = msg.get('role')
                content = msg.get('content', '').replace('`', '\\`').replace("'", "\\'").replace('\n', '<br>')
                timestamp_str = msg.get('timestamp')
                
                # Parse timestamp safely
                try:
                    timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else None
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "Unknown time"
                except ValueError:
                    time_str = timestamp_str if timestamp_str else "Invalid time format"
                
                # Create HTML for message bubble based on role
                bubble_class = "self-end bg-blue-500 text-white" if role == 'user' else "self-start bg-gray-200"
                justify_class = "justify-end" if role == 'user' else "justify-start"
                
                if role not in ['user', 'assistant', 'ai']:
                    bubble_class = "self-center bg-yellow-100"
                    justify_class = "justify-center"
                    content = f"Role: {role}<br>{content}"
                
                messages_html += f"""
                <div class="flex {justify_class} mb-4 w-full">
                    <div class="p-3 rounded-lg max-w-[80%] break-words {bubble_class}">
                        <div class="text-xs opacity-70 mb-1">{time_str}</div>
                        <div class="whitespace-pre-wrap">{content}</div>
                    </div>
                </div>
                """
    elif messages_data is None:
        messages_html = '<p class="text-red-500 text-center w-full">Error fetching messages. Check API connection.</p>'
    else:
        messages_html = '<p class="text-orange-500 text-center w-full">Unexpected data format received for messages.</p>'
    
    # Update messages container with fetched data
    update_js = f"""
    let messagesContainer = document.getElementById("messages_{user_id}");
    if (messagesContainer) {{
        messagesContainer.innerHTML = `{messages_html.replace('`', '\\`').replace("'", "\\'")}`;
    }}
    """
    
    await client.run_javascript(update_js)

async def show_summary_details(summary_data, client=None):
    """Shows a half-screen modal with all summary metadata and the full summary."""
    if not isinstance(summary_data, dict) or not client or not client.has_socket_connection:
        return
    
    # Extract the summary ID to fetch the complete data if needed
    summary_id = summary_data.get('summary_id', 'unknown')
    
    # Check if we need to fetch the full summary - if the summary key contains "..." it's likely truncated
    if '...' in summary_data.get('summary', '') and summary_id:
        # Fetch the complete summary data from the API
        full_summary_data = await api_request('GET', f'/summaries/{summary_id}', client=client)
        if full_summary_data and isinstance(full_summary_data, dict):
            # Replace our data with the complete version
            summary_data = full_summary_data
    
    # Now extract all needed fields
    user_id = summary_data.get('user_id', 'N/A')
    session_id = summary_data.get('session_id', 'N/A')
    created_at = summary_data.get('created_at', 'N/A')
    logged = 'Yes' if summary_data.get('logged') else 'No'
    
    # Make sure we're using the full summary text without truncation
    summary_text = summary_data.get('summary', '').replace('`', '\\`').replace("'", "\\'").replace('\n', '<br>')
    
    placeholder_id = f"summary_modal_{summary_id}"
    
    # Create modal using JavaScript - use a slightly larger and better-styled modal
    js_code = f"""
    // Create modal container if it doesn't exist
    let modalContainer = document.getElementById("{placeholder_id}");
    if (!modalContainer) {{
        modalContainer = document.createElement('div');
        modalContainer.id = "{placeholder_id}";
        modalContainer.classList.add('fixed', 'inset-0', 'bg-black', 'bg-opacity-30', 
            'flex', 'items-center', 'justify-center', 'z-50');
        modalContainer.style.display = 'flex';
        
        // Create modal content - increased size
        let modalContent = document.createElement('div');
        modalContent.classList.add('bg-white', 'rounded-lg', 'shadow-xl', 'w-3/5', 
            'max-w-3xl', 'max-h-[90vh]', 'overflow-y-auto', 'flex', 'flex-col');
        
        // Header
        let header = document.createElement('div');
        header.classList.add('bg-primary', 'text-white', 'p-4', 'flex', 'justify-between', 'items-center', 'sticky', 'top-0', 'z-10');
        let title = document.createElement('h3');
        title.textContent = "Summary Details";
        title.classList.add('text-lg', 'font-bold');
        let closeBtn = document.createElement('button');
        closeBtn.textContent = "×";
        closeBtn.classList.add('text-xl', 'font-bold');
        closeBtn.onclick = function() {{
            document.body.removeChild(modalContainer);
        }};
        header.appendChild(title);
        header.appendChild(closeBtn);
        
        // Summary details section
        let details = document.createElement('div');
        details.classList.add('p-4');
        details.innerHTML = `
            <p class="mb-2"><strong>Summary ID:</strong> {summary_id}</p>
            <p class="mb-2"><strong>User ID:</strong> {user_id}</p>
            <p class="mb-2"><strong>Session ID:</strong> {session_id}</p>
            <p class="mb-2"><strong>Created At:</strong> {created_at}</p>
            <p class="mb-2"><strong>Logged:</strong> {logged}</p>
            <h4 class="font-bold mt-6 mb-3 text-lg">Summary:</h4>
            <div class="bg-gray-100 p-6 rounded-lg w-full min-h-[350px] overflow-y-auto whitespace-pre-wrap text-base leading-relaxed">
                {summary_text}
            </div>
        `;
        
        // Footer
        let footer = document.createElement('div');
        footer.classList.add('p-4', 'flex', 'justify-end', 'sticky', 'bottom-0', 'bg-white', 'border-t');
        let closeButton = document.createElement('button');
        closeButton.textContent = "Close";
        closeButton.classList.add('px-4', 'py-2', 'bg-primary', 'text-white', 'rounded');
        closeButton.onclick = function() {{
            document.body.removeChild(modalContainer);
        }};
        footer.appendChild(closeButton);
        
        // Assemble modal
        modalContent.appendChild(header);
        modalContent.appendChild(details);
        modalContent.appendChild(footer);
        
        modalContainer.appendChild(modalContent);
        document.body.appendChild(modalContainer);
    }}
    """
    
    await client.run_javascript(js_code)

# --- Admin Page Manager Class --- 
class AdminPageManager:
    def __init__(self):
        # Initialize pagination with rowsNumber = 0
        self.pagination_state = {'page': 1, 'rowsPerPage': 25, 'rowsNumber': 0, 'sortBy': 'user_id', 'descending': False}
        self.is_loading = False # Manual loading state variable
        self.users_table = None
        self.analysis_container = None
        self.summaries_container = None
        self.client = None
        # Flag to track if initial load has been triggered
        self._load_triggered = False
        # Common parameters for analysis and summaries
        self.date_selectors = None
        self.user_selector = None
        # self.total_users = 0 # No longer needed as separate variable

    async def handle_users_row_click(self, e):
        """Handles row clicks, showing user details."""
        print(f"Row selected: {e}")
        if isinstance(e, dict):  # Check if we got row data
            await show_user_details(e, client=self.client)
            if self.users_table:
                self.users_table.selected = []
        elif e is None: pass # Handle deselection if needed
        else: 
            if self.client and self.client.has_socket_connection:
                 js_command = "Quasar.plugins.Notify.create({ message: 'Could not interpret row click event data', type: 'negative' })"
                 self.client.run_javascript(js_command)

    async def get_users_page(self, props):
        """Fetches a single page of user data using the new paginated endpoint."""
        if not self.users_table: return

        pagination_in = props['pagination']
        page = pagination_in['page']
        rows_per_page = pagination_in['rowsPerPage']
        sort_by = pagination_in.get('sortBy', 'user_id')
        descending = pagination_in.get('descending', False)

        # print(f"--> Requesting paginated users: page={page}, limit={rows_per_page}, sort_by={sort_by}, descending={descending}")
        skip = (page - 1) * rows_per_page

        api_params = {
            'skip': skip,
            'limit': rows_per_page,
            'sort_by': sort_by,
            'descending': descending
        }

        # --- Set loading to true before request ---
        self.is_loading = True # Set manual loading state

        # Fetch data from the new paginated endpoint
        # !!! UPDATE '/users/paginated' if the final endpoint path is different !!!
        response_data = await api_request('GET', '/users/paginated', client=self.client, params=api_params)

        table_rows = []
        total_users = 0

        if response_data and isinstance(response_data, dict) and 'users' in response_data and 'total_users' in response_data:
            users_page_data = response_data['users']
            total_users = response_data['total_users']
            print(f"<-- Received {len(users_page_data)} users (total: {total_users})")

            for user in users_page_data:
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
                    'message_count': user.get('message_count', 0),
                    'start_time': 'Never',
                    'last_activity': last_active_str
                })

            self.users_table.rows = table_rows

            new_pagination = dict(pagination_in)
            new_pagination['rowsNumber'] = total_users
            self.users_table.pagination = new_pagination
            self.pagination_state.update(new_pagination)

            if self.client and self.client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Loaded page {page} ({len(table_rows)} of {total_users} users)', type: 'positive', position: 'bottom-right', timeout: 1500 }})"
                self.client.run_javascript(js_command)
        else:
            print("ERROR: Invalid response format from paginated users endpoint or API error.")
            self.users_table.rows = []
            new_pagination = dict(pagination_in)
            new_pagination['rowsNumber'] = total_users # Use 0 if fetch failed
            self.users_table.pagination = new_pagination
            self.pagination_state.update(new_pagination)

        # --- Set loading to false after request (success or failure) ---
        self.is_loading = False # Set manual loading state

    async def handle_request_event(self, event_args):
        """Handles the Quasar table's @request event for server-side pagination."""
        # Access event arguments correctly: event_args.args should be the dictionary
        if event_args and hasattr(event_args, 'args') and isinstance(event_args.args, dict):
            request_props = event_args.args # Correctly access the dictionary
            if 'pagination' in request_props:
                print(f"Handling @request event with props: {request_props}")
                # Pass the entire request_props, which contains the requested pagination state
                await self.get_users_page(request_props) 
            else:
                print(f"WARN: @request event with unexpected props format: {request_props}")
        else:
            print("WARN: @request event with missing, invalid arguments, or args not a dict.")

    async def initial_load(self):
        """Performs the initial data load using the new paginated endpoint."""
        # Add a guard to prevent multiple calls
        if self.is_loading:  # Skip if already loading
            print("Skipping duplicate initial_load call - already loading")
            return
        
        # Set loading state to true
        self.is_loading = True
        
        try:
            print("Performing initial user load...")
            await self.get_users_page({'pagination': self.pagination_state})
        finally:
            # Make sure to reset the loading state even if there's an error
            self.is_loading = False

    async def generate_macro_analysis(self, max_summaries_input, tabs_ref):
        """Handles the macro analysis generation."""
        if not self.analysis_container: return
        
        tabs_ref.set_value("Macro Analysis")
        
        limit = int(max_summaries_input.value)
        top_n_questions = 15
        self.analysis_container.clear()

        with self.analysis_container:
            ui.label('Fetching and visualizing analysis data...').classes('text-h6 mb-2')
            ui.spinner('dots', size='lg').classes('text-primary')
        tabs_ref.set_value("Macro Analysis")
        
        # Extract date range and user selection, if available
        date_params = {}
        if self.date_selectors:
            start_date, start_hour, end_date, end_hour = self.date_selectors
            date_params = {
                "start_date": str(start_date.value),  # Ensure it's a string
                "start_hour": int(start_hour.value),
                "end_date": str(end_date.value),      # Ensure it's a string
                "end_hour": int(end_hour.value),
                "limit": limit
            }
            
        # Add user filter if available and not set to 'all'
        if self.user_selector and self.user_selector.value and 'all' not in self.user_selector.value:
            user_ids = [int(uid) for uid in self.user_selector.value if uid.isdigit()]
            if user_ids:
                date_params['user_ids'] = user_ids

        print(f"\n=== FETCHING VISUALIZATION DATA (limit={limit}) ===")
        print(f"Date params: {date_params}")
        
        # All analysis endpoints now use POST with a request body instead of GET with query parameters
        results = await asyncio.gather(
            # Using new POST endpoints with the date_params as the request body
            api_request('POST', '/analysis/topic-sentiment', client=self.client, json_data=date_params, params={'limit': limit}),
            api_request('POST', '/analysis/user-satisfaction', client=self.client, json_data=date_params, params={'limit': limit}),
            api_request('POST', '/analysis/conversation-types', client=self.client, json_data=date_params, params={'limit': limit}),
            api_request('POST', '/analysis/top-questions', client=self.client, json_data=date_params, params={'limit': limit, 'top_n': top_n_questions}),
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
                    for error in errors:
                        ui.label(f"- {error}").classes('text-negative')
                if self.client and self.client.has_socket_connection:
                    js_command = f"Quasar.plugins.Notify.create({{ message: 'Some analysis data failed to load.', type: 'warning' }})"
                    self.client.run_javascript(js_command)
            
            with ui.card().classes('w-full mb-4 p-4'):
                ui.label('Analysis Parameters').classes('text-h6 mb-2')
                with ui.row().classes('w-full justify-between'):
                    with ui.column().classes('mr-4'):
                        ui.label(f'Max Conversations: {limit}').classes('text-subtitle1')
                        if date_params:
                            ui.label(f'Date Range: {date_params["start_date"]} {date_params["start_hour"]}:00 to {date_params["end_date"]} {date_params["end_hour"]}:59').classes('text-subtitle1')
                        if self.user_selector and self.user_selector.value:
                            ui.label(f'Users: {", ".join(self.user_selector.value)}').classes('text-subtitle1')

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
                    with ui.card().classes('w-full mb-4 p-4'):
                        ui.label('Topic Sentiment Analysis').classes('text-h6 mb-2')
                        ui.label('Data not available.').classes('text-gray-500 italic')
            except Exception as e:
                print(f"Error generating topic heatmap: {e}")
                ui.label(f'Error: {str(e)}').classes('text-negative')
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
                        with ui.card().classes('w-full md:w-1/2 p-4'):
                            ui.label('User Satisfaction').classes('text-h6 mb-2')
                            ui.label('Data not available.').classes('text-gray-500 italic')
                except Exception as e:
                    print(f"Error generating satisfaction chart: {e}")
                    ui.label(f'Error: {str(e)}').classes('text-negative')
                try:
                    if types_chart_data:
                        with ui.card().classes('w-full md:w-1/2 p-4'):
                            ui.label('Conversation Types').classes('text-h6 mb-2')
                            fig_types = go.Figure(data=[go.Pie(labels=types_chart_data.get('types', []), values=types_chart_data.get('counts', []), hole=.3)])
                            fig_types.update_layout(title='Distribution of Conversation Types', autosize=True, margin=dict(l=30, r=30, t=50, b=50), height=350, legend_title_text='Types')
                            ui.plotly(fig_types).classes('w-full').props('responsive=true').style('height: 350px; max-width: 100%; overflow: visible;')
                    else: 
                        with ui.card().classes('w-full md:w-1/2 p-4'):
                            ui.label('Conversation Types').classes('text-h6 mb-2')
                            ui.label('Data not available.').classes('text-gray-500 italic')
                except Exception as e:
                    print(f"Error generating types chart: {e}")
                    ui.label(f'Error: {str(e)}').classes('text-negative')
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
                    with ui.card().classes('w-full mb-4 p-4'):
                        ui.label('Top User Questions').classes('text-h6 mb-2')
                        ui.label('Data not available.').classes('text-gray-500 italic')
            except Exception as e:
                print(f"Error generating questions table: {e}")
                ui.label(f'Error: {str(e)}').classes('text-negative')
            
            print("All visualizations complete")
            if self.client and self.client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Analysis visualization complete!', type: 'positive', timeout: 3000 }})"
                self.client.run_javascript(js_command)

            with ui.row().classes('justify-end mt-4'):
                # Need to wrap the call in a lambda or partial to pass arguments correctly
                ui.button('Run New Analysis', icon='refresh', 
                          on_click=lambda: asyncio.create_task(self.generate_macro_analysis(max_summaries_input, tabs_ref))).props('color=primary')

    async def generate_summaries(self, max_summaries_input, tabs_ref):
        """Handles the summary generation based on date range and user selection."""
        if not self.summaries_container: return
        
        tabs_ref.set_value("Conversation Summaries")
        
        limit = int(max_summaries_input.value)
        self.summaries_container.clear()

        with self.summaries_container:
            ui.label('Fetching summaries...').classes('text-h6 mb-2')
            ui.spinner('dots', size='lg').classes('text-primary')
        
        # Extract date range and user selection
        start_date, start_hour, end_date, end_hour = self.date_selectors
        user_ids = self.user_selector.value if self.user_selector.value else ['all']
        
        # Create the request body - Make sure all fields are properly typed
        request_data = {
            "start_date": str(start_date.value),  # Ensure it's a string
            "start_hour": int(start_hour.value),
            "end_date": str(end_date.value),      # Ensure it's a string
            "end_hour": int(end_hour.value),
            "limit": limit
        }
        
        # Only include user_ids if specific users are selected (not 'all')
        if 'all' not in user_ids:
            request_data["user_ids"] = [int(uid) for uid in user_ids if uid.isdigit()]
        
        print(f"Request data: {request_data}")
        
        # First generate the summaries using the new batch-generate endpoint
        generate_result = await api_request('POST', '/summaries/generate-batch', client=self.client, json_data=request_data)
        
        if generate_result:
            # Use client-based notification instead of ui.notify
            if self.client and self.client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Generated {len(generate_result)} summaries', type: 'positive', timeout: 3000 }})"
                self.client.run_javascript(js_command)
            
            # Now fetch the generated summaries
            summaries_data = await api_request('POST', '/summaries/by-date-range', client=self.client, json_data=request_data)
        else:
            # Use client-based notification instead of ui.notify
            if self.client and self.client.has_socket_connection:
                js_command = "Quasar.plugins.Notify.create({ message: 'Failed to generate summaries', type: 'negative', timeout: 3000 })"
                self.client.run_javascript(js_command)
            summaries_data = None
        
        self.summaries_container.clear()
        
        with self.summaries_container:
            ui.label('Conversation Summaries').classes('text-h5 mb-4')
            
            # Display metadata about the query
            with ui.card().classes('w-full mb-4 p-4'):
                ui.label('Query Parameters').classes('text-h6 mb-2')
                with ui.row().classes('w-full justify-between'):
                    with ui.column().classes('mr-4'):
                        ui.label(f'Date Range: {start_date.value} {int(start_hour.value)}:00 to {end_date.value} {int(end_hour.value)}:59').classes('text-subtitle1')
                        ui.label(f'Users: {", ".join(user_ids)}').classes('text-subtitle1')
                        ui.label(f'Max Summaries: {limit}').classes('text-subtitle1')
                    
                    with ui.row():
                        ui.button('Refresh Summaries', icon='refresh', 
                                on_click=lambda: asyncio.create_task(self.generate_summaries(max_summaries_input, tabs_ref))).props('color=primary')
            
            if summaries_data and isinstance(summaries_data, list):
                # Create table columns
                columns = [
                    {'name': 'summary_id', 'field': 'summary_id', 'label': 'ID', 'align': 'left'},
                    {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left'},
                    {'name': 'session_id', 'field': 'session_id', 'label': 'Session ID', 'align': 'left'},
                    {'name': 'created_at', 'field': 'created_at', 'label': 'Created At', 'align': 'left'},
                    {'name': 'logged', 'field': 'logged', 'label': 'Logged User', 'align': 'center'},
                    {'name': 'summary', 'field': 'summary', 'label': 'Summary', 'align': 'left'},
                ]
                
                # Format the data for the table
                rows = []
                for summary in summaries_data:
                    # Format timestamp
                    created_at = summary.get('created_at', '')
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, AttributeError):
                        formatted_time = created_at
                    
                    # Format logged status
                    logged = 'Yes' if summary.get('logged') else 'No'
                    
                    # Get the full summary text
                    full_summary = summary.get('summary', '')
                    
                    # Add to rows
                    rows.append({
                        'summary_id': summary.get('summary_id', ''),
                        'user_id': summary.get('user_id', ''),
                        'session_id': summary.get('session_id', ''),
                        'created_at': formatted_time,
                        'logged': logged,
                        'summary': full_summary[:100] + '...' if len(full_summary) > 100 else full_summary,
                        'original_summary': full_summary  # Store the full text
                    })
                
                ui.label(f'Found {len(rows)} summaries').classes('text-h6 mt-4 mb-2')
                
                # Create the table with the data
                summaries_table = self.show_summaries_table(columns, rows)
                
                # Show success notification
                if self.client and self.client.has_socket_connection:
                    js_command = f"Quasar.plugins.Notify.create({{ message: 'Successfully loaded {len(rows)} summaries', type: 'positive', timeout: 3000 }})"
                    self.client.run_javascript(js_command)
            else:
                ui.label('No summaries found for the specified criteria.').classes('text-h6 mt-4 text-center')
                if self.client and self.client.has_socket_connection:
                    js_command = "Quasar.plugins.Notify.create({ message: 'No summaries found for the specified criteria', type: 'warning', timeout: 3000 })"
                    self.client.run_javascript(js_command)
                    
    async def show_summaries(self, max_summaries_input, tabs_ref):
        """Fetches and displays summaries without generating new ones."""
        if not self.summaries_container: return
        
        tabs_ref.set_value("Conversation Summaries")
        
        limit = int(max_summaries_input.value)
        self.summaries_container.clear()

        with self.summaries_container:
            ui.label('Fetching existing summaries...').classes('text-h6 mb-2')
            ui.spinner('dots', size='lg').classes('text-primary')
        
        # Extract date range and user selection
        start_date, start_hour, end_date, end_hour = self.date_selectors
        user_ids = self.user_selector.value if self.user_selector.value else ['all']
        
        # Create the request body - Make sure all fields are properly typed
        request_data = {
            "start_date": str(start_date.value),  # Ensure it's a string
            "start_hour": int(start_hour.value),
            "end_date": str(end_date.value),      # Ensure it's a string
            "end_hour": int(end_hour.value),
            "limit": limit
        }
        
        # Only include user_ids if specific users are selected (not 'all')
        if 'all' not in user_ids:
            request_data["user_ids"] = [int(uid) for uid in user_ids if uid.isdigit()]
        
        # Fetch existing summaries without generating new ones
        summaries_data = await api_request('POST', '/summaries/by-date-range', client=self.client, json_data=request_data)
        
        self.summaries_container.clear()
        
        with self.summaries_container:
            ui.label('Conversation Summaries').classes('text-h5 mb-4')
            
            # Display metadata about the query
            with ui.card().classes('w-full mb-4 p-4'):
                ui.label('Query Parameters').classes('text-h6 mb-2')
                with ui.row().classes('w-full justify-between'):
                    with ui.column().classes('mr-4'):
                        ui.label(f'Date Range: {start_date.value} {int(start_hour.value)}:00 to {end_date.value} {int(end_hour.value)}:59').classes('text-subtitle1')
                        ui.label(f'Users: {", ".join(user_ids)}').classes('text-subtitle1')
                        ui.label(f'Max Summaries: {limit}').classes('text-subtitle1')
                    
                    with ui.row():
                        ui.button('Refresh', icon='refresh', 
                                on_click=lambda: asyncio.create_task(self.show_summaries(max_summaries_input, tabs_ref))).props('color=primary flat size="sm"')
            
            if summaries_data and isinstance(summaries_data, list):
                # Create table columns
                columns = [
                    {'name': 'summary_id', 'field': 'summary_id', 'label': 'ID', 'align': 'left'},
                    {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left'},
                    {'name': 'session_id', 'field': 'session_id', 'label': 'Session ID', 'align': 'left'},
                    {'name': 'created_at', 'field': 'created_at', 'label': 'Created At', 'align': 'left'},
                    {'name': 'logged', 'field': 'logged', 'label': 'Logged User', 'align': 'center'},
                    {'name': 'summary', 'field': 'summary', 'label': 'Summary', 'align': 'left'},
                ]
                
                # Format the data for the table
                rows = []
                for summary in summaries_data:
                    # Format timestamp
                    created_at = summary.get('created_at', '')
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, AttributeError):
                        formatted_time = created_at
                    
                    # Format logged status
                    logged = 'Yes' if summary.get('logged') else 'No'
                    
                    # Get the full summary text
                    full_summary = summary.get('summary', '')
                    
                    # Add to rows
                    rows.append({
                        'summary_id': summary.get('summary_id', ''),
                        'user_id': summary.get('user_id', ''),
                        'session_id': summary.get('session_id', ''),
                        'created_at': formatted_time,
                        'logged': logged,
                        'summary': full_summary[:100] + '...' if len(full_summary) > 100 else full_summary,
                        'original_summary': full_summary  # Store the full text
                    })
                
                ui.label(f'Found {len(rows)} summaries').classes('text-h6 mt-4 mb-2')
                
                # Create the table with the data
                summaries_table = self.show_summaries_table(columns, rows)
                
                # Show success notification
                if self.client and self.client.has_socket_connection:
                    js_command = f"Quasar.plugins.Notify.create({{ message: 'Successfully loaded {len(rows)} summaries', type: 'positive', timeout: 3000 }})"
                    self.client.run_javascript(js_command)
            else:
                ui.label('No summaries found for the specified criteria.').classes('text-h6 mt-4 text-center')
                if self.client and self.client.has_socket_connection:
                    js_command = "Quasar.plugins.Notify.create({ message: 'No summaries found for the specified criteria', type: 'warning', timeout: 3000 })"
                    self.client.run_javascript(js_command)

    def show_summaries_table(self, columns, rows):
        """Helper to create the summaries table with row click handler."""
        # Create a deep copy of the rows with full summary text
        full_rows = []
        for row in rows:
            full_row = row.copy()
            # Store the untruncated summary in the data if needed
            if 'summary' in row and '...' in row['summary']:
                # Keep the full summary in an attribute but display the truncated version
                original_summary = row.get('original_summary', '')
                if original_summary:
                    full_row['full_summary'] = original_summary
            full_rows.append(full_row)
        
        table = ui.table(
            columns=columns,
            rows=full_rows,
            row_key='summary_id',
        ).classes('w-full')
        table.props('flat bordered separator=cell')
        # Add row click handler via rowClick event
        table.on('rowClick', lambda e: asyncio.create_task(show_summary_details(e.args[1], client=self.client)))
        return table

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
                ui.tab('Conversation Summaries', icon='summarize') # New tab for summaries
                ui.tab('Macro Analysis', icon='analytics')
            tabs.set_value('Users Table')

            with ui.tab_panels(tabs, value='Users Table').classes('w-full').props('animated keep-alive'):
                # --- Users Table Panel --- 
                with ui.tab_panel('Users Table'):
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        ui.label('Click row for details').classes('text-sm text-gray-600')
                        ui.button('Refresh', icon='refresh', on_click=lambda: asyncio.create_task(self.initial_load())).props('flat color=primary size="sm"')

                    # Full-screen semi-transparent overlay
                    self.loading_overlay = ui.element('div').classes('fixed inset-0 bg-black/50 z-[999]') # Use z-[999] for high z-index
                    self.loading_overlay.bind_visibility_from(self, 'is_loading')

                    # Manual spinner for loading state
                    self.loading_spinner = ui.spinner('dots', size='lg').classes('text-white fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-[1000]') # Use z-[1000] for even higher z-index and white color for visibility on dark overlay
                    self.loading_spinner.bind_visibility_from(self, 'is_loading') # Corrected method name

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
                    ).classes('w-full')
                    # Enable server-side pagination via @request event
                    # Ensure sortable columns work with the @request event
                    self.users_table.props('flat bordered separator=cell pagination=@request="onRequest"')
                    self.users_table.on('request', lambda e: asyncio.create_task(self.handle_request_event(e)))
                    self.users_table.props('loading=false') # Ensure built-in loading is off
                    # Add row click handler via rowClick event
                    self.users_table.on('rowClick', lambda e: asyncio.create_task(self.handle_users_row_click(e.args[1])))
                    
                    # Schedule initial load - but only if not already triggered
                    if not self._load_triggered:
                        self._load_triggered = True
                        # Use a short delay to ensure the UI is fully rendered
                        ui.timer(0.1, lambda: asyncio.create_task(self.initial_load()), once=True)
                
                # --- Conversation Summaries Panel --- 
                with ui.tab_panel('Conversation Summaries'):
                    with ui.column().classes('w-full p-4'):
                        ui.label('Conversation Summaries').classes('text-h5 q-mb-md')
                        
                        # Add options panel inside this tab
                        with ui.card().classes('w-full mb-4 p-4'):
                            ui.label('Summary Options').classes('text-h6 mb-2')
                            
                            # Create date range selector
                            self.date_selectors = create_date_range_selector()
                            
                            # Create user selector
                            self.user_selector, refresh_users_func = create_user_selector()
                            
                            # Create max summaries input
                            with ui.row().classes('w-full mt-2 items-center'):
                                max_summaries_input = ui.number(value=100, min=10, max=1000, label='Max Items').classes('w-40')
                                max_summaries_input.props('outlined')
                                
                                ui.button('Refresh Users', icon='refresh', on_click=refresh_users_func).props('flat color=primary q-ml-md size="sm"')
                        
                        # Action buttons for summaries - separate buttons for showing and generating
                        with ui.row().classes('w-full justify-end mb-4 gap-2'):
                            # Show summaries button - just fetches existing summaries
                            show_btn = ui.button('Show Summaries', icon='visibility', 
                                              on_click=lambda: asyncio.create_task(self.show_summaries(max_summaries_input, tabs)))
                            show_btn.props('color=primary size="sm"')
                            
                            # Generate summaries button - creates new summaries
                            generate_btn = ui.button('Generate Summaries', icon='summarize', 
                                                   on_click=lambda: asyncio.create_task(self.generate_summaries(max_summaries_input, tabs)))
                            generate_btn.props('color=secondary size="sm"')
                        
                        # Define the summaries container and store reference in class
                        self.summaries_container = ui.column().classes('w-full mt-4 border rounded p-4 min-h-[500px]')
                        with self.summaries_container:
                            ui.label('Use "Show Summaries" to view existing summaries or "Generate Summaries" to create new ones').classes('text-gray-500 italic text-center w-full py-8')

                # --- Macro Analysis Panel --- 
                with ui.tab_panel('Macro Analysis'):
                    with ui.column().classes('w-full p-4'):
                        ui.label('Conversation Macro Analysis').classes('text-h5 q-mb-md')
                        
                        # Same options panel for this tab
                        with ui.card().classes('w-full mb-4 p-4'):
                            ui.label('Analysis Options').classes('text-h6 mb-2')
                            
                            # Reuse the same date selector and user selector components
                            # No need to recreate them, they're already stored in self.date_selectors and self.user_selector
                            
                            # Create max analysis input (reusing the same max_summaries_input)
                            ui.label(f'Using the date range, user selection, and max items ({max_summaries_input.value}) from the Summaries tab').classes('text-subtitle1 q-mb-sm')
                        
                        # Action buttons for analysis
                        with ui.row().classes('w-full justify-end mb-4'):
                            analyze_btn = ui.button('Generate Analysis', icon='analytics', 
                                                   on_click=lambda: asyncio.create_task(self.generate_macro_analysis(max_summaries_input, tabs)))
                            analyze_btn.props('color=primary size="sm"')
                    
                        # Define the analysis container and store reference in class
                        self.analysis_container = ui.column().classes('w-full mt-4 border rounded p-4 min-h-[500px]')
                        with self.analysis_container:
                            ui.label('Click "Generate Analysis" to create visualizations based on the selected criteria').classes('text-gray-500 italic text-center w-full py-8')
                        
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

# Add a global admin_manager variable at the top of the file
# Add this after your imports
admin_manager = None

# Modify the page_admin function
@ui.page('/admin')
async def page_admin():
    """Admin page handler - creates a singleton manager instance."""
    global admin_manager
    
    # Only create the manager once
    if admin_manager is None:
        admin_manager = AdminPageManager()
        # Build the UI once
        admin_manager.build_ui()
    
# --- No ui.run() ---