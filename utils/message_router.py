from typing import Dict, Any, List, Optional
import json
from utils.filc_agent_client import FilcAgentClient  # Changed from LangflowClient
from utils.database import PostgresAdapter

class MessageRouter:
    """
    Routes messages between the UI and FILC Agent backend
    Handles message processing, storage, and response extraction
    """
    def __init__(self):
        # Use FilcAgentClient instead of LangflowClient
        self.filc_client = FilcAgentClient()
        self.db_adapter = PostgresAdapter()
    
    async def process_user_message(self, 
                                 message: str, 
                                 session_id: str, 
                                 user_id: int) -> Dict[str, Any]:
        """
        Process a user message through FILC Agent API and store in database
        
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
            
            # Send to FILC Agent API
            response = await self.filc_client.process_message(
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
        Extract text from FILC Agent API response
        
        Args:
            response: Raw response from FILC Agent API
            
        Returns:
            Extracted text content or error message
        """
        # Handle error responses
        if "error" in response:
            return f"Error: {response['error']}"
        
        # Handle success responses from FILC Agent API
        if "content" in response and response.get("success", False):
            return response["content"]
        
        # Fallback
        return str(response.get("content", "No response"))