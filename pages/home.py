from nicegui import ui, app
import uuid
from utils.state import logout, update_user_status, set_user_logout_state, set_post_logout_session
from utils.database import PostgresAdapter
from utils.layouts import create_navigation_menu_2

# Initialize database adapter
db_adapter = PostgresAdapter()

# Initialize visit counter cookie
async def get_visit_count() -> int:
    """Get visit count and initialize session if needed"""
    # Use a simpler approach with direct localStorage checks and fewer JavaScript calls
    
    # First, check if we already have a session in app.storage.browser
    if 'session_id' in app.storage.browser and 'user_id' in app.storage.browser:
        # We already have session data in app storage, use it
        session_id = app.storage.browser['session_id']
        user_id = app.storage.browser['user_id']
        
        # Check if logout flag is set - if so, we need to reset
        if logout:
            should_reset = True
        else:
            # Use existing session
            should_reset = False
            
            # Update the localStorage for consistency (one-time operation)
            ui.run_javascript(f"""
                localStorage.setItem('persistent_session_id', '{session_id}');
                localStorage.setItem('persistent_user_id', '{user_id}');
            """)
    else:
        # No session in app.storage.browser, check localStorage
        try:
            # Use a higher timeout (5 seconds) for JavaScript
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
                
                // Return the data if it exists
                if (sessionId && userId) {
                    return {
                        exists: true,
                        session_id: sessionId,
                        user_id: userId
                    };
                }
                return { exists: false };
            """, timeout=5)
            
            # Check if we have data in localStorage
            if storage_data and storage_data.get('exists', False):
                # Use existing localStorage session
                # Set the session ID in the post-logout tracker
                session_id = storage_data['session_id']
                set_post_logout_session(session_id)
                print(f"Setting post-logout session to existing: {session_id}")
                
                try:
                    app.storage.browser['session_id'] = session_id
                    app.storage.browser['user_id'] = storage_data['user_id']
                except TypeError:
                    # If browser storage is locked, we can't update it
                    print("Browser storage already locked, session restore saved in memory only")
                    # session_id is already set above for local use
                    user_id = storage_data['user_id']
                should_reset = False
                print(f"Restored session from localStorage: {storage_data['session_id']}")
            else:
                # No localStorage session either, we need to create a new one
                should_reset = True
        except Exception as e:
            # If there's any error (like a timeout), create a new session
            print(f"Error checking localStorage: {e}")
            should_reset = True
    
    # Check URL parameter for newSession=true
    try:
        new_session_param = await ui.run_javascript("return window.location.search.includes('newSession=true')", timeout=5)
        if new_session_param:
            should_reset = True
            set_user_logout_state(False)
    except Exception:
        # If we can't check URL params, continue with previous decision
        pass
    
    # Create a new session if needed
    if should_reset:
        print("Creating new session and user...")
        
        # Generate new IDs
        new_session_id = str(uuid.uuid4())
        new_user_id = db_adapter.create_user(new_session_id)
        
        # Set the post-logout session ID to handle message retrieval after logout
        set_post_logout_session(new_session_id)
        print(f"Setting post-logout session to: {new_session_id}")
        
        # Update app storage with error handling
        try:
            app.storage.browser['session_id'] = new_session_id
            app.storage.browser['user_id'] = new_user_id
            app.storage.browser['visits'] = 0
        except TypeError:
            # If browser storage is locked, we can't update it
            print("Browser storage already locked when creating new session")
            # But we can still use the values locally
            session_id = new_session_id
            user_id = new_user_id
        
        # Update user status
        db_adapter.update_user_status(new_session_id, "Idle")
        
        # Store in localStorage (do not await this - fire and forget)
        ui.run_javascript(f"""
            localStorage.setItem('persistent_session_id', '{new_session_id}');
            localStorage.setItem('persistent_user_id', '{new_user_id}');
            console.log('Created new session:', {{ session_id: '{new_session_id}', user_id: '{new_user_id}' }});
        """)
        
        # If logout was the reason for reset, clear the flag
        if logout:
            set_user_logout_state(False)
    
    # Initialize visit counter if needed - with error handling
    try:
        if 'visits' not in app.storage.browser:
            app.storage.browser['visits'] = 0
    except TypeError:
        # If browser storage is already locked, we can't set the initial value
        print("Browser storage already locked, can't initialize visits")
        pass
    
    # Simplified visit count approach - use a fixed value on first session creation
    # and don't worry about persisting it - the user ID is what matters
    try:
        if should_reset:
            # If we're creating a new session, always return 1
            return 1
        else:
            # If using existing session, return a simple incremented value
            # This simplifies the logic and avoids browser storage issues
            current_visits = app.storage.browser.get('visits', 0)
            return current_visits + 1
    except Exception as e:
        print(f"Error handling visit count: {e}")
        return 1  # Default to 1 if anything goes wrong

@ui.page('/home')
async def home():
    # Initialize user visit count - this now checks URL parameters internally
    visit_count = await get_visit_count()
    
    # Optional: If you want to display a small header with user info
    with ui.row().classes('w-full justify-end p-2'):
        ui.label(f'Visitas: {visit_count}').classes('text-sm')
    
    with ui.column().classes('w-full items-center'):
        ui.label('Resuelve desafíos reales con FastInnovation').classes('text-h3 q-mb-md')
        ui.label('Disfruta el arte de solucionar problemas cotidianos').classes('text-h5 q-mb-md')
        
        with ui.row().classes('w-full items-center justify-center'):

            # Left column with text
            with ui.column().classes('w-2/5'):  # Takes up 50% of the width
                ui.label('Los mejores productos nacen al comprender profundamente los desafíos cotidianos de tus clientes. FastInnovation es el aliado perfecto para ayudarte a identificar con claridad esos problemas y transformarlos en soluciones rápidas y efectivas.').classes('text-body1 q-mb-md text-left')
                ui.label('¿Qué logramos juntos?').classes('text-body1 q-mb-md text-left')
                ui.label('Identificar quién es realmente tu cliente ideal y qué necesita exactamente.').classes('text-body1 text-left')
                ui.label('Descubrir qué piensa y siente cuando interactúa con tu producto.').classes('text-body1 text-left')
                ui.label('Entender claramente las tareas específicas que tus clientes buscan resolver, posicionando así tu producto como la solución óptima.').classes('text-body1 text-left')
                ui.label('Priorizar los problemas con mayor impacto para enfocarte en lo que realmente importa.').classes('text-body1 text-left')
                ui.label('FastInnovation combina metodologías probadas—como la técnica Persona, Mapa de Empatía, Jobs To Be Done e Impact Check—fortalecidas con la precisión única de la inteligencia artificial.').classes('text-body1 text-left')
                ui.label('¿Listo para hacer tu día más sencillo y productivo?').classes('text-body1 q-mb-md text-left')
                ui.label('Comienza a resolver desafíos reales con la ayuda práctica de FastInnovation.').classes('text-body1 q-mb-md text-left')


                with ui.row().classes('w-full justify-center'):
                    ui.button('Vamos a resolver desafíos reales ...').classes('text-h6 q-mb-md').on_click(lambda: ui.navigate.to('/chat'))

            # Right column with image
            with ui.column().classes('w-2/5'):  # Takes up 50% of the width
                ui.image('static/fastinnovation_cover1.png').style('width: 75%; height: 75%; object-fit: contain').classes('rounded-lg shadow-lg')

        
        ui.label('🚀 FastInnovation tu mejor socio para la innovación. Comienza ahora.').classes('text-body1 q-mb-md text-left')
        ui.html('<strong>Aviso de Privacidad</strong>: Las conversaciones en este sitio son almacenadas de manera anónima con el propósito exclusivo de analizar los intereses de los participantes y mejorar el desarrollo de experiencias de conocimiento. Toda la información recopilada es para uso interno y no será compartida con terceros.').classes('text-body2 q-mb-md text-justify')
