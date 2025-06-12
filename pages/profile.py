from nicegui import ui, app
from utils.layouts import create_navigation_menu_2
from utils.auth_middleware import auth_required
from datetime import datetime, timedelta

@ui.page('/profile')
# @auth_required # TODO: Uncomment this when done debugging
async def profile_page():
    """User profile page with account information, usage statistics, and settings."""
    create_navigation_menu_2()
    
    # Mock user data (replace with actual DB calls later)
    user_data = {
        'name': 'Juan Pérez',
        'email': 'juan.perez@email.com',
        'avatar_url': 'https://via.placeholder.com/100x100?text=JP',
        'join_date': '2024-01-15',
        'last_login': '2024-06-12 14:30',
        'plan': 'Pro',
        'billing_cycle': 'Monthly',
        'next_billing': '2024-07-12',
        'conversations_count': 47,
        'messages_count': 234,
        'api_calls_count': 1289,
        'storage_used': 2.3, # GB
        'storage_limit': 10.0, # GB
    }
    
    usage_stats = {
        'this_month': {
            'conversations': 12,
            'messages': 68,
            'api_calls': 345
        },
        'last_month': {
            'conversations': 15,
            'messages': 82,
            'api_calls': 421
        }
    }
    
    plan_features = {
        'Pro': {
            'price': '$19.99/month',
            'features': [
                'Unlimited conversations',
                'Advanced AI models',
                'Priority support',
                '10GB storage',
                'API access',
                'Custom integrations'
            ],
            'limits': {
                'conversations': 'Unlimited',
                'messages': 'Unlimited',
                'api_calls': '10,000/month',
                'storage': '10GB'
            }
        }
    }

    # Header section
    with ui.header().classes('items-center justify-between bg-white shadow-sm'):
        with ui.row().classes('items-center gap-2'):
            ui.label('Mi Perfil').classes('text-h5 font-semibold')

    # Main content with responsive layout
    with ui.column().classes('w-full max-w-6xl mx-auto p-6 gap-6'):
        
        # Profile Header Card
        with ui.card().classes('w-full p-6'):
            with ui.row().classes('items-center gap-6'):
                # Avatar
                with ui.element('div').classes('relative'):
                    ui.image(user_data['avatar_url']).classes('w-24 h-24 rounded-full border-4 border-blue-200')
                    # Online status indicator
                    with ui.element('div').classes('absolute -bottom-1 -right-1 w-6 h-6 bg-green-500 border-2 border-white rounded-full'):
                        pass
                
                # User info
                with ui.column().classes('gap-1'):
                    ui.label(user_data['name']).classes('text-h4 font-bold text-gray-800')
                    ui.label(user_data['email']).classes('text-lg text-gray-600')
                    ui.label(f"Miembro desde {user_data['join_date']}").classes('text-sm text-gray-500')
                    ui.label(f"Último acceso: {user_data['last_login']}").classes('text-sm text-gray-500')
                
                # Quick actions
                with ui.column().classes('gap-2 ml-auto'):
                    ui.button('Editar Perfil', icon='edit').classes('bg-blue-500 text-white')
                    ui.button('Configuración', icon='settings').classes('bg-gray-500 text-white')

        # Stats Overview Row
        with ui.row().classes('w-full gap-6'):
            # Conversations stat
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.icon('chat', size='2xl').classes('text-blue-500 mb-2')
                ui.label(str(user_data['conversations_count'])).classes('text-h3 font-bold text-gray-800')
                ui.label('Conversaciones').classes('text-sm text-gray-600')
                
            # Messages stat  
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.icon('message', size='2xl').classes('text-green-500 mb-2')
                ui.label(str(user_data['messages_count'])).classes('text-h3 font-bold text-gray-800')
                ui.label('Mensajes').classes('text-sm text-gray-600')
                
            # API calls stat
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.icon('api', size='2xl').classes('text-purple-500 mb-2')
                ui.label(str(user_data['api_calls_count'])).classes('text-h3 font-bold text-gray-800')
                ui.label('Llamadas API').classes('text-sm text-gray-600')
                
            # Storage stat
            with ui.card().classes('flex-1 p-4 text-center'):
                ui.icon('storage', size='2xl').classes('text-orange-500 mb-2')
                ui.label(f"{user_data['storage_used']:.1f}GB").classes('text-h3 font-bold text-gray-800')
                ui.label(f"de {user_data['storage_limit']}GB").classes('text-sm text-gray-600')

        # Main content row
        with ui.row().classes('w-full gap-6'):
            # Left column
            with ui.column().classes('flex-1 gap-6'):
                
                # Current Plan Card
                with ui.card().classes('w-full'):
                    with ui.card_section():
                        ui.label('Plan Actual').classes('text-h6 font-semibold mb-4')
                        
                        with ui.row().classes('items-center justify-between mb-4'):
                            with ui.column().classes('gap-1'):
                                ui.label(f"Plan {user_data['plan']}").classes('text-h5 font-bold text-blue-600')
                                ui.label(plan_features[user_data['plan']]['price']).classes('text-lg text-gray-700')
                                ui.label(f"Facturación {user_data['billing_cycle'].lower()}").classes('text-sm text-gray-500')
                            
                            ui.badge('ACTIVO', color='green').classes('text-white px-3 py-1')
                        
                        # Plan features
                        ui.label('Características incluidas:').classes('text-sm font-semibold text-gray-700 mb-2')
                        for feature in plan_features[user_data['plan']]['features']:
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.icon('check_circle', size='sm').classes('text-green-500')
                                ui.label(feature).classes('text-sm text-gray-600')
                        
                        with ui.row().classes('gap-2 mt-4'):
                            ui.button('Cambiar Plan', icon='upgrade').classes('bg-blue-500 text-white')
                            ui.button('Administrar Facturación', icon='payment').classes('bg-gray-500 text-white')

                # Usage Statistics Card
                with ui.card().classes('w-full'):
                    with ui.card_section():
                        ui.label('Estadísticas de Uso').classes('text-h6 font-semibold mb-4')
                        
                        # Usage comparison
                        with ui.row().classes('gap-6'):
                            with ui.column().classes('flex-1'):
                                ui.label('Este Mes').classes('text-sm font-semibold text-gray-700 mb-2')
                                ui.label(f"📞 {usage_stats['this_month']['conversations']} conversaciones").classes('text-sm text-gray-600')
                                ui.label(f"💬 {usage_stats['this_month']['messages']} mensajes").classes('text-sm text-gray-600')
                                ui.label(f"🔗 {usage_stats['this_month']['api_calls']} llamadas API").classes('text-sm text-gray-600')
                            
                            with ui.column().classes('flex-1'):
                                ui.label('Mes Anterior').classes('text-sm font-semibold text-gray-700 mb-2')
                                ui.label(f"📞 {usage_stats['last_month']['conversations']} conversaciones").classes('text-sm text-gray-600')
                                ui.label(f"💬 {usage_stats['last_month']['messages']} mensajes").classes('text-sm text-gray-600')
                                ui.label(f"🔗 {usage_stats['last_month']['api_calls']} llamadas API").classes('text-sm text-gray-600')
                        
                        # Storage usage bar
                        storage_percentage = (user_data['storage_used'] / user_data['storage_limit']) * 100
                        ui.label('Almacenamiento').classes('text-sm font-semibold text-gray-700 mt-4 mb-2')
                        with ui.element('div').classes('w-full bg-gray-200 rounded-full h-3'):
                            with ui.element('div').classes(f'bg-blue-500 h-3 rounded-full').style(f'width: {storage_percentage}%'):
                                pass
                        ui.label(f'{user_data["storage_used"]}GB de {user_data["storage_limit"]}GB utilizados ({storage_percentage:.1f}%)').classes('text-xs text-gray-500 mt-1')

            # Right column  
            with ui.column().classes('flex-1 gap-6'):
                
                # Payment Information Card
                with ui.card().classes('w-full'):
                    with ui.card_section():
                        ui.label('Información de Pago').classes('text-h6 font-semibold mb-4')
                        
                        # Payment method
                        with ui.row().classes('items-center gap-3 mb-4'):
                            ui.icon('credit_card', size='lg').classes('text-blue-500')
                            with ui.column().classes('gap-1'):
                                ui.label('•••• •••• •••• 4532').classes('text-sm font-mono text-gray-700')
                                ui.label('Visa terminada en 4532').classes('text-xs text-gray-500')
                        
                        # Billing info
                        with ui.column().classes('gap-2'):
                            with ui.row().classes('justify-between'):
                                ui.label('Próxima facturación:').classes('text-sm text-gray-600')
                                ui.label(user_data['next_billing']).classes('text-sm font-semibold text-gray-800')
                            
                            with ui.row().classes('justify-between'):
                                ui.label('Estado:').classes('text-sm text-gray-600')
                                ui.badge('Al día', color='green').classes('text-white text-xs')
                        
                        ui.button('Actualizar método de pago', icon='edit').classes('bg-blue-500 text-white w-full mt-4')

                # Plan Limits Card
                with ui.card().classes('w-full'):
                    with ui.card_section():
                        ui.label('Límites del Plan').classes('text-h6 font-semibold mb-4')
                        
                        limits = plan_features[user_data['plan']]['limits']
                        for limit_name, limit_value in limits.items():
                            with ui.row().classes('justify-between items-center mb-2'):
                                ui.label(limit_name.replace('_', ' ').title()).classes('text-sm text-gray-600')
                                ui.label(limit_value).classes('text-sm font-semibold text-gray-800')
                        
                        ui.button('Ver detalles completos', icon='info').classes('bg-gray-500 text-white w-full mt-4')

                # Quick Actions Card
                with ui.card().classes('w-full'):
                    with ui.card_section():
                        ui.label('Acciones Rápidas').classes('text-h6 font-semibold mb-4')
                        
                        with ui.column().classes('gap-2'):
                            ui.button('📥 Exportar datos', icon='download').classes('bg-gray-500 text-white w-full text-left justify-start')
                            ui.button('🔄 Sincronizar cuenta', icon='sync').classes('bg-blue-500 text-white w-full text-left justify-start')
                            ui.button('🗑️ Eliminar cuenta', icon='delete').classes('bg-red-500 text-white w-full text-left justify-start')
                            ui.button('📞 Contactar soporte', icon='support').classes('bg-green-500 text-white w-full text-left justify-start')

        # Activity Timeline (recent activity)
        with ui.card().classes('w-full'):
            with ui.card_section():
                ui.label('Actividad Reciente').classes('text-h6 font-semibold mb-4')
                
                recent_activities = [
                    {'time': '2 horas', 'action': 'Nueva conversación iniciada', 'icon': 'chat', 'color': 'blue'},
                    {'time': '1 día', 'action': 'Plan actualizado a Pro', 'icon': 'upgrade', 'color': 'green'},
                    {'time': '3 días', 'action': 'Perfil actualizado', 'icon': 'edit', 'color': 'orange'},
                    {'time': '1 semana', 'action': 'Pago procesado exitosamente', 'icon': 'payment', 'color': 'green'},
                ]
                
                for activity in recent_activities:
                    with ui.row().classes('items-center gap-3 mb-3'):
                        ui.icon(activity['icon'], size='sm').classes(f'text-{activity["color"]}-500')
                        with ui.column().classes('gap-0'):
                            ui.label(activity['action']).classes('text-sm text-gray-700')
                            ui.label(f'Hace {activity["time"]}').classes('text-xs text-gray-500')
