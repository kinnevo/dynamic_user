from nicegui import ui, app
import uuid
from utils.message_router import MessageRouter
from utils.layouts import create_navigation_menu_2
from utils.database_singleton import get_db
from utils.auth_middleware import auth_required
from utils.firebase_auth import FirebaseAuth
from utils.filc_agent_client import FilcAgentClient
from datetime import datetime
import asyncio
from typing import Optional

@ui.page('/chat')
# @auth_required TODO: turn on when we have a way to handle auth
async def chat_page():
    """Chat interface with sidebar for managing multiple chat sessions and FILC Agent streaming integration."""
    create_navigation_menu_2()
    
    # Add custom CSS for streaming animations
    ui.add_head_html('''
    <style>
    .streaming-response {
        animation: none !important;
    }
    .streaming-indicator {
        display: inline-block;
        animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .typing-indicator::after {
        content: '●●●';
        animation: typing 1.5s infinite;
        color: #9CA3AF;
    }
    @keyframes typing {
        0%, 20% { opacity: 0; }
        40% { opacity: 1; }
        60% { opacity: 1; }
        80%, 100% { opacity: 0; }
    }
    </style>
    ''')
    
    # Initialize components inside function to avoid module-level database calls
    message_router = MessageRouter()
    db_adapter = await get_db()  # Use singleton instance with await
    filc_client = FilcAgentClient()
    
    # --- UI Element Variables (defined early for access in helpers) ---
    messages_container: Optional[ui.column] = None
    message_input: Optional[ui.input] = None
    spinner: Optional[ui.spinner] = None
    chat_list_ui: Optional[ui.column] = None

    # --- Helper Functions ---
    def format_timestamp(ts):
        if not ts:
            return "Unknown time"
        if isinstance(ts, str): # If already string, assume it's formatted
            try: # Try to parse and reformat for consistency, or return as is
                dt_obj = datetime.fromisoformat(ts)
                return dt_obj.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return ts 
        return ts.strftime("%Y-%m-%d %H:%M")

    def generate_user_avatar(user_email):
        """Generate a unique avatar URL based on user email."""
        if not user_email:
            # Fallback to a default avatar if no email
            return 'https://robohash.org/default?bgset=bg2&size=64x64'
        # Use robohash.org to generate consistent avatars based on email
        return f'https://robohash.org/{user_email}?bgset=bg2&size=64x64'



    async def load_and_display_chat_history(chat_id: str):
        nonlocal messages_container, messages_column, message_input, spinner # Ensure these are from chat_page scope
        
        if not messages_column: return
        messages_column.clear()

        if not chat_id:
            with messages_column:
                ui.label("Select a chat or start a new one.").classes('text-center m-auto')
            if message_input: message_input.disable()
            return

        app.storage.user['active_chat_id'] = chat_id
        print(f"Loading history for active_chat_id: {chat_id}")
        
        if spinner: spinner.visible = True
        try:
            history = await db_adapter.get_recent_messages(session_id=chat_id, limit=100)
            if not messages_column: return 
            
            if not history:
                with messages_column:
                    # Welcome message with assistant avatar
                    with ui.row().classes('justify-start items-end gap-2 w-full'):
                        with ui.avatar(size='sm').classes('flex-shrink-0'):
                            ui.image('https://robohash.org/assistant?bgset=bg1&size=32x32').classes('rounded-full')
                        with ui.element('div').classes('bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                            ui.markdown("Bienvenido! Describe tu idea y desarrollemosla juntos.")
            else:
                with messages_column:
                    for message in history:
                        if message['role'] == 'user':
                            # User message with avatar
                            with ui.row().classes('justify-end items-end gap-2 w-full'):
                                with ui.element('div').classes('bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                                    ui.markdown(message['content'])
                                with ui.avatar(size='sm').classes('flex-shrink-0'):
                                    ui.image(generate_user_avatar(user_email)).classes('rounded-full')
                        else: # assistant
                            # Assistant message with system avatar
                            with ui.row().classes('justify-start items-end gap-2 w-full'):
                                with ui.avatar(size='sm').classes('flex-shrink-0'):
                                    ui.image('https://robohash.org/assistant?bgset=bg1&size=32x32').classes('rounded-full')
                                with ui.element('div').classes('bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                                    ui.markdown(message['content'])
            # Direct scroll using the scroll area - like in reference script
            messages_container.scroll_to(percent=1e6)
            if message_input: message_input.enable()
        except Exception as e:
            print(f"Error loading chat history for {chat_id}: {e}")
            ui.notify(f"Error al cargar el historial del chat: {e}", type='negative')
            if messages_column:
                with messages_column:
                    ui.label(f"Error al cargar el chat {chat_id}.").classes('text-negative')
        finally:
            if spinner: spinner.visible = False
        refresh_task = update_chat_list.refresh()
        if refresh_task is not None:
            await refresh_task

    def scroll_to_bottom():
        """Direct scroll using NiceGUI scroll_area method - like reference script."""
        nonlocal messages_container
        if messages_container:
            try:
                # Direct method like in reference script
                messages_container.scroll_to(percent=1e6)
            except Exception as e:
                print(f"Scroll error: {e}")
                pass

    # --- Main UI Structure ---
    # Header with status indicator
    with ui.header().classes('items-center justify-between bg-white shadow-sm'):
        # Left side with title
        with ui.row().classes('items-center gap-2'):
            ui.label('Chat with FILC Agent').classes('text-h5 font-semibold')
            ui.badge('Streaming Optimized', color='green').classes('text-xs')
        
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

    # Sidebar for chat sessions
    with ui.left_drawer(value=True, bordered=True).classes('bg-gray-100 p-0') as sidebar:
        with ui.column().classes('w-full p-4 gap-2'):
            ui.label("Chats Anteriores").classes('text-h6 font-semibold mb-2')
            new_chat_button = ui.button("Nuevo Chat", icon='add_comment', on_click=lambda: start_new_chat()).props('unelevated color=primary').classes('w-full')
            
            # Container for the list of chats (will be @ui.refreshable)
            chat_list_ui = ui.column().classes('w-full gap-1 mt-2')


    # Main chat area
    with ui.column().classes('w-full h-screen p-0 m-0 flex flex-col ').style('height: 89vh'): # Custom height override
        # Use ui.scroll_area like in the reference script for better scroll control
        messages_container = ui.scroll_area().classes('flex-grow w-full p-4')
        with messages_container:
            # Container for messages inside the scroll area
            messages_column = ui.column().classes('gap-2 w-full')
        
        # Enhanced spinner positioned over the scroll area
        spinner = ui.spinner('audio', size='xl', color='primary').classes(
            'fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50'
        )
        if spinner: spinner.visible = False # Start hidden
        
        # Input area (footer) with user avatar
        with ui.row().classes('w-full p-4 bg-gray-50 border-t items-center gap-3'):
            # User Avatar
            user_email = app.storage.user.get('user_email', '')
            avatar_url = generate_user_avatar(user_email)
            with ui.avatar(size='md').classes('flex-shrink-0'):
                ui.image(avatar_url).classes('rounded-full')
                
            # Create textarea with proper event handling
            message_input = ui.textarea(placeholder='Escribe tu mensaje... (Shift+Enter para nueva línea)') \
                .classes('flex-grow') \
                .props('outlined dense rows=1 auto-grow')
            
                        # Handle Enter key with immediate response
            def handle_keydown(e):
                key = e.args.get('key')
                shift_key = e.args.get('shiftKey', False)
                
                if key == 'Enter' and not shift_key:
                    # Enter without Shift: Send message immediately - no delays
                    if message_input.value.strip():
                        # Clear input immediately for instant feedback
                        message_text = message_input.value.strip()
                        message_input.value = ''
                        # Send message with the captured text
                        asyncio.create_task(send_message_with_text(message_text))
            
            message_input.on('keydown', handle_keydown)
            
            # Add immediate JavaScript to prevent Enter from adding newlines (no delay)
            ui.run_javascript(f'''
                const textarea = document.getElementById('c{message_input.id}');
                if (textarea) {{
                    textarea.addEventListener('keydown', function(e) {{
                        if (e.key === 'Enter' && !e.shiftKey) {{
                            e.preventDefault();
                        }}
                    }});
                }}
            ''')
            
            send_button = ui.button(icon='send', on_click=lambda: send_current_message()).props('round flat color=primary')
            
    # --- Chat Logic & Refreshable Components ---
    @ui.refreshable
    async def update_chat_list():
        nonlocal chat_list_ui # chat_list_ui is modified here
        if not chat_list_ui: return

        chat_list_ui.clear()
        user_email = app.storage.user.get('user_email')
        if not user_email:
            with chat_list_ui:
                ui.label("Error: Usuario no identificado.")
            return

        chat_sessions = await db_adapter.get_chat_sessions_for_user(user_email)
        if not chat_sessions:
            with chat_list_ui:
                ui.label("No hay chats aún.").classes('text-gray-500 p-2')
        else:
            with chat_list_ui:
                active_chat_id_local = app.storage.user.get('active_chat_id')
                for session in chat_sessions:
                    chat_id = session['session_id']
                    preview = session.get('first_message_content', 'Chat iniciado')
                    if preview:
                        preview = preview[:30] + ("..." if len(preview) > 30 else "")
                    else:
                        preview = "Chat sin mensajes..."
                    timestamp_str = format_timestamp(session.get('last_message_timestamp'))
                    
                    item_classes = 'w-full p-3 rounded-lg cursor-pointer hover:bg-gray-200 transition-colors duration-150 ease-in-out'
                    if active_chat_id_local == chat_id:
                        item_classes += ' bg-blue-100 shadow-md'
                        
                    with ui.row().classes(item_classes).on('click', lambda cid=chat_id: select_chat(cid)):
                        with ui.column().classes('gap-0'):
                            ui.label(preview).classes('text-sm font-semibold text-gray-800')
                            ui.label(timestamp_str).classes('text-xs text-gray-500')
    
    async def select_chat(chat_id: str):
        nonlocal message_input # message_input is modified
        print(f"Selected chat: {chat_id}")
        if message_input: message_input.value = '' # Clear input when switching chats
        await load_and_display_chat_history(chat_id) 

    async def start_new_chat():
        nonlocal messages_container, messages_column, message_input # These are modified
        new_id = str(uuid.uuid4())
        app.storage.user['active_chat_id'] = new_id
        print(f"Starting new chat with ID: {new_id}")
        if messages_column:
            messages_column.clear()
            with messages_column:
                 # New chat welcome message with assistant avatar
                 with ui.row().classes('justify-start items-end gap-2 w-full'):
                     with ui.avatar(size='sm').classes('flex-shrink-0'):
                         ui.image('https://robohash.org/assistant?bgset=bg1&size=32x32').classes('rounded-full')
                     with ui.element('div').classes('bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                         ui.markdown("Nuevo chat iniciado. Describe tu idea y desarrollemosla juntos.")
        if message_input:
            message_input.enable()
            message_input.value = ''
        refresh_task = update_chat_list.refresh()
        if refresh_task is not None:
            await refresh_task
        # Direct scroll like reference script
        messages_container.scroll_to(percent=1e6)

    async def send_message_with_text(text: str):
        """Send a message with pre-captured text (for immediate UI response)."""
        nonlocal messages_container, messages_column, message_input, spinner, send_button # These are accessed/modified
        user_email = app.storage.user.get('user_email')
        active_chat_id = app.storage.user.get('active_chat_id')
        
        if not user_email or not text or not active_chat_id:
            ui.notify("Error: No se pudo enviar el mensaje (usuario, texto o chat activo faltante).", type='negative')
            if not active_chat_id:
                 await start_new_chat() # Or prompt user to start new chat
            return

        # 1. IMMEDIATE: Render user message in UI (no waiting for anything)
        if not messages_column: return
        with messages_column:
            # User message with avatar
            with ui.row().classes('justify-end items-end gap-2 w-full'):
                with ui.element('div').classes('bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                    ui.markdown(text)
                with ui.avatar(size='sm').classes('flex-shrink-0'):
                    ui.image(generate_user_avatar(user_email)).classes('rounded-full')
        
        # 2. IMMEDIATE: Scroll to show user message
        messages_container.scroll_to(percent=1e6)
        
        # 3. IMMEDIATE: Show spinner for AI processing
        if spinner: spinner.visible = True

        # 4. ASYNC: Start AI processing first, then DB operations
        asyncio.create_task(process_ai_then_save_to_db(text, user_email, active_chat_id))

    async def process_ai_then_save_to_db(text: str, user_email: str, active_chat_id: str):
        """Handle AI processing first, then DB operations asynchronously."""
        nonlocal messages_container, messages_column, spinner
        
        try:
            # Step 1: Get AI response directly (no DB operations yet)
            # Get conversation history for context
            history = await db_adapter.get_conversation_history(active_chat_id)
            
            # Stream AI response for real-time updates
            assistant_message_div = None
            assistant_markdown = None
            full_response = ""
            
            # Step 2: Create assistant message container immediately
            if messages_column:
                with messages_column:
                    # Assistant message with system avatar
                    with ui.row().classes('justify-start items-end gap-2 w-full'):
                        with ui.avatar(size='sm').classes('flex-shrink-0'):
                            ui.image('https://robohash.org/assistant?bgset=bg1&size=32x32').classes('rounded-full')
                        assistant_message_div = ui.element('div').classes('bg-gray-200 p-3 rounded-lg max-w-[80%]')
                        with assistant_message_div:
                            assistant_markdown = ui.markdown("").classes('streaming-response')
                
                # Scroll to show initial AI response container
                messages_container.scroll_to(percent=1e6)
            
            # Step 3: Stream response chunks
            try:
                async for chunk in message_router.process_user_message_stream(
                    message=text,
                    user_email=user_email,
                    session_id=active_chat_id
                ):
                    if chunk.get("success"):
                        if chunk.get("is_chunk", False):
                            # Update the markdown content with streaming text
                            chunk_content = chunk.get("full_content", "")
                            if assistant_markdown and chunk_content:
                                assistant_markdown.content = chunk_content
                                # Scroll to bottom after each chunk
                                messages_container.scroll_to(percent=1e6)
                        
                        elif chunk.get("is_final", False):
                            # Final update
                            final_content = chunk.get("content", "")
                            if assistant_markdown and final_content:
                                assistant_markdown.content = final_content
                                full_response = final_content
                            messages_container.scroll_to(percent=1e6)
                            break
                    else:
                        # Handle streaming error
                        error_content = f"**⚠️ Error del Sistema**\n\n{chunk.get('error', 'Error desconocido')}"
                        if assistant_markdown:
                            assistant_markdown.content = error_content
                            assistant_message_div.classes('bg-red-100 text-red-700 border-l-4 border-red-500')
                        messages_container.scroll_to(percent=1e6)
                        break
                        
            except Exception as stream_error:
                print(f"❌ Streaming error: {stream_error}")
                # Handle streaming failure
                error_content = f"**⚠️ Error de Conexión**\n\nNo se pudo establecer conexión de streaming: {stream_error}"
                if assistant_markdown:
                    assistant_markdown.content = error_content
                    assistant_message_div.classes('bg-red-100 text-red-700 border-l-4 border-red-500')
                messages_container.scroll_to(percent=1e6)

        except Exception as e:
            print(f"❌ Critical error in AI processing: {e}")
            # Can't use ui.notify from background task, so render error message directly
            if messages_column:
                with messages_column:
                     # Error message with system avatar
                     with ui.row().classes('justify-start items-end gap-2 w-full'):
                         with ui.avatar(size='sm').classes('flex-shrink-0'):
                             ui.image('https://robohash.org/error?bgset=bg1&size=32x32').classes('rounded-full')
                         with ui.element('div').classes('bg-red-100 text-red-700 p-3 rounded-lg max-w-[80%] border-l-4 border-red-500'):
                            ui.markdown(f"**⚠️ Error del Sistema**\n\nNo se pudo obtener respuesta: {e}")
                # Scroll after error message
                messages_container.scroll_to(percent=1e6)
        finally:
            if spinner: spinner.visible = False
            # Refresh sidebar after everything is done
            refresh_task = update_chat_list.refresh()
            if refresh_task is not None:
                await refresh_task



    async def send_current_message():
        """Send message from input field (for send button)."""
        if not message_input: # Guard against None
            ui.notify("Error: El campo de mensaje no está inicializado.", type='negative')
            return
        text = message_input.value.strip()
        if text:
            message_input.value = '' # Clear input immediately
            await send_message_with_text(text)

    # --- Initial Page Load Logic ---
    user_email = app.storage.user.get('user_email')
    if not user_email:
        ui.label("Error: Usuario no autenticado.").classes('text-center m-auto text-negative')
        return

    await update_chat_list() 

    active_chat_id_on_load = app.storage.user.get('active_chat_id')
    if active_chat_id_on_load:
        # Must await async functions called directly
        await load_and_display_chat_history(active_chat_id_on_load)
    else:
        chat_sessions = await db_adapter.get_chat_sessions_for_user(user_email)
        if chat_sessions:
            most_recent_chat_id = chat_sessions[0]['session_id']
            app.storage.user['active_chat_id'] = most_recent_chat_id
            await load_and_display_chat_history(most_recent_chat_id)
            # load_and_display_chat_history already calls update_chat_list.refresh()
        else:
            if messages_column: messages_column.clear()
            if messages_column:
                with messages_column:
                    # Default welcome message with assistant avatar
                    with ui.row().classes('justify-start items-end gap-2 w-full'):
                        with ui.avatar(size='sm').classes('flex-shrink-0'):
                            ui.image('https://robohash.org/assistant?bgset=bg1&size=32x32').classes('rounded-full')
                        with ui.element('div').classes('bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                            ui.markdown("Bienvenido! Inicia un nuevo chat para comenzar o selecciona uno anterior si existe.")
            if message_input: message_input.disable()
