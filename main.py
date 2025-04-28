from nicegui import ui, app
import os
from dotenv import load_dotenv
from utils.database import PostgresAdapter
from utils.filc_agent_client import FilcAgentClient
from utils.message_router import MessageRouter
from pages.reportes import reportes_page
from pages.admin import page_admin
from pages.chat import chat_page
from pages.home import home

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

# Use a fixed secret key for development
secret_key = 'development_secret_key_1234567890'
ui.run(title='User Creation', port=8080, favicon='static/favicon.png', storage_secret=secret_key) 
