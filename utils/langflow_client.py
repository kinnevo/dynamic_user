import requests
import os
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

load_dotenv()

class LangflowClient:
    """
    Client for interacting with Langflow API
    
    Implemented as a singleton to prevent multiple initializations.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LangflowClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if self._initialized:
            return
            
        self.base_url = os.getenv("LANGFLOW_API_URL")
        # Remove trailing slash if present
        if self.base_url.endswith('/'):
            self.base_url = self.base_url[:-1]
            
        self.flow_id = os.getenv("LANGFLOW_FLOW_ID")
        self.api_key = os.getenv("LANGFLOW_API_KEY")
        self.headers = {"Content-Type": "application/json"}
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.connection_status = "unknown"
        
        if self.api_key and self.api_key != "your-api-key-here":
            self.headers["x-api-key"] = self.api_key
            
        print(f"Initialized Langflow client for: {self.base_url}")
        print(f"Using flow ID: {self.flow_id}")
        
        # Run a background health check
        self.check_connection()
        
        self._initialized = True
        
    def check_connection(self) -> Tuple[bool, str]:
        """
        Check if the Langflow API is reachable
        
        Returns:
            Tuple of (is_connected, status_message)
        """
        try:
            # Try to hit the health endpoint if it exists, otherwise just try to reach the server
            health_url = f"{self.base_url}/api/v1/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                self.connection_status = "connected"
                return True, "Connected to Langflow API"
                
            # If health endpoint is not found or returns non-200, try base endpoint
            base_response = requests.get(self.base_url, timeout=5)
            if base_response.status_code in [200, 404]:  # 404 is ok for base endpoint if API is at a subpath
                self.connection_status = "connected"
                return True, "Connected to Langflow server"
                
            self.connection_status = "error"
            return False, f"Server responded with status code: {response.status_code}"
            
        except requests.exceptions.ConnectTimeout:
            self.connection_status = "timeout"
            return False, f"Connection timeout: Could not connect to {self.base_url}"
            
        except requests.exceptions.ConnectionError:
            self.connection_status = "unreachable"
            return False, f"Connection error: Could not reach {self.base_url}"
            
        except Exception as e:
            self.connection_status = "error"
            return False, f"Error checking connection: {str(e)}"
    
    async def process_message(self, 
                             message: str, 
                             session_id: str, 
                             history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Send a message to Langflow API for processing
        
        Args:
            message: The user's message
            session_id: Unique session identifier
            history: Optional conversation history
            
        Returns:
            Response from Langflow API
        """
        # Use either the run endpoint with flow_id or a direct endpoint
        if self.flow_id:
            api_url = f"{self.base_url}/api/v1/run/{self.flow_id}"
        else:
            api_url = f"{self.base_url}/api/v1/process"
            
        # Prepare payload
        payload = {
            "input_value": message,
            "output_type": "chat",
            "input_type": "chat",
            "session_id": session_id
        }
        
        # Include flow_id for process endpoint if available
        if not self.flow_id and "process" in api_url:
            flow_id = os.getenv("LANGFLOW_FLOW_ID")
            if flow_id:
                payload["flow_id"] = flow_id
        
        # Include conversation history if provided
        if history and len(history) > 0:
            payload["conversation_history"] = json.dumps(history)
            
        print(f"Sending request to Langflow API: {api_url}")
            
        # Initialize retry counter
        retries = 0
        last_error = None
        
        # Retry loop
        while retries < self.max_retries:
            try:
                # Add timeout parameters to prevent hanging requests
                # Increase timeout values for potential network latency
                response = requests.post(
                    api_url, 
                    json=payload,
                    headers=self.headers,
                    timeout=(10, 120)  # 10 seconds for connection, 120 seconds for read
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.ConnectTimeout as e:
                last_error = f"Connection timeout ({retries+1}/{self.max_retries}): Could not establish connection to {self.base_url}. The server might be down or unreachable."
                print(last_error)
            
            except requests.exceptions.ReadTimeout as e:
                last_error = f"Read timeout ({retries+1}/{self.max_retries}): The server took too long to respond. It might be processing a complex request or under heavy load."
                print(last_error)
                
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error ({retries+1}/{self.max_retries}): Could not connect to Langflow API. Please check if the API server is running and accessible."
                print(last_error)
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else "unknown"
                last_error = f"HTTP error {status_code} ({retries+1}/{self.max_retries}): The server returned an error status."
                print(last_error)
                
                # No retry for 4xx errors (client errors)
                if status_code and 400 <= status_code < 500:
                    return {"error": f"Client error: {str(e)}"}
                
            except requests.exceptions.RequestException as e:
                last_error = f"Request error ({retries+1}/{self.max_retries}): {str(e)}"
                print(last_error)
                
            except json.JSONDecodeError:
                last_error = f"Invalid JSON response ({retries+1}/{self.max_retries}): The server returned a response that couldn't be parsed as JSON."
                print(last_error)
                
            except Exception as e:
                last_error = f"Unexpected error ({retries+1}/{self.max_retries}): {str(e)}"
                print(last_error)
            
            # Increase retry count and delay before retry
            retries += 1
            if retries < self.max_retries:
                # Exponential backoff
                wait_time = self.retry_delay * (2 ** (retries - 1))
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        # If we've exhausted retries, return the error
        return {
            "error": f"Failed after {self.max_retries} attempts. Last error: {last_error}",
            "status": "connection_failed",
            "suggestions": [
                f"Verify that the Langflow server at {self.base_url} is running",
                "Check network connectivity to the server",
                f"Ensure the flow_id '{self.flow_id}' is correct and the flow is deployed",
                "Try increasing timeouts or max retries if the server is under heavy load"
            ]
        }