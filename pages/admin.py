#!/usr/bin/env python3
import functools
from nicegui import ui
# Use the specific imports from your snippet
from utils.layouts import create_navigation_menu_2


# --- Dialog Definition ---
# Define the dialog structure once. It will be populated dynamically.
with ui.dialog() as user_dialog, ui.card().tight():
    dialog_title = ui.label('User Details').classes('text-h6 p-4 bg-primary text-white')
    with ui.column().classes('p-4'):
        dialog_content = ui.column()
    ui.button('Close', on_click=user_dialog.close).classes('m-4 self-end')

# --- Dialog Handler Function ---
def show_user_details(user_data):
    """Populates and opens the user detail dialog."""
    dialog_title.text = f"Details for User: {user_data.get('user_id', 'N/A')}"
    dialog_content.clear()
    with dialog_content:
        ui.label(f"User ID: {user_data.get('user_id', 'N/A')}")
        ui.label(f"Session ID: {user_data.get('session_id', 'N/A')}")
        ui.label(f"Logged Status: {user_data.get('logged', 'N/A')}")
        # Optional: Add database calls here if needed to fetch more details
    user_dialog.open()

# --- Main Page Definition ---
@ui.page('/admin')
def page_admin():
    # Create navigation using your function
    create_navigation_menu_2()

    # --- Main Content Area ---
    with ui.column().classes('w-full items-center p-4'):
        # Use the title from your snippet
        ui.label('FastInnovation Admin').classes('text-h4 q-mb-md')

        # --- Controls Row ---
        with ui.row().classes('w-full justify-end items-center mb-4'):
            # Refresh button - Use on_click method
            refresh_button = ui.button('Refresh', icon='refresh', on_click=lambda: update_table()).props('flat color=primary')

        # --- Table Definition ---
        # Define columns - using name=field convention for easier slot handling
        columns = [
            {'name': 'user_id', 'field': 'user_id', 'label': 'User ID', 'align': 'left', 'sortable': True},
            {'name': 'session_id', 'field': 'session_id', 'label': 'Session ID', 'align': 'left', 'sortable': True},
            {'name': 'logged', 'field': 'logged', 'label': 'Logged Status', 'align': 'center', 'sortable': True}
        ]

        # Create the table, defaulting to 25 rows per page
        table = ui.table(
            columns=columns,
            rows=[],
            pagination={'rowsPerPage': 25, 'page': 1} # Default to 25 rows
        ).classes('w-full').props(
            'flat bordered separator=cell pagination-rows-per-page-options=[10,25,50,100]'
        )

        # --- Table Slot for Clickable User ID ---
        table.add_slot('body-cell-user_id', r'''
            <td :props="props">
                <a href="#" @click="() => { console.log('props:', props); console.log('row:', props.row); $parent.show_user_details(props.row) }">{{props.row.user_id}}</a>
            </td>
        ''')
        
        # --- Data Update Function (Using your provided logic) ---
        def update_table():
            """Fetches user data from the database and updates the table rows."""
            conn = None # Initialize conn to None for the finally block
            print("DEBUG: update_table() called") # Optional debug
            try:
                # Use your database connection pool
                conn = user_db.connection_pool.getconn()
                cursor = conn.cursor()
                # Use your SQL query
                cursor.execute("SELECT user_id, session_id, logged FROM fi_users ORDER BY user_id") # Added ORDER BY
                rows = cursor.fetchall()
                print(f"DEBUG: Fetched {len(rows)} rows from database.") # Your debug print

                table_rows = []
                for row_tuple in rows: # Iterate through the tuples from fetchall
                    # Convert tuple to dictionary matching column fields
                    # This structure matches the user's snippet logic
                    table_rows.append({
                        'user_id': row_tuple[0],
                        'session_id': row_tuple[1],
                        'logged': 'Yes' if row_tuple[2] else 'No' # Convert boolean
                    })
                print(f"DEBUG: Processed {len(table_rows)} rows for NiceGUI table.") # Your debug print

                # Update the table component's rows
                table.rows = table_rows

            except Exception as e:
                print(f"ERROR in update_table: {e}") # Log error to console
                # Use your notification style
                ui.notify(f'Error loading users: {str(e)}', type='negative', position='top-right')
            finally:
                # Ensure connection is returned to the pool using your logic
                if conn:
                    try:
                        user_db.connection_pool.putconn(conn)
                    except Exception as pool_e:
                        print(f"ERROR putting connection back to pool: {pool_e}")


        # --- Initial Data Load ---
        # Populate the table when the page is first loaded
        update_table()

# --- No ui.run() here, as it's part of an existing app ---