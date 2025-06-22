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
from utils.auth_middleware import auth_required

# Use the specific imports from your snippet
from utils.layouts import create_navigation_menu_2, create_date_range_selector, create_user_selector # Re-added imports

# Add database imports for conversation functionality
from utils.database_singleton import get_db

# Load environment variables
load_dotenv(override=True)

# API Configuration - Use environment variables to determine API URL
def get_api_base_url():
    """Get the API base URL based on environment configuration."""
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Strip comments and whitespace from environment variable
    if environment:
        environment = environment.split('#')[0].strip().lower()
    else:
        environment = "development"
    
    if environment == "production":
        return os.getenv("ADMIN_API_URL_PRODUCTION", "https://analytics-api-604277815223.us-central1.run.app/api/v1")
    else:
        return os.getenv("ADMIN_API_URL_LOCAL", "http://localhost:8000/api/v1")

API_BASE_URL = get_api_base_url()
API_KEY = os.getenv("FI_ANALYTICS_API_KEY")

print(f"Admin API Configuration:")
print(f"  Environment: {os.getenv('ENVIRONMENT', 'development')}")
print(f"  Parsed Environment: {os.getenv('ENVIRONMENT', 'development').split('#')[0].strip().lower() if os.getenv('ENVIRONMENT') else 'development'}")
print(f"  API Base URL: {API_BASE_URL}")
print(f"  API Key configured: {'Yes' if API_KEY else 'No'}")

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

# --- Helper Functions for User Details Modal ---
def generate_user_avatar(user_email):
    """Generate a unique avatar URL based on user email."""
    if not user_email:
        return 'https://robohash.org/default?bgset=bg2&size=64x64'
    return f'https://robohash.org/{user_email}?bgset=bg2&size=64x64'

def format_timestamp(ts):
    """Format timestamp for display."""
    if not ts:
        return "Unknown time"
    if isinstance(ts, str):
        try:
            dt_obj = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt_obj.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return ts 
    return ts.strftime("%Y-%m-%d %H:%M")

# --- Enhanced Dialog Handler Function ---
async def show_user_details(user_data, client=None):
    """Creates and shows a dialog with user details, conversation selector, and chat display."""
    if not isinstance(user_data, dict) or not client or not client.has_socket_connection:
        return
    
    name = user_data.get('name', 'N/A')  # Use 'name' field from table row
    user_id = user_data.get('user_id', 'N/A')  # Use 'user_id' field from table row
    logged = user_data.get('logged', 'N/A')  # Use 'logged' field from table row
    
    # Get user email from API to use with database methods
    user_details = await api_request('GET', f'/users/{user_id}', client=client)
    if not user_details:
        if client and client.has_socket_connection:
            js_command = "Quasar.plugins.Notify.create({ message: 'Could not fetch user details', type: 'negative' })"
            client.run_javascript(js_command)
        return
    
    user_email = user_details.get('email', '')
    if not user_email:
        if client and client.has_socket_connection:
            js_command = "Quasar.plugins.Notify.create({ message: 'User email not found', type: 'negative' })"
            client.run_javascript(js_command)
        return
    
    # Get database adapter to fetch conversations
    try:
        db_adapter = await get_db()
    except Exception as e:
        print(f"Error getting database adapter: {e}")
        if client and client.has_socket_connection:
            js_command = "Quasar.plugins.Notify.create({ message: 'Database connection error', type: 'negative' })"
            client.run_javascript(js_command)
        return
    
    # Fetch conversations for user
    try:
        conversations = await db_adapter.get_chat_sessions_for_user(user_email)
    except Exception as e:
        print(f"Error fetching conversations: {e}")
        conversations = []
    
    placeholder_id = f"user_modal_{user_id}"
    
    # Create enhanced modal with conversation selector
    js_code = f"""
    // Create modal container if it doesn't exist
    let modalContainer = document.getElementById("{placeholder_id}");
    if (!modalContainer) {{
        modalContainer = document.createElement('div');
        modalContainer.id = "{placeholder_id}";
        modalContainer.classList.add('fixed', 'inset-0', 'bg-black', 'bg-opacity-30', 
            'flex', 'items-center', 'justify-center', 'z-50');
        modalContainer.style.display = 'flex';
        
        // Create modal content - larger size for conversation display
        let modalContent = document.createElement('div');
        modalContent.classList.add('bg-white', 'rounded-lg', 'shadow-xl', 'w-4/5', 
            'max-w-5xl', 'max-h-[95vh]', 'overflow-y-auto', 'flex', 'flex-col');
        
        // Header
        let header = document.createElement('div');
        header.classList.add('bg-primary', 'text-white', 'p-4', 'flex', 'justify-between', 'items-center', 'sticky', 'top-0', 'z-10');
        let title = document.createElement('h3');
        title.textContent = "User Details: " + "{name}";
        title.classList.add('text-lg', 'font-bold', 'flex-grow');
        let closeBtn = document.createElement('button');
        closeBtn.textContent = "×";
        closeBtn.classList.add('text-xl', 'font-bold', 'ml-4', 'hover:bg-white', 'hover:text-primary', 'rounded', 'px-2');
        closeBtn.onclick = function() {{
            document.body.removeChild(modalContainer);
        }};
        header.appendChild(title);
        header.appendChild(closeBtn);
        
        // User details section
        let details = document.createElement('div');
        details.classList.add('p-4', 'bg-gray-50', 'border-b');
        details.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><strong>User ID:</strong> {user_id}</div>
                <div><strong>Name:</strong> {name}</div>
                <div><strong>Email:</strong> {user_email}</div>
                <div><strong>Active:</strong> {logged}</div>
            </div>
        `;
        
        // Conversation selector section
        let selectorSection = document.createElement('div');
        selectorSection.classList.add('p-4', 'border-b');
        
        let selectorLabel = document.createElement('label');
        selectorLabel.textContent = 'Select Conversation:';
        selectorLabel.classList.add('block', 'text-sm', 'font-medium', 'mb-2');
        
        let conversationSelect = document.createElement('select');
        conversationSelect.id = "conversation_select_{user_id}";
        conversationSelect.classList.add('w-full', 'p-2', 'border', 'rounded', 'bg-white');
        
        // Add default option
        let defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select a conversation to view...';
        conversationSelect.appendChild(defaultOption);
        
        selectorSection.appendChild(selectorLabel);
        selectorSection.appendChild(conversationSelect);
        
        // Messages container section
        let messagesSection = document.createElement('div');
        messagesSection.classList.add('flex-grow', 'p-4');
        
        let messagesContainer = document.createElement('div');
        messagesContainer.id = "conversation_display_{user_id}";
        messagesContainer.classList.add('h-[50vh]', 'overflow-y-auto', 'border', 'rounded', 'bg-gray-50', 'p-4', 'conversation-scroll');
        messagesContainer.innerHTML = `
            <div class="flex items-center justify-center h-full text-gray-500">
                <div class="text-center">
                    <div class="mb-2">💬</div>
                    <p>Select a conversation to view messages</p>
                </div>
            </div>
        `;
        
        messagesSection.appendChild(messagesContainer);
        
        // Footer
        let footer = document.createElement('div');
        footer.classList.add('p-4', 'flex', 'justify-end', 'sticky', 'bottom-0', 'bg-white', 'border-t');
        let closeButton = document.createElement('button');
        closeButton.textContent = "Close";
        closeButton.classList.add('px-4', 'py-2', 'bg-primary', 'text-white', 'rounded', 'hover:bg-blue-600');
        closeButton.onclick = function() {{
            document.body.removeChild(modalContainer);
        }};
        footer.appendChild(closeButton);
        
        // Assemble modal
        modalContent.appendChild(header);
        modalContent.appendChild(details);
        modalContent.appendChild(selectorSection);
        modalContent.appendChild(messagesSection);
        modalContent.appendChild(footer);
        
        modalContainer.appendChild(modalContent);
        document.body.appendChild(modalContainer);
    }}
    """
    
    await client.run_javascript(js_code)
    
    # Populate conversation selector
    if conversations:
        # Sort conversations by last message timestamp (most recent first)
        conversations_sorted = sorted(conversations, key=lambda x: x.get('last_message_timestamp', ''), reverse=True)
        
        options_html = ""
        most_recent_session_id = None
        for i, conv in enumerate(conversations_sorted):
            session_id = conv.get('session_id', '')
            preview = conv.get('first_message_content', 'No messages')[:50]
            if len(conv.get('first_message_content', '')) > 50:
                preview += "..."
            timestamp = format_timestamp(conv.get('last_message_timestamp'))
            message_count = conv.get('message_count', 0)
            
            option_text = f"{preview} ({message_count} msgs) - {timestamp}"
            options_html += f'<option value="{session_id}">{option_text}</option>'
            
            # Store the most recent session ID (first in sorted list)
            if i == 0:
                most_recent_session_id = session_id
        
        populate_js = f"""
        let select = document.getElementById("conversation_select_{user_id}");
        if (select) {{
            select.innerHTML = `
                <option value="">Select a conversation to view...</option>
                {options_html}
            `;
            
            // Add change event listener
            select.addEventListener('change', function() {{
                if (this.value) {{
                    window.loadConversationInModal('{user_id}', this.value, '{user_email}');
                }}
            }});
            
            // Auto-select the most recent conversation
            {f"select.value = '{most_recent_session_id}';" if most_recent_session_id else ""}
        }}
        """
        await client.run_javascript(populate_js)
        
        # Auto-load the most recent conversation
        if most_recent_session_id:
            print(f"Auto-loading most recent conversation: {most_recent_session_id}")
            await load_conversation_for_modal(user_id, most_recent_session_id, user_email, db_adapter, client)
    
    # Set up conversation loading with polling mechanism
    conversation_request_key = f"conversation_request_{user_id}"
    
    # JavaScript to handle conversation selection and set up polling
    setup_conversation_js = f"""
    // Set up conversation loading with polling mechanism
    window.conversationRequests = window.conversationRequests || {{}};
    
    window.loadConversationInModal = async function(userId, sessionId, userEmail) {{
        let container = document.getElementById("conversation_display_" + userId);
        if (!container) return;
        
        // Show loading spinner
        container.innerHTML = `
            <div class="flex flex-col justify-center items-center h-full">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-3"></div>
                <p class="text-gray-600 font-medium">Loading conversation...</p>
            </div>
        `;
        
        // Set the conversation request
        window.conversationRequests['{conversation_request_key}'] = {{
            sessionId: sessionId,
            timestamp: Date.now()
        }};
    }};
    """
    await client.run_javascript(setup_conversation_js)
    
    # Start polling for conversation requests
    async def poll_for_conversation_requests():
        while True:
            try:
                # Check if there's a conversation request
                request_data = await client.run_javascript(f"""
                if (window.conversationRequests && window.conversationRequests['{conversation_request_key}']) {{
                    let request = window.conversationRequests['{conversation_request_key}'];
                    delete window.conversationRequests['{conversation_request_key}'];
                    return request;
                }}
                return null;
                """, timeout=1.0)
                
                if request_data and isinstance(request_data, dict):
                    session_id = request_data.get('sessionId')
                    if session_id:
                        print(f"Processing conversation request for session: {session_id}")
                        await load_conversation_for_modal(user_id, session_id, user_email, db_adapter, client)
                
                # Sleep briefly before next poll
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Error in conversation polling: {e}")
                await asyncio.sleep(1.0)
                
            # Check if modal still exists, if not, break the polling loop
            try:
                modal_exists = await client.run_javascript(f"""
                return document.getElementById('{placeholder_id}') !== null;
                """, timeout=0.5)
                if not modal_exists:
                    print(f"Modal {placeholder_id} no longer exists, stopping polling")
                    break
            except:
                # If we can't check modal existence, assume it's gone
                break
    
    # Start the polling task
    asyncio.create_task(poll_for_conversation_requests())

async def load_conversation_for_modal(user_id, session_id, user_email, db_adapter, client):
    """Load and display a specific conversation in the modal."""
    try:
        # Fetch conversation messages
        messages = await db_adapter.get_recent_messages(session_id=session_id, limit=100)
        
        if not messages:
            no_messages_html = '''
                <div class="flex items-center justify-center h-full text-gray-500">
                    <p>No messages found in this conversation</p>
                </div>
            '''
            update_js = f"""
            let container = document.getElementById("conversation_display_{user_id}");
            if (container) {{
                container.innerHTML = `{no_messages_html}`;
            }}
            """
            await client.run_javascript(update_js)
            return
        
        # Generate messages HTML in chat format (same as chat.py)
        messages_html = ""
        for message in messages:
            role = message.get('role', '')
            # Properly escape HTML content to prevent issues
            raw_content = message.get('content', '')
            # Convert newlines to HTML breaks and escape quotes for JavaScript
            content = raw_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>').replace("'", "&#39;").replace('"', '&quot;')
            timestamp_str = message.get('created_at', message.get('timestamp', ''))
            
            # Format timestamp
            try:
                if timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    time_str = dt.strftime("%H:%M")
                else:
                    time_str = ""
            except (ValueError, AttributeError):
                time_str = ""
            
            if role == 'user':
                # User message with avatar (right side)
                messages_html += f'''
                <div class="flex justify-end items-end gap-2 mb-4 fade-in">
                    <div class="bg-blue-500 text-white p-3 rounded-lg max-w-[80%] break-words conversation-message">
                        {f'<div class="text-xs opacity-70 mb-1">{time_str}</div>' if time_str else ''}
                        <div>{content}</div>
                    </div>
                    <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                        👤
                    </div>
                </div>
                '''
            else:
                # Assistant message with avatar (left side)
                messages_html += f'''
                <div class="flex justify-start items-end gap-2 mb-4 fade-in">
                    <div class="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                        🤖
                    </div>
                    <div class="bg-gray-200 p-3 rounded-lg max-w-[80%] break-words conversation-message">
                        {f'<div class="text-xs opacity-70 mb-1">{time_str}</div>' if time_str else ''}
                        <div>{content}</div>
                    </div>
                </div>
                '''
        
        # Update the conversation display
        update_js = f"""
        let container = document.getElementById("conversation_display_{user_id}");
        if (container) {{
            container.innerHTML = `
                <div class="space-y-2">
                    {messages_html}
                </div>
            `;
            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        }}
        """
        await client.run_javascript(update_js)
        
    except Exception as e:
        print(f"Error loading conversation {session_id}: {e}")
        error_html = f'''
            <div class="flex items-center justify-center h-full text-red-500">
                <p>Error loading conversation: {str(e)}</p>
            </div>
        '''
        update_js = f"""
        let container = document.getElementById("conversation_display_{user_id}");
        if (container) {{
            container.innerHTML = `{error_html}`;
        }}
        """
        await client.run_javascript(update_js)

# --- Conversation Loading Handler ---
# We need to add a way to trigger conversation loading from JavaScript
# This will be handled through a polling mechanism or WebSocket-like approach

async def show_summary_details(summary_data, client=None):
    """Shows a half-screen modal with all summary metadata and the full summary."""
    if not isinstance(summary_data, dict) or not client or not client.has_socket_connection:
        return
    
    # Extract the summary ID to fetch the complete data if needed
    summary_id = summary_data.get('summary_id', 'unknown')
    
    # Check if we need to fetch the full summary - if the summary key contains "..." it's likely truncated
    if '...' in summary_data.get('summary', '') and summary_id:
        # Fetch the complete summary data from the API
        print(f"DEBUG: Fetching full summary data for ID: {summary_id}")
        full_summary_data = await api_request('GET', f'/summaries/{summary_id}', client=client)
        if full_summary_data and isinstance(full_summary_data, dict):
            # Replace our data with the complete version
            summary_data = full_summary_data
            print(f"DEBUG: Successfully fetched full summary data")
        else:
            print(f"DEBUG: Failed to fetch full summary data or invalid response")
    
    # Now extract all needed fields
    user_id = summary_data.get('user_id', 'N/A')
    conversation_id = summary_data.get('conversation_id', 'N/A')
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
            <p class="mb-2"><strong>Conversation ID:</strong> {conversation_id}</p>
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

        # Map frontend column names to API sort field names
        sort_field_mapping = {
            'user_id': 'user_id',
            'logged': 'is_active',
            'message_count': 'message_count',
            'last_activity': 'last_activity'
        }
        
        # Use the mapped field name for API call
        api_sort_by = sort_field_mapping.get(sort_by, 'user_id')

        print(f"--> Requesting paginated users: page={page}, limit={rows_per_page}, sort_by={sort_by} -> {api_sort_by}, descending={descending}")
        skip = (page - 1) * rows_per_page

        api_params = {
            'skip': skip,
            'limit': rows_per_page,
            'sort_by': api_sort_by,
            'descending': descending
        }

        # --- Set loading to true before request ---
        self.is_loading = True # Set manual loading state

        # Fetch data from the new paginated endpoint
        # !!! UPDATE '/users/paginated' if the final endpoint path is different !!!
        response_data = await api_request('GET', '/users/paginated', client=self.client, params=api_params)

        table_rows = []
        total_users = 0

        # Debug: Log the full response structure
        # print(f"DEBUG: Full response_data = {response_data}")

        if response_data and isinstance(response_data, dict) and 'users' in response_data and 'total_users' in response_data:
            users_page_data = response_data['users']
            total_users = response_data['total_users']
            print(f"<-- Received {len(users_page_data)} users (total: {total_users})")
        elif response_data and isinstance(response_data, list):
            # Fallback: Maybe the API returns a direct array instead of wrapped structure
            users_page_data = response_data
            total_users = len(response_data)
            print(f"<-- Received direct array: {len(users_page_data)} users")
        else:
            print("ERROR: Invalid response format from paginated users endpoint or API error.")
            users_page_data = []
            total_users = 0

        if users_page_data:
            for user in users_page_data:
                # Debug logging to see actual API response values
                # print(f"DEBUG: User data - id: {user.get('id')}, message_count: {user.get('message_count')}, created_at: {user.get('created_at')}")
                
                last_active_str = 'Never'
                raw_last_active = user.get('last_active')
                if raw_last_active:
                    try:
                        last_active_str = datetime.fromisoformat(raw_last_active).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        last_active_str = raw_last_active

                # Format created_at for start_time - handle missing created_at from paginated endpoint
                start_time_str = 'Not Available'  # Since paginated endpoint doesn't include created_at
                raw_created_at = user.get('created_at')
                if raw_created_at:
                    try:
                        start_time_str = datetime.fromisoformat(raw_created_at).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        start_time_str = raw_created_at

                table_rows.append({
                    'user_id': user.get('id'),
                    'name': user.get('display_name', 'N/A'),
                    'logged': 'Yes' if user.get('is_active', False) else 'No',
                    'message_count': user.get('message_count', 0),  # Use message_count instead of total_messages
                    'start_time': start_time_str,
                    'last_activity': last_active_str
                })

        # Update table regardless of whether we have data or not
        self.users_table.rows = table_rows

        new_pagination = dict(pagination_in)
        new_pagination['rowsNumber'] = total_users
        self.users_table.pagination = new_pagination
        self.pagination_state.update(new_pagination)

        if self.client and self.client.has_socket_connection:
            js_command = f"Quasar.plugins.Notify.create({{ message: 'Loaded page {page} ({len(table_rows)} of {total_users} users)', type: 'positive', position: 'bottom-right', timeout: 1500 }})"
            self.client.run_javascript(js_command)

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

    async def _trigger_batch_analysis(self, summaries_data_list: list | None):
        """Helper to trigger batch analysis generation for a list of summaries."""
        if not self.summaries_container:
            print("Summaries container not available for batch analysis status.")
            return

        if not summaries_data_list or not isinstance(summaries_data_list, list) or not summaries_data_list:
            print("No summaries data provided or data is empty, skipping batch analysis trigger.")
            return

        summary_ids = [s.get('id') for s in summaries_data_list if isinstance(s, dict) and s.get('id')]

        print(f"DEBUG: Extracted summary IDs: {summary_ids}")

        if not summary_ids:
            print("No valid summary IDs found in the provided data to trigger batch analysis.")
            return

        self.summaries_container.clear()
        with self.summaries_container:
            ui.label(f'Initiating analysis generation for {len(summary_ids)} summaries...').classes('text-h6 mb-2 text-center')
            ui.spinner('dots', size='lg').classes('text-primary self-center my-4')
        
        analysis_payload = {'summary_ids': summary_ids}
        print(f"Calling /analysis/batch-generate with {len(summary_ids)} summary IDs (first 5: {summary_ids[:5]}...).")
        
        analysis_initiation_result = await api_request(
            'POST', 
            '/analysis/batch-generate', 
            client=self.client, 
            json_data=analysis_payload
        )

        if analysis_initiation_result:
            if self.client and self.client.has_socket_connection:
                message = (
                    f"Analysis generation process initiated for {len(summary_ids)} summaries. "
                    "Visualizations in 'Macro Analysis' tab should reflect this data shortly."
                )
                js_command = f"Quasar.plugins.Notify.create({{ message: '{message}', type: 'positive', timeout: 5000, position: 'bottom' }})"
                self.client.run_javascript(js_command)
            print(f"Analysis generation successfully initiated for {len(summary_ids)} summaries.")
        else:
            # api_request likely showed its own error for HTTP/network issues
            if self.client and self.client.has_socket_connection:
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Failed to initiate batch analysis for summaries. Visualizations may use older data.', type: 'warning', timeout: 5000, position: 'bottom' }})"
                self.client.run_javascript(js_command)
            print("Failed to initiate batch analysis for summaries.")

        print("Waiting 3 seconds for analysis processing to begin...")
        await asyncio.sleep(3) 
        print("Wait finished. Proceeding to display summaries list if available.")
        # The calling function will clear self.summaries_container again before drawing the final table.

    async def generate_macro_analysis(self, max_summaries_input, tabs_ref):
        """Handles the macro analysis generation."""
        if not self.analysis_container: return
        
        tabs_ref.set_value("Macro Analysis")
        
        limit_val = int(max_summaries_input.value) # Renamed to avoid conflict with dict key
        top_n_questions = 15
        self.analysis_container.clear()

        with self.analysis_container:
            ui.label('Fetching and visualizing analysis data...').classes('text-h6 mb-2')
            ui.spinner('dots', size='lg').classes('text-primary')
        
        # Prepare the request body for visualization endpoints
        visualization_request_body = {
            "limit": limit_val # Add limit to the JSON body
        }
        if self.date_selectors:
            start_date, start_hour, end_date, end_hour = self.date_selectors
            visualization_request_body.update({
                "start_date": str(start_date.value),
                "start_hour": int(start_hour.value),
                "end_date": str(end_date.value),
                "end_hour": int(end_hour.value),
            })
            
        if self.user_selector and self.user_selector.value and 'all' not in self.user_selector.value:
            user_ids = [int(uid) for uid in self.user_selector.value if uid.isdigit()]
            if user_ids:
                visualization_request_body['user_ids'] = user_ids

        print(f"\n=== FETCHING VISUALIZATION DATA ===")
        print(f"Request Body (for JSON): {visualization_request_body}")
        # top_n will be the only query param, for questions-table only
        print(f"Query Params (for questions-table only): top_n={top_n_questions}") 
        
        # API calls using new endpoints and parameter structure
        # Limit is now in the body, top_n is a query param for questions_table
        results = await asyncio.gather(
            api_request('POST', '/visualizations/topic-heatmap', 
                        client=self.client, 
                        json_data=visualization_request_body, 
                        params=None), # No query params
            api_request('POST', '/visualizations/satisfaction-chart', 
                        client=self.client, 
                        json_data=visualization_request_body, 
                        params=None), # No query params
            api_request('POST', '/visualizations/conversation-types-chart',
                        client=self.client, 
                        json_data=visualization_request_body, 
                        params=None), # No query params
            api_request('POST', '/visualizations/questions-table', 
                        client=self.client, 
                        json_data=visualization_request_body, 
                        params={'top_n': top_n_questions}), # Only top_n as query param
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
                        ui.label(f'Max Conversations (Limit in body): {limit_val}').classes('text-subtitle1')
                        if "start_date" in visualization_request_body: # Check if date selectors were used
                            sd = visualization_request_body["start_date"]
                            sh = visualization_request_body["start_hour"]
                            ed = visualization_request_body["end_date"]
                            eh = visualization_request_body["end_hour"]
                            ui.label(f'Date Range: {sd} {sh:02d}:00 to {ed} {eh:02d}:59').classes('text-subtitle1')
                        else:
                            ui.label('Date Range: Not applied (all time)').classes('text-subtitle1')
                            
                        if self.user_selector and self.user_selector.value:
                            selected_users = ", ".join(self.user_selector.value)
                            ui.label(f'Users: {selected_users}').classes('text-subtitle1')
                        else:
                            ui.label(f'Users: All').classes('text-subtitle1')

            # tabs_ref.set_value("Macro Analysis") # Redundant here, already set

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
            ui.label('Generating and fetching summaries...').classes('text-h6 mb-2 text-center')
            ui.spinner('dots', size='lg').classes('text-primary self-center my-4')
        
        # Extract date range and user selection
        start_date, start_hour, end_date, end_hour = self.date_selectors
        user_ids_selection = self.user_selector.value if self.user_selector.value else ['all']
        
        # Create the request body - Make sure all fields are properly typed
        request_data = {
            "start_date": str(start_date.value),  # Ensure it's a string
            "start_hour": int(start_hour.value),
            "end_date": str(end_date.value),      # Ensure it's a string
            "end_hour": int(end_hour.value),
            "limit": limit
        }
        
        # Only include user_ids if specific users are selected (not 'all')
        if 'all' not in user_ids_selection:
            request_data["user_ids"] = [int(uid) for uid in user_ids_selection if uid.isdigit()]
        
        print(f"Requesting summary generation with data: {request_data}")
        generate_result = await api_request('POST', '/summaries/generate-batch', client=self.client, json_data=request_data)
        
        summaries_data = None # Initialize
        if generate_result:
            if self.client and self.client.has_socket_connection:
                count_msg = f"{len(generate_result)} summaries" if isinstance(generate_result, list) and generate_result else "summaries"
                js_command = f"Quasar.plugins.Notify.create({{ message: 'Summary generation process completed for {count_msg}. Now fetching...', type: 'info', timeout: 3000, position: 'bottom' }})"
                self.client.run_javascript(js_command)
            
            print(f"Fetching summaries after generation, using request data: {request_data}")
            # Fetch the generated summaries (or all matching if generate_result isn't specific)
            summaries_data = await api_request('POST', '/summaries/by-date-range', client=self.client, json_data=request_data)
        else:
            if self.client and self.client.has_socket_connection:
                js_command = "Quasar.plugins.Notify.create({ message: 'Failed to trigger summary generation. No new summaries to fetch or analyze.', type: 'negative', timeout: 3000, position: 'bottom' })"
                self.client.run_javascript(js_command)
        
        # Trigger batch analysis if summaries were fetched successfully and are not empty
        if summaries_data and isinstance(summaries_data, list) and summaries_data:
            await self._trigger_batch_analysis(summaries_data)
        elif not summaries_data and generate_result: # Generation was attempted but fetching failed or returned empty
            self.summaries_container.clear() 
            with self.summaries_container:
                 ui.label('Summary generation was triggered, but failed to fetch summaries or no summaries were found.').classes('text-h6 mt-4 text-center text-negative')
        elif not generate_result: # Generation itself failed
             self.summaries_container.clear() 
             with self.summaries_container:
                  ui.label('Summary generation failed. Cannot proceed to fetch or analyze.').classes('text-h6 mt-4 text-center text-negative')


        # This clear is crucial to remove any messages from _trigger_batch_analysis
        # or the initial "Generating and fetching..." message if _trigger_batch_analysis was skipped or failed.
        self.summaries_container.clear() 
        
        with self.summaries_container:
            ui.label('Conversation Summaries').classes('text-h5 mb-4')
            
            with ui.card().classes('w-full mb-4 p-4'):
                ui.label('Query Parameters').classes('text-h6 mb-2')
                with ui.row().classes('w-full justify-between'):
                    with ui.column().classes('mr-4'):
                        ui.label(f'Date Range: {start_date.value} {int(start_hour.value)}:00 to {end_date.value} {int(end_hour.value)}:59').classes('text-subtitle1')
                        ui.label(f'Users: {", ".join(user_ids_selection)}').classes('text-subtitle1')
                        ui.label(f'Max Summaries: {limit}').classes('text-subtitle1')
                    
                    with ui.row().classes('items-center'): # Group buttons
                        ui.button('Re-Generate & Show', icon='refresh', 
                                on_click=lambda: asyncio.create_task(self.generate_summaries(max_summaries_input, tabs_ref))).props('color=secondary flat size="sm"')
                        ui.button('Show Existing Only', icon='visibility',
                                  on_click=lambda: asyncio.create_task(self.show_summaries(max_summaries_input, tabs_ref))).props('color=primary flat size="sm" q-ml-sm')
            
            if summaries_data and isinstance(summaries_data, list) and summaries_data:
                columns = [
                    {'name': 'summary_id', 'field': 'summary_id', 'label': 'ID', 'align': 'left'},
                    {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left'},
                    {'name': 'conversation_id', 'field': 'conversation_id', 'label': 'Conversation ID', 'align': 'left'},
                    {'name': 'created_at', 'field': 'created_at', 'label': 'Created At', 'align': 'left'},
                    {'name': 'logged', 'field': 'logged', 'label': 'Logged User', 'align': 'center'},
                    {'name': 'summary', 'field': 'summary', 'label': 'Summary (Preview)', 'align': 'left'},
                ]
                
                rows = []
                for summary_item in summaries_data:
                    if not isinstance(summary_item, dict): continue 
                    created_at_raw = summary_item.get('created_at', '')
                    try:
                        dt = datetime.fromisoformat(created_at_raw.replace('Z', '+00:00')) if created_at_raw else None
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else 'N/A'
                    except (ValueError, AttributeError):
                        formatted_time = created_at_raw or 'N/A'
                    
                    logged = 'Yes' if summary_item.get('logged') else 'No'
                    full_summary_text = summary_item.get('summary', '')
                    
                    rows.append({
                        'summary_id': summary_item.get('id', 'N/A'),
                        'user_id': summary_item.get('user_id', 'N/A'),
                        'conversation_id': summary_item.get('conversation_id', 'N/A'),
                        'created_at': formatted_time,
                        'logged': logged,
                        'summary': full_summary_text[:100] + '...' if len(full_summary_text) > 100 else full_summary_text,
                        'original_summary': full_summary_text
                    })
                
                ui.label(f'Displaying {len(rows)} summaries.').classes('text-h6 mt-4 mb-2')
                self.show_summaries_table(columns, rows) # Reuses the table rendering method
                
                if self.client and self.client.has_socket_connection:
                    js_command = f"Quasar.plugins.Notify.create({{ message: 'Successfully loaded and displayed {len(rows)} summaries.', type: 'positive', timeout: 3000, position: 'bottom' }})"
                    self.client.run_javascript(js_command)
            elif summaries_data and isinstance(summaries_data, list) and not summaries_data:
                 ui.label('No summaries found for the specified criteria after generation attempt.').classes('text-h6 mt-4 text-center')
            # If summaries_data is None, specific error messages were shown before this block.
                    
    async def show_summaries(self, max_summaries_input, tabs_ref):
        """Fetches and displays summaries without generating new ones."""
        if not self.summaries_container: return
        
        tabs_ref.set_value("Conversation Summaries")
        
        limit = int(max_summaries_input.value)
        self.summaries_container.clear()

        with self.summaries_container:
            ui.label('Fetching existing summaries...').classes('text-h6 mb-2 text-center')
            ui.spinner('dots', size='lg').classes('text-primary self-center my-4')
        
        # Extract date range and user selection
        start_date, start_hour, end_date, end_hour = self.date_selectors
        user_ids_selection = self.user_selector.value if self.user_selector.value else ['all']
        
        # Create the request body
        request_data = {
            "start_date": str(start_date.value),
            "start_hour": int(start_hour.value),
            "end_date": str(end_date.value),
            "end_hour": int(end_hour.value),
            "limit": limit
        }
        
        if 'all' not in user_ids_selection:
            request_data["user_ids"] = [int(uid) for uid in user_ids_selection if uid.isdigit()]
        
        print(f"Fetching existing summaries with request data: {request_data}")
        summaries_data = await api_request('POST', '/summaries/by-date-range', client=self.client, json_data=request_data)
        
        # This clear is crucial to remove the initial "Fetching existing..." message 
        # or handle cases where fetching might have failed before this point.
        self.summaries_container.clear()
        
        with self.summaries_container:
            ui.label('Conversation Summaries').classes('text-h5 mb-4')
            
            with ui.card().classes('w-full mb-4 p-4'):
                ui.label('Query Parameters').classes('text-h6 mb-2')
                with ui.row().classes('w-full justify-between'):
                    with ui.column().classes('mr-4'):
                        ui.label(f'Date Range: {start_date.value} {int(start_hour.value)}:00 to {end_date.value} {int(end_hour.value)}:59').classes('text-subtitle1')
                        ui.label(f'Users: {", ".join(user_ids_selection)}').classes('text-subtitle1')
                        ui.label(f'Max Summaries: {limit}').classes('text-subtitle1')
                    
                    with ui.row().classes('items-center'):
                        ui.button('Refresh View', icon='refresh', 
                                on_click=lambda: asyncio.create_task(self.show_summaries(max_summaries_input, tabs_ref))).props('color=primary flat size="sm"')
                        ui.button('Generate & Show New', icon='summarize',
                                  on_click=lambda: asyncio.create_task(self.generate_summaries(max_summaries_input, tabs_ref))).props('color=secondary flat size="sm" q-ml-sm')
            
            if summaries_data and isinstance(summaries_data, list) and summaries_data:
                # Create table columns
                columns = [
                    {'name': 'summary_id', 'field': 'summary_id', 'label': 'ID', 'align': 'left'},
                    {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left'},
                    {'name': 'conversation_id', 'field': 'conversation_id', 'label': 'Conversation ID', 'align': 'left'},
                    {'name': 'created_at', 'field': 'created_at', 'label': 'Created At', 'align': 'left'},
                    {'name': 'logged', 'field': 'logged', 'label': 'Logged User', 'align': 'center'},
                    {'name': 'summary', 'field': 'summary', 'label': 'Summary (Preview)', 'align': 'left'},
                ]
                
                # Format the data for the table
                rows = []
                for summary_item in summaries_data:
                    if not isinstance(summary_item, dict): continue
                    created_at_raw = summary_item.get('created_at', '')
                    try:
                        dt = datetime.fromisoformat(created_at_raw.replace('Z', '+00:00')) if created_at_raw else None
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else 'N/A'
                    except (ValueError, AttributeError):
                        formatted_time = created_at_raw or 'N/A'
                    
                    logged = 'Yes' if summary_item.get('logged') else 'No'
                    full_summary_text = summary_item.get('summary', '')
                    
                    rows.append({
                        'summary_id': summary_item.get('id', 'N/A'),
                        'user_id': summary_item.get('user_id', 'N/A'),
                        'conversation_id': summary_item.get('conversation_id', 'N/A'),
                        'created_at': formatted_time,
                        'logged': logged,
                        'summary': full_summary_text[:100] + '...' if len(full_summary_text) > 100 else full_summary_text,
                        'original_summary': full_summary_text
                    })
                
                ui.label(f'Displaying {len(rows)} existing summaries.').classes('text-h6 mt-4 mb-2')
                self.show_summaries_table(columns, rows)
                
                if self.client and self.client.has_socket_connection:
                    js_command = f"Quasar.plugins.Notify.create({{ message: 'Successfully loaded and displayed {len(rows)} existing summaries.', type: 'positive', timeout: 3000, position: 'bottom' }})"
                    self.client.run_javascript(js_command)
            elif summaries_data and isinstance(summaries_data, list) and not summaries_data: # Empty list from API
                ui.label('No existing summaries found for the specified criteria.').classes('text-h6 mt-4 text-center')
            else: # summaries_data is None (fetch failed)
                 ui.label('Failed to fetch existing summaries. Please check API connection or logs.').classes('text-h6 mt-4 text-center text-negative')

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
                         {'name': 'name', 'field': 'name', 'label': 'Name', 'align': 'left', 'sortable': False},
                         {'name': 'logged', 'field': 'logged', 'label': 'Logged', 'align': 'center', 'sortable': True}, # Use is_active for sorting
                         {'name': 'message_count', 'field': 'message_count', 'label': 'Messages', 'align': 'center', 'sortable': True}, # Enable sorting
                         {'name': 'start_time', 'field': 'start_time', 'label': 'Started', 'align': 'center', 'sortable': False}, # Or True if API supports
                         {'name': 'last_activity', 'field': 'last_activity', 'label': 'Last Activity', 'align': 'center', 'sortable': True} # Use last_activity for sorting
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

        # Add CSS/JS for admin functionality and modal styling
        ui.add_head_html(r'''
        <style> 
        .q-table tbody tr { cursor: pointer; }
        .q-table tbody tr:hover { background-color: #f5f5f5; }
        
        /* Modal and conversation styling */
        .conversation-message {
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        .conversation-scroll {
            scrollbar-width: thin;
        }
        .conversation-scroll::-webkit-scrollbar {
            width: 6px;
        }
        .conversation-scroll::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 3px;
        }
        .conversation-scroll::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }
        .conversation-scroll::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8;
        }
        
        /* Loading animations */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .fade-in {
            animation: fadeIn 0.3s ease-in;
        }
        </style>
        <script>
        // Global conversation management
        window.conversationRequests = window.conversationRequests || {};
        
        // Utility function to escape HTML
        window.escapeHtml = function(text) {
            var map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, function(m) { return map[m]; });
        };
        </script>
        ''')

@ui.page('/admin')
# @auth_required #TODO: turn off after development
def page_admin():
    """Admin page handler - creates a new manager instance for each session."""
    # Create a new manager instance for this session
    admin_manager = AdminPageManager()
    # Build the UI
    admin_manager.build_ui()
    
# --- No ui.run() ---