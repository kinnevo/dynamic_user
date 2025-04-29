from nicegui import ui, app
import uuid
from utils.message_router import MessageRouter
from utils.layouts import create_navigation_menu_2
from utils.database import PostgresAdapter
from utils.filc_agent_client import FilcAgentClient  # Changed from LangflowClient

# Initialize components
message_router = MessageRouter()
db_adapter = PostgresAdapter()
# Use the FilcAgentClient instead of LangflowClient
filc_client = FilcAgentClient()

@ui.page('/chat')
async def chat_page():
    """Chat interface for FILC Agent interaction"""
    create_navigation_menu_2()
    
    with ui.header().classes('items-center justify-between'):
        # Left side with title
        with ui.row().classes('items-center gap-2'):
            ui.label('Chat with FILC Agent').classes('text-h3')
        
        # Right side with status indicator and check button
        with ui.row().classes('items-center gap-2'):
            # Create the status indicator as refreshable component
            @ui.refreshable
            def update_status_indicator():
                # Use the connection status from filc_client
                connection_status = filc_client.connection_status if hasattr(filc_client, 'connection_status') else 'unknown'
                
                status_color = {
                    'connected': 'green',
                    'timeout': 'red',
                    'unreachable': 'red',
                    'error': 'red',
                    'unknown': 'yellow'
                }.get(connection_status, 'yellow')
                
                status_text = {
                    'connected': 'Connected to FILC Agent',
                    'timeout': 'Connection Timeout - Server not responding',
                    'unreachable': 'Server Unreachable - Check network or server status',
                    'error': 'Connection Error - See logs for details',
                    'unknown': 'Status Unknown - Click "Check Connection"'
                }.get(connection_status, 'Unknown Status')
                
                with ui.tooltip(status_text):
                    ui.icon('circle', color=status_color).classes('text-sm')
            
            # Display the status indicator
            status_indicator = update_status_indicator()
            
            # Function to check connection and update indicator
            async def check_and_update_connection():
                ui.notify('Checking FILC Agent connection...', timeout=2000)
                is_connected, message = await filc_client.check_connection()
                # Store the connection status for the indicator
                filc_client.connection_status = 'connected' if is_connected else 'error'
                
                refresh_task = status_indicator.refresh()
                if refresh_task is not None:
                    await refresh_task
                
                if is_connected:
                    ui.notify('Connected to FILC Agent API', type='positive')
                else:
                    ui.notify(f'Connection issue: {message}', type='negative', timeout=8000)
            
            # Add a button to check connection
            ui.button('Check Connection', on_click=check_and_update_connection).classes('text-xs bg-blue-100')
    
    # Chat messages container
    messages_container = ui.column().classes('w-full h-[60vh] overflow-y-auto p-4 gap-2')
    
    # Add a spacer at the bottom to ensure content is visible
    with messages_container:
        ui.space().classes('h-8')  # Add some space at the bottom
    
    @ui.refreshable
    async def display_messages():
        """Display chat messages from the database"""
        messages_container.clear()
        
        session_id = app.storage.browser.get('session_id', None)
        if not session_id:
            return
        
        # Get recent messages
        messages = db_adapter.get_recent_messages(session_id, limit=50)
        
        for message in messages:
            if message['role'] == 'user':
                with ui.element('div').classes('self-end bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                    ui.markdown(message['content'])
            else:
                with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                    ui.markdown(message['content'])
        
        # Add spacer at the bottom after messages
        with messages_container:
            ui.space().classes('h-8')
        
        # Scroll to bottom after adding messages
        try:
            await ui.run_javascript('''
                const container = document.querySelector(".overflow-y-auto");
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            ''', timeout=5.0)
        except Exception as e:
            print(f"Error scrolling: {e}")  # Log the error but don't break the function
    
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
                
                # Get session info
                session_id = app.storage.browser.get('session_id', None)
                user_id = app.storage.browser.get('user_id', None)
                
                if not session_id:
                    # Create a new session ID if missing
                    session_id = str(uuid.uuid4())
                    app.storage.browser['session_id'] = session_id
                
                if not user_id:
                    # Create a new user ID if missing
                    user_id = db_adapter.create_user(session_id)
                    app.storage.browser['user_id'] = user_id
                    ui.notify('Session initialized', type='positive')
                
                message = message_input.value
                message_input.value = ''
                
                # Show loading spinner
                spinner.visible = True
                
                # First scroll after sending message
                display_messages.refresh()
                try:
                    await ui.run_javascript('''
                        const container = document.querySelector(".overflow-y-auto");
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    ''', timeout=5.0)
                except Exception as e:
                    print(f"Error scrolling: {e}")  # Log the error but don't break the function
                
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
                
                # Final scroll after displaying response
                display_messages.refresh()
                try:
                    await ui.run_javascript('''
                        const container = document.querySelector(".overflow-y-auto");
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    ''', timeout=5.0)
                except Exception as e:
                    print(f"Error scrolling: {e}")  # Log the error but don't break the function
            
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