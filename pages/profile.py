from nicegui import ui
from utils.layouts import create_navigation_menu_2

@ui.page('/profile')
async def profile_page():
    """Profile page with text display and input functionality"""
    create_navigation_menu_2()
    
    with ui.header().classes('items-center justify-between'):
        ui.label('Profile Page').classes('text-h3')
    
    # Main content container
    with ui.column().classes('w-full p-4 gap-4'):
        # Text display area with automatic scrolling
        text_display = ui.textarea('').classes('w-full h-[40vh] overflow-y-auto').props('readonly')
        
        # Input area and button
        with ui.row().classes('w-full items-center gap-2'):
            message_input = ui.input(placeholder='Type your message...').classes('flex-grow')
            
            async def add_message():
                if not message_input.value:
                    return
                
                # Get current text and append new message
                current_text = text_display.value
                new_text = f"{current_text}\n{message_input.value}" if current_text else message_input.value
                text_display.value = new_text
                
                # Clear input
                message_input.value = ''
                
                # Scroll to bottom with error handling
                try:
                    await ui.run_javascript('''
                        const textarea = document.querySelector("textarea");
                        if (textarea) {
                            textarea.scrollTop = textarea.scrollHeight;
                        }
                    ''', timeout=5.0)  # Increased timeout to 5 seconds
                except Exception as e:
                    print(f"Error scrolling: {e}")  # Log the error but don't break the function
            
            # Button to add message
            ui.button('Add Message', on_click=add_message).props('flat')
            
            # Also allow sending with Enter key
            message_input.on('keydown.enter', add_message)
    
    # Initialize with some example text
    text_display.value = "Welcome to your profile page!\n\nThis is a text display area that will automatically scroll when new content is added."
    
    # Scroll to bottom on initial load with error handling
    try:
        await ui.run_javascript('''
            const textarea = document.querySelector("textarea");
            if (textarea) {
                textarea.scrollTop = textarea.scrollHeight;
            }
        ''', timeout=5.0)  # Increased timeout to 5 seconds
    except Exception as e:
        print(f"Error scrolling on initial load: {e}")  # Log the error but don't break the function
