import aiohttp
import asyncio
import json
import os
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional, Tuple

# Load environment variables
load_dotenv(override=True)

def get_filc_api_url():
    """Get the FILC API URL based on environment configuration."""
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Strip comments and whitespace from environment variable
    if environment:
        environment = environment.split('#')[0].strip().lower()
    else:
        environment = "development"
    
    if environment == "production":
        return os.getenv("FILC_API_URL_PRODUCTION", "https://filc-production.up.railway.app")
    else:
        return os.getenv("FILC_API_URL_LOCAL", "http://localhost:3000")

class FilcAgentClient:
    """Client for interacting with the FILC Agent API"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        # Use environment variable if no base_url is provided
        self.base_url = base_url or get_filc_api_url()
        
        # Use environment variable if no api_key is provided
        self.api_key = api_key or os.getenv("FILC_API_KEY")
        
        self.chat_endpoint = "/api/v1/agent/chat/optimized"
        self.chat_stream_endpoint = "/api/v1/agent/chat/stream/optimized"
        api_key = os.getenv('FILC_API_KEY')
        if not api_key:
            raise ValueError("FILC_API_KEY environment variable is required")
        self.headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        }
        
        # Add API key to headers if available
        if self.api_key:
            self.headers['X-API-Key'] = self.api_key
        
        self.connection_status = "unknown"  # Added for UI compatibility
        
        print(f"FILC Agent Configuration:")
        print(f"  Environment: {os.getenv('ENVIRONMENT', 'development')}")
        parsed_env = os.getenv("ENVIRONMENT", "development").split('#')[0].strip().lower() if os.getenv("ENVIRONMENT") else "development"
        print(f"  Parsed Environment: {parsed_env}")
        print(f"  API Base URL: {self.base_url}")
        print(f"  API Key configured: {'Yes' if self.api_key else 'No'}")
        
        if not self.api_key:
            print("WARNING: FILC_API_KEY not found in environment variables. API calls may fail if the service requires authentication.")
        
    async def check_connection(self) -> Tuple[bool, str]:
        """Check if the API is reachable"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v1/health", 
                                       headers=self.headers,
                                       timeout=10) as response:
                    if response.status == 200:
                        self.connection_status = "connected"
                        return True, "Connected successfully"
                    else:
                        self.connection_status = "error"
                        return False, f"API returned status code {response.status}"
        except asyncio.TimeoutError:
            self.connection_status = "timeout"
            return False, "Connection timed out"
        except Exception as e:
            self.connection_status = "error"
            return False, f"Connection error: {str(e)}"
    
    async def process_message_stream(self, message: str, session_id: str, 
                                   history: List[Dict[str, str]] = None):
        """Send a message and get a streaming response from the FILC Agent API"""
        # Prepare the same payload as process_message
        payload = {
            "message": message,
            "session_id": session_id,
            "context": {}
        }
        
        # Handle conversation history (same logic as process_message)
        if history and len(history) > 0:
            conversation_history = []
            for msg in history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    conversation_history.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            if conversation_history:
                payload["conversation_history"] = conversation_history
                print(f"FILC Agent Stream: Using provided conversation history with {len(conversation_history)} messages")
        
        elif history is not None and len(history) == 0:
            try:
                from utils.database_singleton import get_db
                db_adapter = await get_db()
                
                existing_history = await db_adapter.get_conversation_history(session_id)
                
                if existing_history and len(existing_history) > 0:
                    last_messages = existing_history[-10:] if len(existing_history) > 10 else existing_history
                    
                    conversation_history = []
                    for msg in last_messages:
                        if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            conversation_history.append({
                                "role": msg['role'],
                                "content": msg['content']
                            })
                    
                    if conversation_history:
                        payload["conversation_history"] = conversation_history
                        print(f"FILC Agent Stream: Retrieved and using last {len(conversation_history)} messages from DB")
                else:
                    print(f"FILC Agent Stream: New conversation detected")
                    
            except Exception as e:
                print(f"FILC Agent Stream: Warning - Could not fetch conversation history from DB: {e}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{self.chat_stream_endpoint}",
                    headers=self.headers,
                    json=payload,
                    timeout=60
                ) as response:
                    if response.status == 200:
                        self.connection_status = "connected"
                        
                        # Stream the response
                        full_response = ""
                        async for line in response.content:
                            if line:
                                try:
                                    # Decode the line
                                    line_text = line.decode('utf-8').strip()
                                    
                                    # Skip empty lines
                                    if not line_text:
                                        continue
                                    
                                    # Handle Server-Sent Events format
                                    if line_text.startswith('data: '):
                                        data_part = line_text[6:]  # Remove 'data: ' prefix
                                        
                                        # Skip [DONE] marker
                                        if data_part == '[DONE]':
                                            break
                                        
                                        try:
                                            # Parse JSON chunk
                                            chunk_data = json.loads(data_part)
                                            # The API returns 'chunk' field, not 'content'
                                            chunk_text = chunk_data.get('chunk', '')
                                            is_finished = chunk_data.get('finished', False)
                                            
                                            # Always yield chunks, even if content is empty (for final chunk)
                                            if chunk_text or is_finished:
                                                if chunk_text:
                                                    full_response += chunk_text
                                                
                                                # Yield each chunk for real-time streaming
                                                yield {
                                                    "content": chunk_text,
                                                    "full_content": full_response,
                                                    "success": True,
                                                    "is_chunk": not is_finished,
                                                    "is_final": is_finished
                                                }
                                            
                                            # If finished, break the loop
                                            if is_finished:
                                                break
                                        except json.JSONDecodeError:
                                            # If not JSON, treat as plain text chunk
                                            if data_part:
                                                full_response += data_part
                                                yield {
                                                    "content": data_part,
                                                    "full_content": full_response,
                                                    "success": True,
                                                    "is_chunk": True
                                                }
                                    
                                except UnicodeDecodeError:
                                    continue
                        
                        # Stream is complete - final chunk was already sent with finished=true
                        pass
                        
                    else:
                        self.connection_status = "error"
                        error_text = await response.text()
                        yield {
                            "error": f"API Error (Status {response.status}): {error_text}",
                            "success": False,
                            "is_final": True
                        }
                        
        except asyncio.TimeoutError:
            self.connection_status = "timeout"
            yield {
                "error": "Request timed out",
                "success": False,
                "is_final": True
            }
        except Exception as e:
            self.connection_status = "error"
            yield {
                "error": f"Request failed: {str(e)}",
                "success": False,
                "is_final": True
            }
    
    async def process_message(self, message: str, session_id: str, 
                              history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Send a message to the FILC Agent API and get a response"""
        # Prepare the payload with proper conversation_history format
        payload = {
            "message": message,
            "session_id": session_id,
            "context": {}
        }
        
        # Handle conversation history
        if history and len(history) > 0:
            # Use provided history and format it correctly for the API
            conversation_history = []
            for msg in history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    conversation_history.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            if conversation_history:
                payload["conversation_history"] = conversation_history
                print(f"FILC Agent: Using provided conversation history with {len(conversation_history)} messages")
        
        elif history is not None and len(history) == 0:
            # History was explicitly passed as empty, check if this is an existing conversation
            # that might need history from the database
            try:
                from utils.database_singleton import get_db
                db_adapter = await get_db()
                
                # Check if this session has any previous messages
                existing_history = await db_adapter.get_conversation_history(session_id)
                
                if existing_history and len(existing_history) > 0:
                    # This is an existing conversation, get last 10 messages for context
                    last_messages = existing_history[-10:] if len(existing_history) > 10 else existing_history
                    
                    conversation_history = []
                    for msg in last_messages:
                        if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            conversation_history.append({
                                "role": msg['role'],
                                "content": msg['content']
                            })
                    
                    if conversation_history:
                        payload["conversation_history"] = conversation_history
                        print(f"FILC Agent: Retrieved and using last {len(conversation_history)} messages from DB for existing conversation")
                else:
                    print(f"FILC Agent: New conversation detected, no history added")
                    
            except Exception as e:
                print(f"FILC Agent: Warning - Could not fetch conversation history from DB: {e}")
                # Continue without history - this is not a critical error
        
        # If no history was provided at all (None), this is likely a new conversation
        # and we don't need to add conversation_history
        
        # print(f"FILC Agent: Sending payload to {self.base_url}{self.chat_endpoint}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{self.chat_endpoint}",
                    headers=self.headers,
                    json=payload,
                    timeout=60  # Same timeout as original script
                ) as response:
                    response_status = response.status
                    # print(f"FILC Agent: Received status code {response_status}")
                    if response.status == 200:
                        self.connection_status = "connected"
                        result = await response.json()
                        # print(f"FILC Agent: Received JSON response: {json.dumps(result, indent=2)}")
                        # Assuming the API returns a response with content field
                        # Adjust this based on the actual API response structure
                        return {"content": result.get("response", ""), "success": True}
                    else:
                        self.connection_status = "error"
                        error_text = await response.text()
                        return {"error": f"API Error (Status {response.status}): {error_text}", "success": False}
        except asyncio.TimeoutError:
            self.connection_status = "timeout"
            return {"error": "Request timed out", "success": False}
        except Exception as e:
            self.connection_status = "error"
            return {"error": f"Request failed: {str(e)}", "success": False}