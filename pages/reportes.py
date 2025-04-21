from nicegui import ui, app
from utils.layouts import create_navigation_menu
from utils.state import set_user_logout_state, get_user_logout_state
from utils.database import PostgresAdapter

@ui.page('/reportes')
def reportes_page():
    create_navigation_menu('/reportes')
    db_adapter = PostgresAdapter()

    with ui.column().classes('w-full p-4'):
        ui.label('Reportes y Administración').classes('text-h4 q-mb-md')

    session_id = "194e77d7-49af-41d1-b682-28a00d1de914"
    messages = db_adapter.get_recent_messages(session_id, limit=100)
    print(messages)
"""
    if messages:
        for message in messages:
            # Your message handling code here
"""