from typing import Dict, Any, List, Optional
import json
from utils.filc_agent_client import FilcAgentClient
from utils.database import PostgresAdapter

class MessageRouter:
    """
    Routes messages between the UI and FILC Agent backend.
    Handles message processing, storage, and response extraction.
    Assumes user is identified by email and chats by chat_session_id.
    """
    def __init__(self):
        self.filc_client = FilcAgentClient()
        self.db_adapter = PostgresAdapter()
    
    async def process_user_message(self, 
                                 message: str, 
                                 user_email: str, 
                                 chat_session_id: str) -> Dict[str, Any]:
        """
        Process a user message, store it, get a response from FILC Agent, and store response.
        
        Args:
            message: User message text.
            user_email: Email of the user.
            chat_session_id: Unique identifier for this specific chat session.
            
        Returns:
            Response data with content and raw response, or an error.
        """
        try:
            # Save user message to database.
            # user_id will be resolved by save_message via get_or_create_user_by_email.
            user_message_id = self.db_adapter.save_message(
                user_email=user_email,
                chat_session_id=chat_session_id,
                content=message,
                role="user"
            )
            if not user_message_id:
                print(f"Error saving user message for {user_email} in chat {chat_session_id}. Aborting.")
                return {"error": "Failed to save user message."}
            
            # Get conversation history for context, using the chat_session_id
            history = self.db_adapter.get_conversation_history(chat_session_id)
            
            # Update user status to Active (identified by email)
            self.db_adapter.update_user_status(identifier=user_email, status="Active", is_email=True)
            
            # Send to FILC Agent API
            # Note: filc_client.process_message might also need to be updated if it expects an old session_id model
            response_from_agent = await self.filc_client.process_message(
                message=message,
                session_id=chat_session_id, # Assuming filc_client uses this as a context/history key
                history=history
                # Potentially pass user_email or a user identifier if filc_client needs it
            )
            
            # Extract response text
            response_text = self._extract_response_text(response_from_agent)
            
            # Save assistant response to database
            if response_text:
                self.db_adapter.save_message(
                    user_email=user_email,
                    chat_session_id=chat_session_id,
                    content=response_text,
                    role="assistant"
                )
            else:
                # Handle cases where response_text might be empty or None from _extract_response_text
                print(f"No valid response text extracted from agent for chat {chat_session_id}. Not saving assistant message.")
            
            # Update user status (e.g., "Completed" could mean completed this interaction cycle)
            self.db_adapter.update_user_status(identifier=user_email, status="CompletedInteraction", is_email=True)
            
            result = {
                "content": response_text if response_text else "No response content from assistant.",
                "raw_response": response_from_agent
            }
            
            if "error" in response_from_agent and response_text and not str(response_text).startswith("Error:"):
                result["error"] = response_from_agent.get("error")
                result["error_type"] = "non_critical"
                
            return result
            
        except Exception as e:
            print(f"Error in MessageRouter.process_user_message for {user_email}, chat {chat_session_id}: {e}")
            # Update user status to Failed (identified by email)
            self.db_adapter.update_user_status(identifier=user_email, status="FailedInteraction", is_email=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
    
    def _extract_response_text(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract text from FILC Agent API response.
        """
        if not isinstance(response, dict):
            print(f"Warning: Agent response is not a dict: {response}")
            return str(response) # Or handle more gracefully

        if "error" in response:
            return f"Error from agent: {response['error']}"
        
        # Adjusted to check for content and success, common in API responses
        # This part depends heavily on the actual structure of filc_client responses
        content = response.get("content")
        success = response.get("success", True) # Assume success if not specified, but content must exist

        if content is not None: # Check for None specifically, as empty string can be valid
            if success:
                return str(content)
            else:
                return f"Agent indicated failure but provided content: {str(content)}"
        
        # Fallback if content is None
        return "No meaningful content in agent response."