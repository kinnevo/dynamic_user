import asyncio
import aiohttp
from nicegui import ui
import os

class LangflowApp:
    def __init__(self):
        
        self.progress = ui.linear_progress(0).props('style="display: none;"')
        self.langflow_url = os.getenv("LANGFLOW_FLOW_ID", "http://localhost:7860/api/v1/process")
        
    async def setup_ui(self):
        ui.label("Langflow Process Execution").classes("text-2xl font-bold")
        
        with ui.row():
            self.input_text = ui.input("Input for Langflow").classes("w-full")
        
        with ui.row():
            ui.button("Process with Langflow", on_click=self.start_langflow_process)
            
        self.result_area = ui.markdown("Results will appear here")
        
    async def start_langflow_process(self):
        """Start the Langflow process with progress bar updates"""
        # Make progress bar visible
        self.progress.props('style="display: block;"')
        self.result_area.content = "Processing..."
        
        # Reset progress
        self.progress.value = 0
        
        try:
            # Start background task to handle Langflow API call
            result = await self.call_langflow_with_progress()
            self.result_area.content = f"## Result\n```\n{result}\n```"
        except Exception as e:
            self.result_area.content = f"Error - aqui: {str(e)}"
        finally:
            # Set progress to 100% and hide after a short delay
            self.progress.value = 1.0
            await asyncio.sleep(0.5)
            self.progress.props('style="display: none;"')
    
    async def call_langflow_with_progress(self):
        """Call Langflow API and update progress bar while waiting"""
        data = {
            "message": self.input_text.value,
            "flow_id": os.getenv("LANGFLOW_FLOW_ID"),
            "chat_id": None,
            "session_id": "ZZZZZ"
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        api_key = os.getenv("LANGFLOW_API_KEY")
        if api_key and api_key != "your-api-key-here":
            headers["x-api-key"] = api_key

        print("After API key")
        async with aiohttp.ClientSession() as session:
            async with session.post(self.langflow_url, json=data, headers=headers) as response:
                # If Langflow provides a streaming response or progress updates,
                # you could consume them here to update the progress bar more precisely
                print("SESSIONS: in call_langflow_with_progress 1")
                # For demonstration, we'll simulate progress updates
                total_steps = 20
                for step in range(total_steps):
                    # Update progress bar
                    self.progress.value = step / total_steps
                    # Small delay to simulate processing time and allow UI updates
                    await asyncio.sleep(0.1)
                
                print("in call_langflow_with_progress")
                # Get the final result
                if response.status == 200:
                    print("in call_langflow_with_progress 200")
                    result = await response.json()
                    return result
                else:
                    print("in call_langflow_with_progress else")
                    error_text = await response.text()
                    raise Exception(f"API call failed with status {response.status}: {error_text}")
            print("XXXXX")
        print("YYYYY")
    print("ZZZZZ")
print

@ui.page('/spinner1')
async def page_spinner1():
    app = LangflowApp()
    await app.setup_ui()

