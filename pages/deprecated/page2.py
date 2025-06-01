from nicegui import ui, app

@ui.page('/page2')
def page2():
    with ui.column().classes('w-full items-center'):
        ui.label('Página 2').classes('text-h4 q-mb-md')
        ui.button('Volver al inicio', on_click=lambda: ui.navigate.to('/')).classes('bg-blue-500 text-white')
