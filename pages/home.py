from nicegui import ui, app
# import uuid # No longer needed for session_id generation here
# from utils.state import logout, set_user_logout_state # logout flag and set_user_logout_state might be re-evaluated
from utils.layouts import create_navigation_menu_2
from utils.database_singleton import get_db
from utils.firebase_auth import FirebaseAuth
from utils.auth_middleware import get_user_display_name, auth_required

@ui.page('/home')
@auth_required
async def home():
    """Home page with user tracking and navigation"""
    # Initialize the navigation menu
    create_navigation_menu_2()
    
    # Use singleton database adapter for user tracking - moved inside function
    db_adapter = get_db()

    # Get current authenticated user
    current_user_details = FirebaseAuth.get_current_user()

    if current_user_details and current_user_details.get('email'):
        user_email = current_user_details['email']
        firebase_uid = current_user_details.get('uid')
        display_name = current_user_details.get('displayName')
        
        # Ensure user exists in database with Firebase UID and display name
        user_id = db_adapter.get_or_create_user_by_email(
            email=user_email,
            firebase_uid=firebase_uid,
            display_name=display_name
        )
        
        if user_id:
            print(f"User {user_email} (UID: {firebase_uid}) ensured in database with ID: {user_id}")
            # Update user status to Active when they visit home
            db_adapter.update_user_status(identifier=user_email, status="Active", is_email=True)
        else:
            print(f"Failed to ensure user {user_email} in database")
    else:
        # This case should ideally not be reached due to @auth_required
        # but as a fallback or if auth_required logic changes:
        print("Home page: No authenticated user email found. Cannot update status.")
        # Optionally, redirect to login if somehow @auth_required didn't catch it
        # return ui.navigate.to('/login')

    # Header with user info and authentication controls (can be part of create_navigation_menu_2 or separate)
    # If create_navigation_menu_2 already handles user display and logout, this might be redundant.
    # For now, let's assume create_navigation_menu_2 provides the visual structure,
    # and we might add specific user-related actions here if needed, or integrate them into create_navigation_menu_2.
    
    # Example of displaying user info if not handled by create_navigation_menu_2:
    # with ui.row().classes('w-full justify-end items-center p-2'):
    #     if current_user_details:
    #         display_name = get_user_display_name() # Uses updated get_user_display_name
    #         ui.label(f'Hola, {display_name}').classes('text-sm mr-2')
    #         logout_btn = ui.button('Cerrar Sesión', icon='logout', 
    #                                on_click=lambda: (FirebaseAuth.logout_user(), ui.navigate.to('/login')))
    #         logout_btn.props('flat dense').classes('text-sm')
    #     else:
    #         # Should not happen due to @auth_required
    #         ui.label("Not logged in.")

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
