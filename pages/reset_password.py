from nicegui import ui, app
from utils.firebase_auth import FirebaseAuth
import re

@ui.page('/reset-password')
def reset_password_page():
    """Password reset page with Firebase authentication"""
    
    # Initialize user storage if not already done
    if not hasattr(app.storage, 'user'):
        app.storage.user = {}
    
    # Create a container for the password reset form
    with ui.card().classes('w-96 mx-auto mt-16 p-6'):
        ui.label('Restablecer Contraseña').classes('text-h4 mb-4 text-center')
        
        # Email input
        email_input = ui.input('Correo electrónico').props('outlined').classes('w-full mb-6')
        
        # Error message (hidden by default)
        error_label = ui.label('').classes('text-negative text-center w-full mb-4 hidden')
        
        # Success message (hidden by default)
        success_label = ui.label('').classes('text-positive text-center w-full mb-4 hidden')
        
        # Debug message (for troubleshooting)
        debug_label = ui.label('').classes('text-gray-500 text-sm text-center w-full mb-4')
        
        # Reset password button
        with ui.row().classes('w-full justify-center'):
            reset_btn = ui.button('Enviar Link de Recuperación').props('unelevated').classes('w-full')
        
        # Back to login link
        with ui.row().classes('w-full justify-center mt-4'):
            ui.link('Volver a Iniciar Sesión', '/login').classes('text-primary')
        
        # Reset button click handler
        def on_reset_click():
            # Clear previous messages
            error_label.classes('hidden')
            success_label.classes('hidden')
            debug_label.text = 'Procesando solicitud de restablecimiento...'
            
            # Validate inputs
            if not email_input.value:
                error_label.text = 'Por favor ingresa tu correo electrónico'
                error_label.classes('text-negative text-center w-full mb-4')
                debug_label.text = 'Error: Email vacío'
                return
            
            # Validate email format
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_pattern, email_input.value):
                error_label.text = 'Por favor ingresa un correo electrónico válido'
                error_label.classes('text-negative text-center w-full mb-4')
                debug_label.text = 'Error: Formato de email inválido'
                return
            
            # Update debug label
            debug_label.text = f'Enviando solicitud a Firebase: {email_input.value}'
            
            try:
                # Attempt to send password reset email
                result = FirebaseAuth.reset_password(email_input.value)
                
                if result['success']:
                    # Show success message
                    success_label.text = 'Se ha enviado un link de recuperación a tu correo electrónico'
                    success_label.classes('text-positive text-center w-full mb-4')
                    debug_label.text = 'Solicitud enviada exitosamente, redirigiendo...'
                    
                    # Clear the email input
                    email_input.value = ''
                    
                    # Redirect to login page after a delay
                    ui.timer(3, lambda: ui.navigate.to('/login'))
                else:
                    # Show error message
                    error_msg = result.get('error', 'Error al enviar el correo de recuperación')
                    debug_label.text = f'Error de Firebase: {error_msg}'
                    
                    # Handle common Firebase errors
                    if 'EMAIL_NOT_FOUND' in error_msg:
                        error_msg = 'No se encontró ninguna cuenta con este correo electrónico'
                    
                    error_label.text = error_msg
                    error_label.classes('text-negative text-center w-full mb-4')
            except Exception as e:
                error_label.text = f"Error inesperado: {str(e)}"
                error_label.classes('text-negative text-center w-full mb-4')
                debug_label.text = f'Excepción: {str(e)}'
        
        # Connect button to handler
        reset_btn.on('click', on_reset_click)
