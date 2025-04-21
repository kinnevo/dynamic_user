from nicegui import ui, app
import uuid
from utils.state import logout, update_user_status, set_user_logout_state
from utils.database import PostgresAdapter
from utils.layouts import create_navigation_menu_2

# Initialize database adapter
db_adapter = PostgresAdapter()

# Initialize visit counter cookie
def get_visit_count() -> int:
    """Get visit count and initialize session if needed"""
    # Check if we should create a new session
    should_reset = ('visits' in app.storage.browser and logout == True) or ('visits' not in app.storage.browser)
    
    # Get the URL parameters using JavaScript
    def check_for_new_session():
        result = ui.run_javascript("""
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('newSession') === 'true';
        """)
        return result
    
    # Force reset if we have the newSession parameter
    if ui.run_javascript("return window.location.search.includes('newSession=true')"):
        should_reset = True
        # Reset the logout flag
        set_user_logout_state(False)
    
    if should_reset:
        # Initialize new session
        app.storage.browser['visits'] = 0
        app.storage.browser['session_id'] = str(uuid.uuid4())
        app.storage.browser['user_id'] = db_adapter.create_user(app.storage.browser['session_id'])
        
        # Set initial user status
        db_adapter.update_user_status(app.storage.browser['session_id'], "Idle")
    
    app.storage.browser['visits'] += 1
    return app.storage.browser['visits']

@ui.page('/home')
def home():
    # Initialize user visit count - this now checks URL parameters internally
    visit_count = get_visit_count()
    
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
