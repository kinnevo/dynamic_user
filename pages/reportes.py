from nicegui import ui, app
from utils.layouts import create_navigation_menu_2
from utils.database import PostgresAdapter
from utils.auth_middleware import auth_required
import plotly.graph_objects as go
from wordcloud import WordCloud
import nltk
import numpy as np
from nltk.corpus import stopwords

# Download NLTK stopwords (run once)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

@ui.page('/reportes')
@auth_required
def reportes_page():
    create_navigation_menu_2()
    db_adapter = PostgresAdapter()

    with ui.column().classes('w-full p-4'):
        ui.label('Reportes y Administración').classes('text-h4 q-mb-md')

        # Create tabs for different reports
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('Wordcloud de Conversaciones', icon='chat')
            ui.tab('Otros Reportes', icon='analytics')
        
        with ui.tab_panels(tabs, value='Wordcloud de Conversaciones').classes('w-full'):
            with ui.tab_panel('Wordcloud de Conversaciones'):
                ui.label('Visualización de Palabras Frecuentes').classes('text-h5 q-mb-sm')
                
                # Show current session ID
                current_session_id = app.storage.browser.get('session_id', None)
                if current_session_id:
                    ui.label(f"Sesión actual: {current_session_id}").classes('text-subtitle2 mb-2')
                else:
                    ui.label("No hay sesión activa").classes('text-subtitle2 mb-2 text-negative')
                
                # Create initial empty figure
                initial_fig = go.Figure()
                initial_fig.add_annotation(text="Genera un wordcloud usando el botón de abajo", 
                                         xref="paper", yref="paper",
                                         x=0.5, y=0.5, showarrow=False)
                initial_fig.update_layout(height=500)
                
                # Container for the wordcloud using Plotly - now with initial figure
                wordcloud_plot = ui.plotly(initial_fig).classes('w-full h-[500px] border rounded my-4')
                
                def generate_wordcloud():
                    # Get session ID directly from browser storage
                    session_id = app.storage.browser.get('session_id', None)
                    if not session_id:
                        ui.notify('No hay sesión activa', type='warning')
                        return
                    
                    # Get all messages for this session
                    messages = db_adapter.get_recent_messages(session_id, limit=1000)
                    
                    # Filter only user messages
                    user_messages = [msg for msg in messages if msg['role'] == 'user']
                    
                    if not user_messages:
                        fig = go.Figure()
                        fig.add_annotation(text="No se encontraron mensajes del usuario", 
                                          xref="paper", yref="paper",
                                          x=0.5, y=0.5, showarrow=False)
                        fig.update_layout(height=500)
                        wordcloud_plot.update_figure(fig)
                        return
                    
                    # Combine all user message content
                    all_text = " ".join([msg['content'] for msg in user_messages])
                    
                    # Get Spanish stopwords from NLTK
                    spanish_stopwords = set(stopwords.words('spanish'))
                    
                    # Add custom stopwords specific to your domain
                    custom_stopwords = {'quisiera', 'por', 'el', 'la', 'los', 'las', 'un', 'una', 'al', 'del'}
                    all_stopwords = spanish_stopwords.union(custom_stopwords)
                    
                    try:
                        # Generate wordcloud
                        wordcloud = WordCloud(
                            width=800, 
                            height=500,
                            background_color='white',
                            stopwords=all_stopwords,
                            colormap='viridis',
                            max_words=100,
                            collocations=True
                        ).generate(all_text)
                        
                        # Get the image array
                        wc_image = wordcloud.to_array()
                        
                        # Create a Plotly figure with the wordcloud image
                        fig = go.Figure(go.Image(z=wc_image))
                        
                        # Update layout for better display
                        fig.update_layout(
                            height=500,
                            margin=dict(l=0, r=0, t=0, b=0)
                        )
                        fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
                        fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False)
                        
                        # Update the plot
                        wordcloud_plot.update_figure(fig)
                        ui.notify('Wordcloud generado con éxito', type='positive')
                    except Exception as e:
                        ui.notify(f'Error al generar wordcloud: {str(e)}', type='negative')
                        print(f"Error: {str(e)}")
                
                # Button to generate the wordcloud
                ui.button('Generar Wordcloud', on_click=generate_wordcloud).props('color=primary')
                
                # Generate wordcloud on page load with current session
                ui.timer(0.5, generate_wordcloud, once=True)
                
            with ui.tab_panel('Otros Reportes'):
                ui.label('Aquí puedes agregar otros tipos de reportes').classes('text-h6 q-mt-md')