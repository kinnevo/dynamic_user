from nicegui import ui, app
from typing import Optional
import uuid
import os
from dotenv import load_dotenv
from utils.layouts import create_navigation_menu, create_navigation_menu_2
from utils.database import PostgresAdapter
from utils.langflow_client import LangflowClient
from utils.message_router import MessageRouter
from pages.reportes import reportes_page
# Import the chat page
from pages.chat import chat_page
from utils.state import logout, update_user_status

# Load environment variables if .env file exists
if os.path.exists('.env'):
    load_dotenv()

# Initialize database adapter and service components
db_adapter = PostgresAdapter()
langflow_client = LangflowClient()
message_router = MessageRouter()

@app.on_startup
def on_startup():
    """Application startup handler"""
    print("Starting up...")
    # Initialize database connection
    db_adapter._init_db()

@app.on_shutdown
def on_shutdown():
    """Application shutdown handler"""
    print("Shutting down...")

def get_user_logout() -> bool:
    """Check if user is logged out"""
    return False

# Initialize visit counter cookie
def get_visit_count() -> int:
    """Get visit count and initialize session if needed"""
    if ('visits' in app.storage.browser and get_user_logout() == True) or ('visits' not in app.storage.browser):
        # Initialize new session
        app.storage.browser['visits'] = 0
        app.storage.browser['session_id'] = str(uuid.uuid4())
        app.storage.browser['user_id'] = db_adapter.create_user(app.storage.browser['session_id'])
        
        # Set initial user status
        db_adapter.update_user_status(app.storage.browser['session_id'], "Idle")
    
    app.storage.browser['visits'] += 1
    return app.storage.browser['visits']

@ui.page('/')
def home():
    """Home page with navigation and basic user info"""
    create_navigation_menu_2()
    with ui.header().classes('items-center justify-between'):
        ui.label('Reto a resolver').classes('text-h3')
    
    with ui.row():
        ui.label('Usuario: jorge')
        visit_count = get_visit_count()
        ui.label(f'Visits: {visit_count}')
        ui.label(f'Logout: {logout}')

    # Navigation buttons
    ui.button('Ir a Reportes', on_click=lambda: ui.navigate.to('/reportes')).classes('bg-blue-500 text-white')
    # Add button to navigate to chat page
    ui.button('Chat con Langflow', on_click=lambda: ui.navigate.to('/chat')).classes('bg-green-500 text-white')

# Use a fixed secret key for development
secret_key = 'development_secret_key_1234567890'
ui.run(title='User Creation', port=8080, favicon='static/favicon.svg', storage_secret=secret_key) 
