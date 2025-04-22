from nicegui import ui, app
import uuid
from utils.message_router import MessageRouter
from utils.layouts import create_navigation_menu_2
from utils.database import PostgresAdapter
from utils.langflow_client import LangflowClient
from utils.state import set_post_logout_session

# Initialize components
message_router = MessageRouter()
db_adapter = PostgresAdapter()
# Use the existing singleton instance
langflow_client = LangflowClient()

@ui.page('/chat')
async def chat_page():
    """Chat interface for Langflow interaction"""
    create_navigation_menu_2()
    
    with ui.header().classes('items-center justify-between'):
        # Left side with title
        with ui.row().classes('items-center gap-2'):
            ui.label('Chat with Langflow').classes('text-h3')
        
        # Right side with status indicator and check button
        with ui.row().classes('items-center gap-2'):
            # Create the status indicator as refreshable component
            @ui.refreshable
            def update_status_indicator():
                status_color = {
                    'connected': 'green',
                    'timeout': 'red',
                    'unreachable': 'red',
                    'error': 'red',
                    'unknown': 'yellow'
                }.get(langflow_client.connection_status, 'yellow')
                
                status_text = {
                    'connected': 'Connected to Langflow',
                    'timeout': 'Connection Timeout - Server not responding',
                    'unreachable': 'Server Unreachable - Check network or server status',
                    'error': 'Connection Error - See logs for details',
                    'unknown': 'Status Unknown - Click "Check Connection"'
                }.get(langflow_client.connection_status, 'Unknown Status')
                
                with ui.tooltip(status_text):
                    ui.icon('circle', color=status_color).classes('text-sm')
            
            # Display the status indicator
            status_indicator = update_status_indicator()
            
            # Function to check connection and update indicator
            async def check_and_update_connection():
                ui.notify('Checking Langflow connection...', timeout=2000)
                is_connected, message = langflow_client.check_connection()
                refresh_task = status_indicator.refresh()
                if refresh_task is not None:
                    await refresh_task
                
                if is_connected:
                    ui.notify('Connected to Langflow API', type='positive')
                else:
                    ui.notify(f'Connection issue: {message}', type='negative', timeout=8000)
            
            # Add a button to check connection
            ui.button('Check Connection', on_click=check_and_update_connection).classes('text-xs bg-blue-100')
    
    # Chat messages container
    messages_container = ui.column().classes('w-full h-[60vh] overflow-y-auto p-4 gap-2')
    
    @ui.refreshable
    async def display_messages():
        """Display chat messages from the database"""
        messages_container.clear()
        
        # Try to get session from browser storage first
        session_id = app.storage.browser.get('session_id', None)
        
        # If no session in browser storage, try to retrieve from localStorage
        if not session_id:
            try:
                # Direct localStorage check with higher timeout
                storage_data = await ui.run_javascript("""
                    const sessionId = localStorage.getItem('persistent_session_id');
                    const userId = localStorage.getItem('persistent_user_id');
                    const loggedOut = localStorage.getItem('logged_out');
                    
                    // Check if user has logged out
                    if (loggedOut === 'true') {
                        // Clear the logged_out flag
                        localStorage.removeItem('logged_out');
                        return {
                            exists: false,
                            logged_out: true
                        };
                    }
                    
                    if (sessionId && userId) {
                        return {
                            exists: true,
                            session_id: sessionId,
                            user_id: userId
                        };
                    }
                    return { exists: false };
                """, timeout=5)
                
                # If we have localStorage data, use it
                if storage_data and storage_data.get('exists', False):
                    session_id = storage_data.get('session_id')
                    # Update app storage with localStorage values - with error handling
                    try:
                        app.storage.browser['session_id'] = session_id
                        app.storage.browser['user_id'] = storage_data.get('user_id')
                    except TypeError:
                        # If browser storage is locked, just use the local variable
                        print("Browser storage already locked in display_messages")
                        # session_id is already set above for local use
                    print(f"Chat: Restored session from localStorage: {session_id}")
                elif storage_data and storage_data.get('logged_out', False):
                    # If the user has logged out, we should not show any messages
                    print("User has logged out, not displaying old messages")
                    with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                        ui.markdown("*You have started a new session. Previous messages won't be displayed.*")
                    return
            except Exception as e:
                print(f"Error checking localStorage in chat: {e}")
        
        # If still no session_id, can't display messages
        if not session_id:
            with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                ui.markdown("*No active session. Please start a conversation.*")
            return
        
        # Get recent messages
        messages = db_adapter.get_recent_messages(session_id, limit=50)
        
        if not messages:
            with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                ui.markdown("*No messages yet. Start a conversation!*")
            return
        
        for message in messages:
            if message['role'] == 'user':
                with ui.element('div').classes('self-end bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                    ui.markdown(message['content'])
            else:
                with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                    ui.markdown(message['content'])
    
    # Spinner for loading state
    spinner = ui.spinner('dots', size='lg').classes('text-primary')
    spinner.visible = False
    
    # Message input area
    with ui.footer().classes('bg-white p-4'):
        with ui.row().classes('w-full items-center gap-2'):
            message_input = ui.input(placeholder='Type your message...').classes('w-full')
            
            async def send_message():
                if not message_input.value:
                    return
                
                # Get session info - first from browser storage, then from localStorage
                session_id = app.storage.browser.get('session_id', None)
                user_id = app.storage.browser.get('user_id', None)
                
                # Only try to get or create session if we don't have one already
                if not session_id or not user_id:
                    try:
                        # Direct localStorage check with higher timeout
                        storage_data = await ui.run_javascript("""
                            const sessionId = localStorage.getItem('persistent_session_id');
                            const userId = localStorage.getItem('persistent_user_id');
                            
                            if (sessionId && userId) {
                                return {
                                    exists: true,
                                    session_id: sessionId,
                                    user_id: userId
                                };
                            }
                            return { exists: false };
                        """, timeout=5)
                        
                        # Check if user has logged out first
                        if storage_data and storage_data.get('logged_out', False):
                            print("User has logged out, creating new session in chat")
                            # Create new session after logout
                            session_id = str(uuid.uuid4())
                            user_id = db_adapter.create_user(session_id)
                            
                            # Update the global post-logout session tracker
                            set_post_logout_session(session_id)
                            print(f"Chat: Setting post-logout session to: {session_id}")
                            
                            # Update app storage with error handling
                            try:
                                app.storage.browser['session_id'] = session_id
                                app.storage.browser['user_id'] = user_id
                            except TypeError:
                                print("Browser storage already locked when creating session after logout")
                                # Still have local variables for this request
                            
                            # Store in localStorage
                            ui.run_javascript(f"""
                                localStorage.setItem('persistent_session_id', '{session_id}');
                                localStorage.setItem('persistent_user_id', '{user_id}');
                                console.log('Created new post-logout session:', {{ session_id: '{session_id}', user_id: '{user_id}' }});
                            """)
                            
                            ui.notify('Started new chat session', type='positive')
                        # If we have regular localStorage data, use it
                        elif storage_data and storage_data.get('exists', False):
                            print(f"Chat: Restoring existing session: {storage_data.get('session_id')}")
                            # Restore from localStorage
                            session_id = storage_data.get('session_id')
                            user_id = storage_data.get('user_id')
                            
                            # Update app storage with localStorage values - with error handling
                            try:
                                app.storage.browser['session_id'] = session_id
                                app.storage.browser['user_id'] = user_id
                            except TypeError:
                                # If browser storage is locked, we can't update it but can still use the session values
                                print("Browser storage already locked in chat, using session values in memory only")
                                pass
                        else:
                            # No session in localStorage - genuinely new session required
                            print("Chat: Creating new session and user (first time visitor)")
                            session_id = str(uuid.uuid4())
                            user_id = db_adapter.create_user(session_id)
                            
                            # Update the global post-logout session
                            set_post_logout_session(session_id)
                            print(f"Chat: Setting post-logout session to new first-time session: {session_id}")
                            
                            # Update browser storage with error handling
                            try:
                                app.storage.browser['session_id'] = session_id
                                app.storage.browser['user_id'] = user_id
                            except TypeError:
                                # If browser storage is locked, we can't update it
                                print("Browser storage already locked when creating new session in chat")
                                # We can still use the values locally
                            
                            # Store in localStorage for persistence - don't await (fire and forget)
                            ui.run_javascript(f"""
                                localStorage.setItem('persistent_session_id', '{session_id}');
                                localStorage.setItem('persistent_user_id', '{user_id}');
                                console.log('Chat created new session:', {{ session_id: '{session_id}', user_id: '{user_id}' }});
                            """)
                            
                            ui.notify('New session initialized', type='positive')
                    except Exception as e:
                        # If there's any error with JavaScript, create a new session
                        print(f"Error checking localStorage in chat send_message: {e}")
                        session_id = str(uuid.uuid4())
                        user_id = db_adapter.create_user(session_id)
                        
                        # Update the global post-logout session
                        set_post_logout_session(session_id)
                        print(f"Chat: Setting post-logout session to new fallback session: {session_id}")
                        
                        # Update browser storage with error handling  
                        try:
                            app.storage.browser['session_id'] = session_id
                            app.storage.browser['user_id'] = user_id
                        except TypeError:
                            # If browser storage is locked, we can't update it
                            print("Browser storage already locked when handling errors in chat")
                            # Session and user_id variables are still available locally
                        
                        # Try to store in localStorage - don't await
                        ui.run_javascript(f"""
                            localStorage.setItem('persistent_session_id', '{session_id}');
                            localStorage.setItem('persistent_user_id', '{user_id}');
                        """)
                        
                        ui.notify('New session created', type='positive')
                
                message = message_input.value
                message_input.value = ''
                
                # Show loading spinner
                spinner.visible = True
                
                try:
                    # Process message
                    response = await message_router.process_user_message(
                        message=message,
                        session_id=session_id,
                        user_id=user_id
                    )
                except Exception as e:
                    ui.notify(f'Error processing message: {str(e)}', type='negative')
                    spinner.visible = False
                    return
                
                # Hide spinner
                spinner.visible = False
                
                # Handle errors - only display significant errors, not connection warnings
                if 'error' in response and 'content' not in response:
                    error_message = response['error']
                    
                    # Only show UI errors for significant issues that prevent message processing
                    # Skip showing connection warnings if we got a proper response
                    is_connection_warning = ('connection' in error_message.lower() or 'timeout' in error_message.lower())
                    
                    if not is_connection_warning:
                        # Display a notification with a shorter version of the error
                        short_error = error_message.split('\n')[0] if '\n' in error_message else error_message
                        ui.notify(f"Error: {short_error}", type='negative', timeout=10000)
                        
                        # For severe errors that prevent message delivery
                        with messages_container:
                            with ui.element('div').classes('self-start bg-red-100 p-3 rounded-lg max-w-[80%] border-l-4 border-red-500'):
                                ui.markdown("**⚠️ Error**\n\nThere was a problem processing your request. The message was saved but the AI response could not be generated.")
                
                # Refresh messages display
                # Make sure display_messages.refresh() returns a value that can be awaited
                refresh_task = display_messages.refresh()
                if refresh_task is not None:
                    await refresh_task
            
            # Allow sending message with Enter key
            message_input.on('keydown.enter', send_message)
            
            # Send button
            ui.button('Send', on_click=send_message).classes('bg-blue-500 text-white')
    
    # Button to clear chat history
    with ui.row().classes('w-full justify-center mt-4'):
        async def clear_chat():
            # This would need a method in the adapter to clear messages
            session_id = app.storage.browser.get('session_id', None)
            if session_id:
                # For now, we'll just refresh the display
                refresh_task = display_messages.refresh()
                if refresh_task is not None:
                    await refresh_task
                ui.notify('Chat cleared', type='positive')
        
        ui.button('Clear Chat', on_click=clear_chat).classes('bg-red-500 text-white')
    
    # Initialize display
    refresh_task = display_messages()
    if refresh_task is not None:
        await refresh_task