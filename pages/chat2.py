from nicegui import ui, app
import uuid
from utils.message_router import MessageRouter
from utils.layouts import create_navigation_menu_2
from utils.database import PostgresAdapter
from utils.filc_agent_client import FilcAgentClient

# Initialize components
message_router = MessageRouter()
db_adapter = PostgresAdapter()
filc_client = FilcAgentClient()

@ui.page('/chat2')
async def chat_page():
    """Chat interface for FILC Agent interaction with reliable scrolling"""
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

    # Spinner for loading state - positioned absolute so it can be outside any container
    spinner = ui.spinner('dots', size='lg').classes('text-primary absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50')
    spinner.visible = False
    
    # Text display area using a direct html textarea for maximum compatibility
    messages_textarea = ui.html("""
        <textarea id="chat-messages" readonly 
            style="width: 100%; height: 73vh; min-height: 300px; 
                  resize: none; padding: 10px; border: 1px solid #e0e0e0; 
                  border-radius: 4px; font-family: inherit; overflow-y: auto;">
            Welcome to FILC Agent Chat!
            Type a message below to begin.
        </textarea>
    """).classes('w-full')

    # Define the send_message function
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
        
        # Get message and clear input
        message = message_input.value
        message_input.value = ''
        
        # Update the textarea with JavaScript for more reliable behavior
        try:
            await ui.run_javascript('''
                const textarea = document.getElementById('chat-messages');
                if (textarea) {
                    textarea.value += '\\nYou: ' + ''' + repr(message) + ''';
                    textarea.scrollTop = textarea.scrollHeight;
                }
            ''', timeout=5.0)
        except Exception as e:
            print(f"Error updating chat: {e}")
        
        # Show loading spinner
        spinner.visible = True
        
        try:
            # Process message
            response = await message_router.process_user_message(
                message=message,
                session_id=session_id,
                user_id=user_id
            )
            
            # Add response to display using JavaScript
            if 'content' in response:
                try:
                    await ui.run_javascript('''
                        const textarea = document.getElementById('chat-messages');
                        if (textarea) {
                            textarea.value += '\\n\\nFILC Agent: ' + ''' + repr(response['content']) + ''' + '\\n';
                            textarea.scrollTop = textarea.scrollHeight;
                        }
                    ''', timeout=5.0)
                except Exception as e:
                    print(f"Error adding response: {e}")
        except Exception as e:
            ui.notify(f'Error processing message: {str(e)}', type='negative')
            
            # Add error message to display using JavaScript
            try:
                await ui.run_javascript('''
                    const textarea = document.getElementById('chat-messages');
                    if (textarea) {
                        textarea.value += '\\n\\n⚠️ Error: Could not get response\\n';
                        textarea.scrollTop = textarea.scrollHeight;
                    }
                ''', timeout=5.0)
            except Exception as e:
                print(f"Error adding error message: {e}")
        finally:
            # Hide spinner
            spinner.visible = False
    
    # Message input area - direct child of the page content
    with ui.footer().classes('bg-white p-4'):
        with ui.row().classes('w-full items-center gap-2'):
            message_input = ui.input(placeholder='Type your message...').classes('w-full')
            
            # Allow sending message with Enter key
            message_input.on('keydown.enter', send_message)
            
            # Send button
            ui.button('Send', on_click=send_message).classes('bg-blue-500 text-white') 