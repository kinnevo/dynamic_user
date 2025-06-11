from nicegui import ui, app
from utils.database_singleton import get_db
from utils.layouts import create_navigation_menu_2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from wordcloud import WordCloud
import pandas as pd
from collections import Counter
import re
from utils.auth_middleware import auth_required
import nltk
import numpy as np
from nltk.corpus import stopwords
from datetime import datetime

# Download NLTK stopwords (run once)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

@ui.page('/reportes')
@auth_required 
async def reportes_page():
    # Initialize async database adapter inside function
    db_adapter = await get_db()
    
    create_navigation_menu_2()

    with ui.column().classes('w-full p-4'):
        ui.label('Reportes y Administración').classes('text-h4 q-mb-md')

        # Create tabs for different reports
        with ui.tabs().classes('w-full') as tabs:
            ui.tab('Wordcloud de Conversaciones', icon='chat')
            ui.tab('Otros Reportes', icon='analytics')
        
        with ui.tab_panels(tabs, value='Wordcloud de Conversaciones').classes('w-full'):
            with ui.tab_panel('Wordcloud de Conversaciones'):
                ui.label('Visualización de Palabras Frecuentes').classes('text-h5 q-mb-sm')
                
                # Get user email for session filtering
                user_email = app.storage.user.get('user_email')
                if not user_email:
                    ui.label("Error: Usuario no autenticado").classes('text-negative')
                    return

                # Get all chat sessions for the user
                chat_sessions = await db_adapter.get_chat_sessions_for_user(user_email)
                
                if not chat_sessions:
                    ui.label("No hay conversaciones disponibles para analizar").classes('text-orange-600 mb-4')
                    return

                # Create session selector
                def format_session_label(session):
                    """Format session for dropdown display"""
                    preview = session.get('first_message_content', 'Sin mensajes')
                    if preview and len(preview) > 50:
                        preview = preview[:50] + "..."
                    
                    # Format timestamp
                    timestamp = session.get('last_message_timestamp')
                    if timestamp:
                        if isinstance(timestamp, str):
                            try:
                                dt_obj = datetime.fromisoformat(timestamp)
                                time_str = dt_obj.strftime("%Y-%m-%d %H:%M")
                            except ValueError:
                                time_str = timestamp
                        else:
                            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
                    else:
                        time_str = "Fecha desconocida"
                    
                    return f"{preview} ({time_str})"

                # Prepare session options for dropdown
                session_options = {}
                for session in chat_sessions:
                    session_id = session['session_id']
                    label = format_session_label(session)
                    session_options[label] = session_id

                # Default to first session
                default_session_label = list(session_options.keys())[0] if session_options else None
                
                # Session selector dropdown
                ui.label('Selecciona una conversación:').classes('text-subtitle1 mb-2')
                session_selector = ui.select(
                    options=session_options,
                    value=default_session_label,  # Use the label as value, not the session_id
                    label='Conversación'
                ).classes('w-full max-w-md mb-4')

                # Show selected session info
                session_info = ui.label().classes('text-subtitle2 mb-4 text-blue-600')
                
                async def update_session_info():
                    if session_selector.value and session_selector.value in session_options:
                        # Get the actual session_id from the selected label
                        selected_session_id = session_options[session_selector.value]
                        selected_session = next(
                            (s for s in chat_sessions if s['session_id'] == selected_session_id), 
                            None
                        )
                        if selected_session:
                            messages = await db_adapter.get_recent_messages(selected_session_id, limit=1000)
                            message_count = len(messages)
                            session_info.text = f"Sesión seleccionada: {selected_session_id[:8]}... | Total mensajes: {message_count}"
                        else:
                            session_info.text = "Sesión no encontrada"
                    else:
                        session_info.text = "Ninguna sesión seleccionada"

                # Update info when selection changes - wrap async function for ui callback
                def on_session_change():
                    import asyncio
                    asyncio.create_task(update_session_info())
                    
                session_selector.on_value_change(lambda: on_session_change())
                
                # Initial session info update
                await update_session_info()
                
                # Create initial empty figure
                initial_fig = go.Figure()
                initial_fig.add_annotation(text="Selecciona una conversación y genera un wordcloud usando el botón de abajo", 
                                         xref="paper", yref="paper",
                                         x=0.5, y=0.5, showarrow=False)
                initial_fig.update_layout(height=500)
                
                # Container for the wordcloud using Plotly - now with initial figure
                wordcloud_plot = ui.plotly(initial_fig).classes('w-full h-[500px] border rounded my-4')
                
                async def generate_wordcloud():
                    # Get selected session ID from dropdown (convert label to session_id)
                    if not session_selector.value or session_selector.value not in session_options:
                        print('⚠️ Por favor selecciona una conversación')  # Use print instead of ui.notify
                        return
                    
                    selected_session_id = session_options[session_selector.value]
                    
                    # Get all messages for selected session
                    messages = await db_adapter.get_recent_messages(selected_session_id, limit=1000)
                    
                    # Filter only user messages
                    user_messages = [msg for msg in messages if msg['role'] == 'user']
                    
                    if not user_messages:
                        fig = go.Figure()
                        fig.add_annotation(text="No se encontraron mensajes del usuario en esta conversación", 
                                          xref="paper", yref="paper",
                                          x=0.5, y=0.5, showarrow=False)
                        fig.update_layout(height=500)
                        wordcloud_plot.update_figure(fig)
                        print('ℹ️ No hay mensajes del usuario en esta conversación')  # Use print instead of ui.notify
                        return
                    
                    # Combine all user message content
                    all_text = " ".join([msg['content'] for msg in user_messages])
                    
                    if len(all_text.strip()) < 10:
                        fig = go.Figure()
                        fig.add_annotation(text="No hay suficiente texto para generar un wordcloud", 
                                          xref="paper", yref="paper",
                                          x=0.5, y=0.5, showarrow=False)
                        fig.update_layout(height=500)
                        wordcloud_plot.update_figure(fig)
                        print('ℹ️ No hay suficiente texto para generar un wordcloud')  # Use print instead of ui.notify
                        return
                    
                    # Get Spanish stopwords from NLTK
                    spanish_stopwords = set(stopwords.words('spanish'))
                    
                    # Add custom stopwords specific to your domain
                    custom_stopwords = {'quisiera', 'por', 'el', 'la', 'los', 'las', 'un', 'una', 'al', 'del', 'que', 'como', 'para', 'con', 'en', 'de', 'y', 'a', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'ya', 'me', 'mi', 'muy', 'sin', 'sobre', 'también', 'hasta', 'hay', 'donde', 'han', 'este', 'esta', 'esto', 'ese', 'esa', 'esos', 'esas'}
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
                            collocations=False,  # Avoid repeated phrases
                            relative_scaling=0.5,
                            min_font_size=10
                        ).generate(all_text)
                        
                        # Check if wordcloud was generated successfully
                        if not wordcloud.words_:
                            fig = go.Figure()
                            fig.add_annotation(text="No se pudieron extraer palabras significativas", 
                                              xref="paper", yref="paper",
                                              x=0.5, y=0.5, showarrow=False)
                            fig.update_layout(height=500)
                            wordcloud_plot.update_figure(fig)
                            print('ℹ️ No se pudieron extraer palabras significativas')  # Use print instead of ui.notify
                            return
                        
                        # Get the image array
                        wc_image = wordcloud.to_array()
                        
                        # Create a Plotly figure with the wordcloud image
                        fig = go.Figure(go.Image(z=wc_image))
                        
                        # Update layout for better display
                        fig.update_layout(
                            title=f"Wordcloud - Conversación {selected_session_id[:8]}...",
                            height=500,
                            margin=dict(l=0, r=0, t=30, b=0)
                        )
                        fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
                        fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False)
                        
                        # Update the plot
                        wordcloud_plot.update_figure(fig)
                        print(f'✅ Wordcloud generado con éxito para la conversación seleccionada ({len(user_messages)} mensajes)')  # Use print instead of ui.notify
                    except Exception as e:
                        print(f'❌ Error al generar wordcloud: {str(e)}')  # Use print instead of ui.notify
                        print(f"Error: {str(e)}")
                
                # Button to generate the wordcloud - wrap async function for ui callback
                def on_generate_click():
                    import asyncio
                    asyncio.create_task(generate_wordcloud())
                    
                ui.button('Generar Wordcloud', on_click=on_generate_click).props('color=primary size=lg').classes('mb-4')
                
                # Auto-generate wordcloud on page load with first session
                if session_selector.value and session_selector.value in session_options:
                    import asyncio
                    asyncio.create_task(generate_wordcloud())
                
            with ui.tab_panel('Otros Reportes'):
                ui.label('Espera pronto más reportes para ti.').classes('text-h6 q-mt-md')
                
                # Example of other potential reports
                with ui.card().classes('w-full p-4 mt-4'):
                    ui.label('Estadísticas Generales').classes('text-h6 mb-2')
                    
                    user_email = app.storage.user.get('user_email')
                    if user_email:
                        chat_sessions = await db_adapter.get_chat_sessions_for_user(user_email)
                        total_conversations = len(chat_sessions)
                        
                        # Calculate total messages across all conversations
                        total_messages = 0
                        for session in chat_sessions:
                            messages = await db_adapter.get_recent_messages(session['session_id'], limit=1000)
                            total_messages += len(messages)
                        
                        ui.label(f'Total de conversaciones: {total_conversations}').classes('mb-1')
                        ui.label(f'Total de mensajes: {total_messages}').classes('mb-1')
                        if total_conversations > 0:
                            avg_messages = total_messages / total_conversations
                            ui.label(f'Promedio de mensajes por conversación: {avg_messages:.1f}').classes('mb-1')