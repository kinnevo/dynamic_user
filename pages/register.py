from nicegui import ui, app
from utils.firebase_auth import FirebaseAuth
import re

@ui.page('/register')
def register_page():
    """Registration page with Firebase authentication"""
    
    # Create a container for the registration form
    with ui.card().classes('w-96 mx-auto mt-16 p-6'):
        ui.label('Crear una Cuenta').classes('text-h4 mb-4 text-center')
        
        # Name input
        name_input = ui.input('Nombre').props('outlined').classes('w-full mb-4')
        
        # Email input
        email_input = ui.input('Correo electrónico').props('outlined').classes('w-full mb-4')
        
        # Password input
        password_input = ui.input('Contraseña', password=True).props('outlined').classes('w-full mb-4')
        
        # Confirm password input
        confirm_password_input = ui.input('Confirmar contraseña', password=True).props('outlined').classes('w-full mb-6')
        
        # Error message (hidden by default)
        error_label = ui.label('').classes('text-negative text-center w-full mb-4 hidden')
        
        # Success message (hidden by default)
        success_label = ui.label('').classes('text-positive text-center w-full mb-4 hidden')
        
        # Register button
        with ui.row().classes('w-full justify-center'):
            register_btn = ui.button('Registrarse').props('unelevated').classes('w-full')
        
        # Login link
        with ui.row().classes('w-full justify-center mt-4'):
            ui.label('¿Ya tienes una cuenta?').classes('mr-2')
            ui.link('Iniciar Sesión', '/login').classes('text-primary')
        
        # Register button click handler
        def on_register_click():
            # Clear previous messages
            error_label.classes('hidden')
            success_label.classes('hidden')
            
            # Validate inputs
            if not name_input.value:
                error_label.text = 'Por favor ingresa tu nombre'
                error_label.classes('text-negative text-center w-full mb-4')
                return
            
            if not email_input.value:
                error_label.text = 'Por favor ingresa tu correo electrónico'
                error_label.classes('text-negative text-center w-full mb-4')
                return
            
            # Validate email format
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_pattern, email_input.value):
                error_label.text = 'Por favor ingresa un correo electrónico válido'
                error_label.classes('text-negative text-center w-full mb-4')
                return
            
            if not password_input.value:
                error_label.text = 'Por favor ingresa una contraseña'
                error_label.classes('text-negative text-center w-full mb-4')
                return
            
            # Validate password strength (minimum 6 characters)
            if len(password_input.value) < 6:
                error_label.text = 'La contraseña debe tener al menos 6 caracteres'
                error_label.classes('text-negative text-center w-full mb-4')
                return
            
            if password_input.value != confirm_password_input.value:
                error_label.text = 'Las contraseñas no coinciden'
                error_label.classes('text-negative text-center w-full mb-4')
                return
            
            # Attempt registration
            result = FirebaseAuth.register_user(
                email_input.value, 
                password_input.value,
                name_input.value
            )
            
            if result['success']:
                # Show success message
                success_label.text = '¡Registro exitoso! Ahora puedes iniciar sesión.'
                success_label.classes('text-positive text-center w-full mb-4')
                
                # Redirect to login page after short delay
                ui.timer(2, lambda: ui.navigate.to('/login'))
            else:
                # Show error message
                error_msg = result.get('error', 'Error de registro')
                # Handle common Firebase errors
                if 'EMAIL_EXISTS' in error_msg:
                    error_msg = 'Este correo electrónico ya está registrado'
                elif 'WEAK_PASSWORD' in error_msg:
                    error_msg = 'La contraseña es demasiado débil'
                
                error_label.text = error_msg
                error_label.classes('text-negative text-center w-full mb-4')
        
        # Connect button to handler
        register_btn.on('click', on_register_click)
