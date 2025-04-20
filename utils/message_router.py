from typing import Dict, Any, List, Optional
import json
from utils.langflow_client import LangflowClient
from utils.database import PostgresAdapter

class MessageRouter:
    """
    Routes messages between the UI and Langflow backend
    Handles message processing, storage, and response extraction
    """
    def __init__(self):
        self.langflow_client = LangflowClient()
        self.db_adapter = PostgresAdapter()
    
    async def process_user_message(self, 
                                 message: str, 
                                 session_id: str, 
                                 user_id: int) -> Dict[str, Any]:
        """
        Process a user message through Langflow and store in database
        
        Args:
            message: User message text
            session_id: Unique session identifier
            user_id: User ID associated with the message
            
        Returns:
            Response data with content and raw response
        """
        try:
            # Ensure user exists before saving messages
            user = self.db_adapter.get_user(session_id)
            if not user:
                # Create user if not exists
                user_id = self.db_adapter.create_user(session_id)
            
            # Save user message to database
            self.db_adapter.save_message(
                session_id=session_id,
                user_id=user_id,
                content=message,
                role="user"
            )
            
            # Get conversation history for context
            history = self.db_adapter.get_conversation_history(session_id)
            
            # Update user status
            self.db_adapter.update_user_status(session_id, "Active")
            
            # Send to Langflow
            response = await self.langflow_client.process_message(
                message=message,
                session_id=session_id,
                history=history
            )
            
            # Extract response text
            response_text = self._extract_response_text(response)
            
            # Save assistant response to database
            if response_text:
                self.db_adapter.save_message(
                    session_id=session_id,
                    user_id=user_id,
                    content=response_text,
                    role="assistant"
                )
            
            # Update user status
            self.db_adapter.update_user_status(session_id, "Completed")
            
            result = {
                "content": response_text,
                "raw_response": response
            }
            
            # If we have an error but also got a valid response, include both
            # This helps the UI distinguish between critical and non-critical errors
            if "error" in response and response_text and not response_text.startswith("Error:"):
                result["error"] = response.get("error")
                result["error_type"] = "non_critical"
                
            return result
        except Exception as e:
            # Update user status on error
            self.db_adapter.update_user_status(session_id, "Failed")
            return {"error": str(e)}
    
    def _extract_response_text(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract text from Langflow response
        
        Args:
            response: Raw response from Langflow API
            
        Returns:
            Extracted text content or error message
        """
        # Handle error responses with detailed information
        if "error" in response:
            error_message = response["error"]
            
            # If we have status and suggestions, format a more helpful error message
            if "status" in response and "suggestions" in response:
                suggestions = "\n• " + "\n• ".join(response["suggestions"])
                return f"Error: {error_message}\n\nTroubleshooting suggestions:{suggestions}"
            
            return f"Error: {error_message}"
        
        # Based on Workshop_full format
        if "outputs" in response and len(response["outputs"]) > 0:
            try:
                return response["outputs"][0]["outputs"][0]["results"]["message"]["text"]
            except (KeyError, IndexError) as e:
                print(f"Failed to parse output format 1: {str(e)}")
        
        # Alternative format
        if "result" in response:
            result = response["result"]
            if isinstance(result, dict) and "message" in result:
                return result["message"]["text"]
            return str(result)
        
        # Debug output format
        print(f"Response format not recognized. Keys: {', '.join(response.keys())}")
            
        # Fallback
        return str(response.get("output", "No response"))