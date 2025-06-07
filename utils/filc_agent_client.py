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
        
        self.chat_endpoint = "/api/v1/agent/chat"
        self.headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
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
    
    async def process_message(self, message: str, session_id: str, 
                              history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Send a message to the FILC Agent API and get a response"""
        # In this API we don't directly pass history but could use it to build context
        context = {"history": history} if history else {}
        
        payload = {
            "message": message,
            "session_id": session_id,
            "context": context
        }
        
        # print(f"FILC Agent: Sending payload to {self.base_url}{self.chat_endpoint}: {json.dumps(payload, indent=2)}")
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