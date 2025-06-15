from nicegui import ui, app
import uuid
from utils.message_router import MessageRouter
from utils.layouts import create_navigation_menu_2
from utils.database_singleton import get_db
from utils.auth_middleware import auth_required
from datetime import datetime
import asyncio
from typing import Optional # Added for type hinting

# Initialize components - moved inside function to avoid module-level database initialization
# message_router = MessageRouter()
# db_adapter = get_db()  # Use singleton instance

@ui.page('/chat')
# @auth_required # TODO: Uncomment this when done debugging
async def chat_page():
    """Chat interface with sidebar for managing multiple chat sessions."""
    create_navigation_menu_2()
    
    # Initialize components inside function to avoid module-level database calls
    message_router = MessageRouter()
    db_adapter = await get_db()  # Use singleton instance with await
    
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
        """Simple scroll function using element ID and fallback methods."""
        nonlocal messages_container
        if not messages_container:
            return
            
        try:
            # Fire-and-forget JavaScript call - don't await to avoid KeyError
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
                    
                    // Method 2: Find any scrollable container
                    const containers = document.querySelectorAll('[class*="overflow-y-auto"]');
                    for (let container of containers) {{
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
    # Sidebar for chat sessions
    with ui.left_drawer(value=True, bordered=True).classes('bg-gray-100 p-0') as sidebar:
        with ui.column().classes('w-full p-4 gap-2'):
            ui.label("Chats Anteriores").classes('text-h6 font-semibold mb-2')
            new_chat_button = ui.button("Nuevo Chat", icon='add_comment', on_click=lambda: start_new_chat()).props('unelevated color=primary').classes('w-full')
            
            # Container for the list of chats (will be @ui.refreshable)
            chat_list_ui = ui.column().classes('w-full gap-1 mt-2')


    # Main chat area
    with ui.column().classes('w-full h-screen p-0 m-0 flex flex-col ').style('height: 89vh'): # Custom height override
        # Use a div with relative positioning to act as a container for messages_container and spinner
        with ui.element('div').classes('flex-grow w-full relative overflow-hidden'):
            messages_container = ui.column().classes(
                'absolute inset-0 overflow-y-auto p-4 gap-2' 
            )
            # Spinner is defined and placed here, centered over messages_container
            spinner = ui.spinner(size='xl', color='primary').classes(
                'absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2'
            )
            if spinner: spinner.visible = False # Start hidden
        
        # Input area (footer)
        with ui.row().classes('w-full p-4 bg-gray-50 border-t items-center gap-2'):
            message_input = ui.input(placeholder='Escribe tu mensaje...').classes('flex-grow').on('keydown.enter', lambda: send_current_message())
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
        nonlocal messages_container, message_input # These are modified
        new_id = str(uuid.uuid4())
        app.storage.user['active_chat_id'] = new_id
        print(f"Starting new chat with ID: {new_id}")
        if messages_container:
            messages_container.clear()
            with messages_container:
                 ui.markdown("Nuevo chat iniciado. Describe tu idea y desarrollemosla juntos.").classes('self-start bg-gray-200 p-3 rounded-lg max-w-[80%]')
        if message_input:
            message_input.enable()
            message_input.value = ''
        update_chat_list.refresh() # Remove await - refresh() is not async
        await scroll_to_bottom()

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
            
            # Small delay to ensure DOM is updated, then scroll
            await scroll_to_bottom()

            if response_data.get("error") and response_data.get("error_type") == "non_critical":
                ui.notify(f"Nota: {response_data['error']}", type='warning', timeout=5000)
            elif response_data.get("error") and not response_data.get("content"):
                 ui.notify(f"Error procesando el mensaje: {response_data['error']}", type='negative', timeout=5000)

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
            if message_input: message_input.disable()

    # Add asyncio import if not already present at the top
    # import asyncio # Already present

# Note: The FilcAgentClient and MessageRouter integrations are placeholders
# and would need to be fully integrated into the send_current_message logic.
# Error handling, loading spinners, and more sophisticated UI updates can be added. 