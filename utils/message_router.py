from typing import Dict, Any, List, Optional
import json
from utils.filc_agent_client import FilcAgentClient
from utils.unified_database import UnifiedDatabaseAdapter
from utils.firebase_auth import FirebaseAuth
import openai
import os
from datetime import datetime
import asyncio
import aiofiles
import time

class MessageRouter:
    """
    Routes messages between the UI and FILC Agent backend.
    Handles message processing, storage, and response extraction.
    Assumes user is identified by email and chats by session_id.
    """
    def __init__(self):
        self.filc_client = FilcAgentClient()
        self.db_adapter = UnifiedDatabaseAdapter()
    
    async def process_user_message(self, 
                                 message: str, 
                                 user_email: str, 
                                 session_id: str) -> Dict[str, Any]:
        """
        Process a user message, store it, get a response from FILC Agent, and store response.
        
        Args:
            message: User message text.
            user_email: Email of the user.
            session_id: Unique identifier for this specific chat session.
            
        Returns:
            Response data with content and raw response, or an error.
        """
        try:
            print(f"MessageRouter: Processing message from {user_email} for chat {session_id}: '{message[:50]}...'" ) # Log entry
            
            # Get current user Firebase data
            current_user = FirebaseAuth.get_current_user()
            firebase_uid = current_user.get('uid') if current_user else None
            display_name = current_user.get('displayName') if current_user else None
            
            print(f"MessageRouter: User Firebase UID: {firebase_uid}, Display Name: {display_name}")
            
            # Save user message to database with Firebase UID and display name
            user_message_id = self.db_adapter.save_message(
                user_email=user_email,
                session_id=session_id,
                content=message,
                role="user",
                firebase_uid=firebase_uid,
                display_name=display_name
            )
            if not user_message_id:
                print(f"Error saving user message for {user_email} in chat {session_id}. Aborting.")
                return {"error": "Failed to save user message."}
            # print(f"MessageRouter: User message saved with ID: {user_message_id}")
            
            # Get conversation history for context, using the session_id
            history = self.db_adapter.get_conversation_history(session_id)
            # print(f"MessageRouter: Fetched history for chat {session_id}. Number of messages: {len(history)}")
            
            # Update user status to Active (identified by email)
            self.db_adapter.update_user_status(identifier=user_email, status="Active", is_email=True)
            
            # Send to FILC Agent API and track processing time
            start_time = time.time()
            # print(f"MessageRouter: Calling FilcAgentClient.process_message for chat {session_id}")
            response_from_agent = await self.filc_client.process_message(
                message=message,
                session_id=session_id, # Assuming filc_client uses this as a context/history key
                history=history
                # Potentially pass user_email or a user identifier if filc_client needs it
            )
            processing_time_ms = int((time.time() - start_time) * 1000)  # Convert to milliseconds
            # print(f"MessageRouter: Received response from agent: {json.dumps(response_from_agent, indent=2)}")
            
            # Extract response text
            response_text = self._extract_response_text(response_from_agent)
            # print(f"MessageRouter: Extracted response text: '{response_text}'")
            
            # Save assistant response to database with Firebase UID and processing time
            if response_text:
                assistant_message_id = self.db_adapter.save_message(
                    user_email=user_email,
                    session_id=session_id,
                    content=response_text,
                    role="assistant",
                    firebase_uid=firebase_uid,
                    display_name=display_name,
                    model_used="FILC Agent",  # Specify the model used
                    processing_time=processing_time_ms
                )
                # print(f"MessageRouter: Assistant response saved with ID: {assistant_message_id}")
            else:
                # Handle cases where response_text might be empty or None from _extract_response_text
                print(f"No valid response text extracted from agent for chat {session_id}. Not saving assistant message.")
            
            # Update user status (e.g., "Completed" could mean completed this interaction cycle)
            self.db_adapter.update_user_status(identifier=user_email, status="CompletedInteraction", is_email=True)
            
            result = {
                "content": response_text if response_text else "No response content from assistant.",
                "raw_response": response_from_agent
            }
            
            if "error" in response_from_agent and response_text and not str(response_text).startswith("Error:"):
                result["error"] = response_from_agent.get("error")
                result["error_type"] = "non_critical"
                
            # print(f"MessageRouter: Successfully processed. Returning to UI: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            print(f"MessageRouter: CRITICAL ERROR in process_user_message for {user_email}, chat {session_id}: {e}", flush=True)
            # Update user status to Failed (identified by email)
            self.db_adapter.update_user_status(identifier=user_email, status="FailedInteraction", is_email=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
    
    def _extract_response_text(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract text from FILC Agent API response.
        """
        print(f"MessageRouter._extract_response_text: Analyzing agent response: {json.dumps(response, indent=2)}")
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