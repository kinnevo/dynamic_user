from nicegui import ui, app
import os
from dotenv import load_dotenv
from utils.database_singleton import get_db
from utils.filc_agent_client import FilcAgentClient
from utils.message_router import MessageRouter
from utils.firebase_auth import FirebaseAuth
from utils.auth_middleware import auth_required
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

# Initialize service components using singleton database
# Note: These are no longer needed at module level since they're instantiated locally where needed
# filc_client = FilcAgentClient()
# message_router = MessageRouter()

@app.on_startup
async def on_startup():
    """Application startup handler"""
    print("Starting up...")
    # Initialize database connection using singleton
    db_adapter = await get_db()
    print("Database adapter initialized successfully")


@app.on_shutdown
async def on_shutdown():
    """Application shutdown handler"""
    print("Shutting down...")
    # Close database connections properly
    from utils.database_singleton import DatabaseManager
    await DatabaseManager.reset_instance()

# Redirect root to authentication check
@ui.page('/')
def index():
    """Check if user is authenticated and redirect accordingly"""
    # Initialize user storage for this session if not already done
    if not hasattr(app.storage, 'user'):
        app.storage.user = {}
        
    user = FirebaseAuth.get_current_user()
    if user:
        # User is logged in, redirect to home
        return ui.navigate.to('/home')
    else:
        # User is not logged in, redirect to login page
        return ui.navigate.to('/login')

# Health endpoint for Cloud Run
@ui.page('/health')
def health():
    """Health check endpoint for Cloud Run"""
    with ui.element('div').style('text-align: center; padding: 20px;'):
        ui.label('Service is healthy').style('color: green; font-size: 18px;')
        ui.label(f'Environment: {os.environ.get("ENVIRONMENT", "development")}')
        ui.label(f'Cloud SQL: {"Enabled" if os.environ.get("USE_CLOUD_SQL") == "true" else "Disabled"}')

# Get port from environment variable (Cloud Run sets PORT)
port = int(os.environ.get('PORT', 8080))

# Get secret key from environment variable or use a default for development
secret_key = os.environ.get('STORAGE_SECRET', 'development_secret_key_1234567890')

ui.run(title='FastInnovation 1.2', port=port, host='0.0.0.0', favicon='static/favicon.png', storage_secret=secret_key) 
