from nicegui import ui, app
from utils.layouts import create_navigation_menu_2
from utils.database import user_db

@ui.page('/admin')
def page_admin():
    create_navigation_menu_2()

    with ui.column().classes('w-full items-center'):
        ui.label('FastInnovation Admin').classes('text-h4 q-mb-md')

        # --- Removed Filter Controls ---
        # Only keep the refresh button, perhaps center it or place it differently
        with ui.row().classes('w-full justify-end items-center'): # Changed justify-between to justify-end
            refresh_button = ui.button('Refresh', icon='refresh').props('flat color=primary')

        # Create table
        table = ui.table(rows=[], columns=[
            {'name': 'User ID', 'field': 'user_id', 'label': 'User ID', 'align': 'left', 'sortable': True},
            {'name': 'Session ID', 'field': 'session_id', 'label': 'Session ID', 'align': 'left', 'sortable': True},
            {'name': 'Logged Status', 'field': 'logged', 'label': 'Logged Status', 'align': 'center', 'sortable': True}
        ], pagination={'rowsPerPage': 5, 'page': 1} ).classes('w-full')

        def update_table():
            conn = None # Initialize conn to None for the finally block
            try:
                conn = user_db.connection_pool.getconn()
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, session_id, logged FROM fi_users")
                rows = cursor.fetchall()
                print(f"DEBUG: Fetched {len(rows)} rows from database.")


                table_rows = []
                for row in rows:
                    # --- Removed Filtering Logic ---
                    # Always add the row now
                    table_rows.append({
                        'user_id': row[0],
                        'session_id': row[1],
                        'logged': 'Yes' if row[2] else 'No'
                    })
                print(f"DEBUG: Processed {len(table_rows)} rows for NiceGUI table.")
                table.rows = table_rows
            except Exception as e:
                ui.notify(f'Error loading users: {str(e)}', type='negative')
            finally:
                # Ensure conn is not None before trying to put it back
                if conn:
                    user_db.connection_pool.putconn(conn)

        # Initial load
        update_table()

        # Update on button click
        refresh_button.on('click', update_table)
        # --- Removed Checkbox Event Handler ---