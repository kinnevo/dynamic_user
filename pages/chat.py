from nicegui import ui, app
import uuid
from utils.message_router import MessageRouter
from utils.layouts import create_navigation_menu_2
from utils.database_singleton import get_db
from utils.auth_middleware import auth_required
from utils.filc_agent_client import FilcAgentClient
from datetime import datetime
import asyncio
from typing import Optional

@ui.page('/chat')
@auth_required 
async def chat_page():
    """Chat interface with sidebar for managing multiple chat sessions and FILC Agent integration."""
    create_navigation_menu_2()
    
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

    async def load_and_display_chat_history(chat_id: str):
        nonlocal messages_container, message_input, spinner # Ensure these are from chat_page scope
        
        if not messages_container: return
        messages_container.clear()

        if not chat_id:
            with messages_container:
                ui.label("Select a chat or start a new one.").classes('text-center m-auto')
            if message_input: message_input.disable()
            return

        app.storage.user['active_chat_id'] = chat_id
        print(f"Loading history for active_chat_id: {chat_id}")
        
        if spinner: spinner.visible = True
        try:
            history = await db_adapter.get_conversation_history(session_id=chat_id)
            if not messages_container: return
            
            if not history:
                with messages_container:
                    ui.markdown("Bienvenido! Describe tu idea y desarrollemosla juntos.").classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]')
            else:
                with messages_container:
                    for message in history:
                        if message['role'] == 'user':
                            with ui.element('div').classes('self-end bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                                ui.markdown(message['content'])
                        else: # assistant
                            with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                                ui.markdown(message['content'])
            
            # Add spacer at the bottom after messages
            with messages_container:
                ui.space().classes('h-8')
                
            await scroll_to_bottom()
            if message_input: message_input.enable()
        except Exception as e:
            print(f"Error loading chat history for {chat_id}: {e}")
            ui.notify(f"Error al cargar el historial del chat: {e}", type='negative')
            if messages_container:
                with messages_container:
                    ui.label(f"Error al cargar el chat {chat_id}.").classes('text-negative')
        finally:
            if spinner: spinner.visible = False
        update_chat_list.refresh() # Remove await - refresh() is not async

    async def scroll_to_bottom():
        """Enhanced scroll function with multiple fallback methods."""
        nonlocal messages_container
        if not messages_container:
            return
            
        try:
            # Fire-and-forget JavaScript call with multiple methods
            ui.run_javascript(f'''
                setTimeout(() => {{
                    // Method 1: Direct element access
                    try {{
                        const el = getElement({messages_container.id});
                        if (el) {{
                            el.scrollTop = el.scrollHeight;
                            console.log('Scrolled using element ID');
                            return;
                        }}
                    }} catch (e) {{
                        console.log('Element ID failed:', e);
                    }}
                    
                    // Method 2: Find overflow-y-auto containers
                    const containers = document.querySelectorAll('[class*="overflow-y-auto"]');
                    for (let container of containers) {{
                        if (container.scrollHeight > container.clientHeight) {{
                            container.scrollTop = container.scrollHeight;
                            console.log('Scrolled using overflow-y-auto method');
                            return;
                        }}
                    }}
                    
                    // Method 3: Find any scrollable container
                    const allContainers = document.querySelectorAll('div');
                    for (let container of allContainers) {{
                        if (container.scrollHeight > container.clientHeight) {{
                            container.scrollTop = container.scrollHeight;
                            console.log('Scrolled using fallback method');
                            return;
                        }}
                    }}
                    
                    console.log('No scrollable container found');
                }}, 150);
            ''')
        except Exception as e:
            print(f"Scroll error: {e}")
            pass

    # --- Main UI Structure ---
    # Header with status indicator
    with ui.header().classes('items-center justify-between bg-white shadow-sm'):
        # Left side with title
        with ui.row().classes('items-center gap-2'):
            ui.label('Chat with FILC Agent').classes('text-h5 font-semibold')
        
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

    # Main content area with improved layout to eliminate bottom whitespace
    with ui.element('div').classes('flex flex-col w-full').style('height: calc(100vh - 10.8vh); max-height: calc(100vh - 4vh);'):  # Account for header + navigation + padding
        # Messages area - takes up available space
        with ui.element('div').classes('flex-1 w-full relative overflow-hidden'):
            messages_container = ui.column().classes(
                'absolute inset-0 overflow-y-auto p-4 gap-2' 
            )
            # Spinner is defined and placed here, centered over messages_container
            spinner = ui.spinner('dots', size='lg', color='primary').classes(
                'absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2'
            )
            if spinner: spinner.visible = False # Start hidden
        
        # Input area - fixed at bottom with no extra margin/padding
        with ui.row().classes('flex-shrink-0 w-full p-4 bg-white border-t items-center gap-2').style('margin: 0; padding-bottom: 16px;'):
            message_input = ui.input(placeholder='Escribe tu mensaje...').classes('flex-1')
            
            # Send button - define the function first, then use it
            send_button = ui.button('Send', on_click=lambda: send_current_message()).classes('bg-blue-500 text-white')
            
    async def send_current_message():
        nonlocal messages_container, message_input, spinner # These are accessed/modified
        user_email = app.storage.user.get('user_email')
        active_chat_id = app.storage.user.get('active_chat_id')
        
        if not message_input: # Guard against None
            ui.notify("Error: El campo de mensaje no está inicializado.", type='negative')
            return
        text = message_input.value.strip()
        
        if not user_email or not text or not active_chat_id:
            ui.notify("Error: No se pudo enviar el mensaje (usuario, texto o chat activo faltante).", type='negative')
            if not active_chat_id:
                 await start_new_chat() # Or prompt user to start new chat
            return
        
        message_input.value = '' # Clear input immediately

        if not messages_container: return
        with messages_container:
            with ui.element('div').classes('self-end bg-blue-500 text-white p-3 rounded-lg max-w-[80%]'):
                ui.markdown(text)
        
        # Small delay to ensure DOM is updated, then scroll
        await scroll_to_bottom()

        if spinner: spinner.visible = True
        try:
            response_data = await message_router.process_user_message(
                message=text,
                user_email=user_email,
                session_id=active_chat_id
            )
            
            assistant_response_content = "Error: No se pudo obtener respuesta del asistente."
            if response_data.get("content"):
                assistant_response_content = response_data.get("content")
            elif response_data.get("error"):
                 assistant_response_content = f"Error del asistente: {response_data.get('error')}"

            # The assistant's message is saved by MessageRouter. Display it.
            with messages_container:
                with ui.element('div').classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]'):
                    ui.markdown(assistant_response_content)
            
            # Add spacer at the bottom after messages
            with messages_container:
                ui.space().classes('h-8')
            
            # Small delay to ensure DOM is updated, then scroll
            await scroll_to_bottom()

            # Handle errors - only display significant errors, not connection warnings
            if response_data.get("error"):
                error_message = response_data.get("error")
                is_connection_warning = ('connection' in error_message.lower() or 'timeout' in error_message.lower())
                
                if response_data.get("error_type") == "non_critical" or is_connection_warning:
                    if not is_connection_warning:
                        ui.notify(f"Nota: {response_data['error']}", type='warning', timeout=5000)
                elif not response_data.get("content"):
                    short_error = error_message.split('\n')[0] if '\n' in error_message else error_message
                    ui.notify(f"Error procesando el mensaje: {short_error}", type='negative', timeout=10000)
                    
                    # For severe errors that prevent message delivery
                    with messages_container:
                        with ui.element('div').classes('self-start bg-red-100 p-3 rounded-lg max-w-[80%] border-l-4 border-red-500'):
                            ui.markdown("**⚠️ Error del Sistema**\n\nHubo un problema procesando tu solicitud. El mensaje fue guardado pero no se pudo generar la respuesta del AI.")

        except Exception as e:
            print(f"Critical error calling message router: {e}")
            ui.notify(f"Error crítico del sistema: {e}", type='negative')
            with messages_container:
                 with ui.element('div').classes('self-start bg-red-100 text-red-700 p-3 rounded-lg max-w-[80%] border-l-4 border-red-500'):
                    ui.markdown(f"**⚠️ Error del Sistema**\n\nNo se pudo obtener respuesta: {e}")
            await scroll_to_bottom()
        finally:
            if spinner: spinner.visible = False
        update_chat_list.refresh() # Remove await - refresh() is not async

    # Set up Enter key handler after function is defined
    if message_input:
        message_input.on('keydown.enter', send_current_message)
            
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
        nonlocal messages_container, message_input # These are modified
        new_id = str(uuid.uuid4())
        app.storage.user['active_chat_id'] = new_id
        print(f"Starting new chat with ID: {new_id}")
        if messages_container:
            messages_container.clear()
            with messages_container:
                 ui.markdown("Nuevo chat iniciado. Describe tu idea y desarrollemosla juntos.").classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]')
                 # Add spacer at the bottom
                 ui.space().classes('h-8')
        if message_input:
            message_input.enable()
            message_input.value = ''
        update_chat_list.refresh() # Remove await - refresh() is not async
        await scroll_to_bottom()

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
            if messages_container: messages_container.clear()
            if messages_container:
                with messages_container:
                    ui.markdown("Bienvenido! Inicia un nuevo chat para comenzar o selecciona uno anterior si existe.").classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]')
                    ui.space().classes('h-8')
            if message_input: message_input.disable()
