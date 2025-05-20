from nicegui import ui, app
from utils.firebase_auth import FirebaseAuth
from utils.layouts import create_navigation_menu_2
import json

@ui.page('/login')
def login_page():
    """Login page with Firebase authentication"""
    
    # Initialize user storage if not already done
    if not hasattr(app.storage, 'user'):
        app.storage.user = {}
    
    # Create a container for the login form
    with ui.card().classes('w-96 mx-auto mt-16 p-6'):
        ui.label('Iniciar Sesión').classes('text-h4 mb-4 text-center')
        
        # Email input
        email_input = ui.input('Correo electrónico').props('outlined').classes('w-full mb-4')
        
        # Password input 
        password_input = ui.input('Contraseña', password=True).props('outlined').classes('w-full mb-6')
        
        # Error message (hidden by default)
        error_label = ui.label('').classes('text-negative text-center w-full mb-4 hidden')
        
        # Success message (hidden by default)
        success_label = ui.label('').classes('text-positive text-center w-full mb-4 hidden')
        
        # Debug message (for troubleshooting)
        debug_label = ui.label('').classes('text-gray-500 text-sm text-center w-full mb-4')
        
        # Login button
        with ui.row().classes('w-full justify-center'):
            login_btn = ui.button('Iniciar Sesión').props('unelevated').classes('w-full')
        
        # Register link
        with ui.row().classes('w-full justify-center mt-4'):
            ui.label('¿No tienes una cuenta?').classes('mr-2')
            ui.link('Regístrate', '/register').classes('text-primary')
        
        # Reset password link
        with ui.row().classes('w-full justify-center mt-2'):
            ui.link('¿Olvidaste tu contraseña?', '/reset-password').classes('text-primary')
        
        # Login button click handler
        def on_login_click():
            # Clear previous messages
            error_label.classes('hidden')
            success_label.classes('hidden')
            debug_label.text = 'Procesando inicio de sesión...'
            
            # Validate inputs
            if not email_input.value:
                error_label.text = 'Por favor ingresa tu correo electrónico'
                error_label.classes('text-negative text-center w-full mb-4')
                debug_label.text = 'Error: Email vacío'
                return
            
            if not password_input.value:
                error_label.text = 'Por favor ingresa tu contraseña'
                error_label.classes('text-negative text-center w-full mb-4')
                debug_label.text = 'Error: Contraseña vacía'
                return
            
            debug_label.text = f'Enviando credenciales a Firebase: {email_input.value}'
            
            try:
                # Attempt login
                result = FirebaseAuth.login_user(email_input.value, password_input.value)
                
                if result['success']:
                    # Store user data in session
                    app.storage.user['user'] = result['user']
                    
                    # Show success message
                    success_label.text = '¡Inicio de sesión exitoso!'
                    success_label.classes('text-positive text-center w-full mb-4')
                    debug_label.text = 'Inicio de sesión exitoso, redirigiendo...'
                    
                    # Redirect to home page after short delay
                    ui.timer(0.8, lambda: ui.navigate.to('/home'))
                else:
                    # Show error message
                    error_msg = result.get('error', 'Error de inicio de sesión')
                    debug_label.text = f'Error de Firebase: {error_msg}'
                    
                    # Handle common Firebase errors
                    if 'INVALID_LOGIN_CREDENTIALS' in error_msg:
                        error_msg = 'Credenciales inválidas. Verifica tu correo y contraseña.'
                    elif 'TOO_MANY_ATTEMPTS_TRY_LATER' in error_msg:
                        error_msg = 'Demasiados intentos. Intenta más tarde.'
                    
                    error_label.text = error_msg
                    error_label.classes('text-negative text-center w-full mb-4')
            except Exception as e:
                error_label.text = f"Error inesperado: {str(e)}"
                error_label.classes('text-negative text-center w-full mb-4')
                debug_label.text = f'Excepción: {str(e)}'
        
        # Connect button to handler
        login_btn.on('click', on_login_click)
