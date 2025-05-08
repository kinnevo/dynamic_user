from nicegui import ui, app
import os
from dotenv import load_dotenv
from utils.database import PostgresAdapter
from utils.filc_agent_client import FilcAgentClient
from utils.message_router import MessageRouter
from utils.firebase_auth import FirebaseAuth
from pages.reportes import reportes_page
from pages.admin import page_admin
from pages.chat import chat_page
from pages.home import home
from pages.login import login_page
from pages.register import register_page
from pages.reset_password import reset_password_page

# Load environment variables if .env file exists
if os.path.exists('.env'):
    load_dotenv()

# Initialize database adapter and service components
# The database adapter is also initialized in home.py for user session tracking
db_adapter = PostgresAdapter()
filc_client = FilcAgentClient()
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

# Redirect root to home page
@ui.page('/')
def index():
    """Redirect to home page"""
    return ui.navigate.to('/home')

# Initialize user storage at the application level
@app.on_startup
def init_user_storage():
    """Initialize the user storage for Firebase authentication"""
    # This ensures we have a place to store user data in the session
    if not hasattr(app.storage, 'user'):
        app.storage.user = {}

# Use a fixed secret key for development
secret_key = 'development_secret_key_1234567890'
ui.run(title='FastInnovation 1.2', port=8080, favicon='static/favicon.png', storage_secret=secret_key) 
