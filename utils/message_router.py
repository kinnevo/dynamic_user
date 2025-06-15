from typing import Dict, Any, List, Optional
import json
from utils.filc_agent_client import FilcAgentClient
from utils.firebase_auth import FirebaseAuth
import os
from datetime import datetime
import asyncio
import aiofiles
import time
from utils.database_singleton import get_db

class MessageRouter:
    """
    Routes messages between the UI and FILC Agent backend.
    Handles message processing, storage, and response extraction.
    Assumes user is identified by email and chats by session_id.
    """
    def __init__(self):
        # Database adapter will be initialized async in methods
        self.db_adapter = None
        
        # Initialize AI clients
        self.filc_client = FilcAgentClient()
    
    async def _get_db_adapter(self):
        """Get the async database adapter, initializing if needed"""
        if self.db_adapter is None:
            self.db_adapter = await get_db()
        return self.db_adapter
    
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
            
            # Track total processing time
            total_start_time = time.time()
            
            # Get async database adapter
            db_start = time.time()
            db_adapter = await self._get_db_adapter()
            db_init_time = int((time.time() - db_start) * 1000)
            
            # Get current user Firebase data
            current_user = FirebaseAuth.get_current_user()
            firebase_uid = current_user.get('uid') if current_user else None
            display_name = current_user.get('displayName') if current_user else None
            
            print(f"MessageRouter: User Firebase UID: {firebase_uid}, Display Name: {display_name}")
            
            # 🚀 PARALLEL PHASE 1: Operations that can run in parallel
            db_start = time.time()
            
            # Run these operations in parallel since they don't depend on each other
            save_user_task = db_adapter.save_message(
                user_email=user_email,
                session_id=session_id,
                content=message,
                role="user",
                firebase_uid=firebase_uid,
                display_name=display_name
            )
            
            history_task = db_adapter.get_conversation_history(session_id)
            
            status_update_task = db_adapter.update_user_status(
                identifier=user_email, 
                status="Active", 
                is_email=True
            )
            
            # Wait for all parallel operations to complete
            user_message_id, history, _ = await asyncio.gather(
                save_user_task,
                history_task,
                status_update_task
            )
            
            parallel_db_time = int((time.time() - db_start) * 1000)
            
            if not user_message_id:
                print(f"Error saving user message for {user_email} in chat {session_id}. Aborting.")
                return {"error": "Failed to save user message."}
            
            # 🎯 SEQUENTIAL PHASE: API call (needs history)
            api_start_time = time.time()
            response_from_agent = await self.filc_client.process_message(
                message=message,
                session_id=session_id,
                history=history
            )
            api_processing_time_ms = int((time.time() - api_start_time) * 1000)
            
            # Extract response text immediately
            response_text = self._extract_response_text(response_from_agent)
            
            # Calculate time up to user response
            user_response_time = int((time.time() - total_start_time) * 1000)
            
            # 🔥 BACKGROUND PHASE: Fire-and-forget operations after user gets response
            async def background_operations():
                """Run non-critical operations in background"""
                try:
                    bg_start = time.time()
                    
                    # Save assistant response and final status update in parallel
                    save_assistant_task = None
                    if response_text:
                        save_assistant_task = db_adapter.save_message(
                            user_email=user_email,
                            session_id=session_id,
                            content=response_text,
                            role="assistant",
                            firebase_uid=firebase_uid,
                            display_name=display_name,
                            model_used="FILC Agent",
                            processing_time=api_processing_time_ms
                        )
                    
                    final_status_task = db_adapter.update_user_status(
                        identifier=user_email, 
                        status="CompletedInteraction", 
                        is_email=True
                    )
                    
                    # Run background operations in parallel
                    if save_assistant_task:
                        await asyncio.gather(save_assistant_task, final_status_task)
                    else:
                        await final_status_task
                    
                    bg_time = int((time.time() - bg_start) * 1000)
                    print(f"🔥 Background operations completed in {bg_time}ms")
                    
                except Exception as e:
                    print(f"❌ Error in background operations: {e}")
            
            # Start background operations (fire-and-forget)
            asyncio.create_task(background_operations())
            
            # Log performance breakdown (only up to user response)
            print(f"⚡ Fast response performance (ms):")
            print(f"   User Response Time: {user_response_time}ms")
            print(f"   API Call: {api_processing_time_ms}ms ({api_processing_time_ms/user_response_time*100:.1f}%)")
            print(f"   Parallel DB Ops: {parallel_db_time}ms ({parallel_db_time/user_response_time*100:.1f}%)")
            print(f"   DB Init: {db_init_time}ms")
            print(f"   🔥 Background ops: Running async...")
            
            result = {
                "content": response_text if response_text else "No response content from assistant.",
                "raw_response": response_from_agent
            }
            
            if "error" in response_from_agent and response_text and not str(response_text).startswith("Error:"):
                result["error"] = response_from_agent.get("error")
                result["error_type"] = "non_critical"
                
            return result
            
        except Exception as e:
            print(f"MessageRouter: CRITICAL ERROR in process_user_message for {user_email}, chat {session_id}: {e}", flush=True)
            # Update user status to Failed (identified by email)
            try:
                db_adapter = await self._get_db_adapter()
                await db_adapter.update_user_status(identifier=user_email, status="FailedInteraction", is_email=True)
            except Exception as db_error:
                print(f"MessageRouter: Additional error updating user status: {db_error}")
            return {"error": f"An unexpected error occurred: {str(e)}"}
    
    async def process_user_message_stream(self, 
                                        message: str, 
                                        user_email: str, 
                                        session_id: str):
        """
        Process a user message with streaming response from FILC Agent.
        
        Args:
            message: User message text.
            user_email: Email of the user.
            session_id: Unique identifier for this specific chat session.
            
        Yields:
            Streaming response chunks with content and metadata.
        """
        try:
            print(f"MessageRouter Stream: Processing message from {user_email} for chat {session_id}: '{message[:50]}...'" )
            
            # Get async database adapter
            db_adapter = await self._get_db_adapter()
            
            # Get current user Firebase data
            current_user = FirebaseAuth.get_current_user()
            firebase_uid = current_user.get('uid') if current_user else None
            display_name = current_user.get('displayName') if current_user else None
            
            # Save user message first
            user_message_id = await db_adapter.save_message(
                user_email=user_email,
                session_id=session_id,
                content=message,
                role="user",
                firebase_uid=firebase_uid,
                display_name=display_name
            )
            
            if not user_message_id:
                yield {"error": "Failed to save user message.", "is_final": True}
                return
            
            # Get conversation history
            history = await db_adapter.get_conversation_history(session_id)
            
            # Update user status to active
            await db_adapter.update_user_status(
                identifier=user_email, 
                status="Active", 
                is_email=True
            )
            
            # Stream response from FILC Agent
            full_response = ""
            
            async for chunk in self.filc_client.process_message_stream(
                message=message,
                session_id=session_id,
                history=history
            ):
                if chunk.get("success"):
                    if chunk.get("is_chunk", False):
                        # Stream chunk to frontend
                        yield {
                            "content": chunk.get("content", ""),
                            "full_content": chunk.get("full_content", ""),
                            "is_chunk": True,
                            "success": True
                        }
                        full_response = chunk.get("full_content", "")
                    
                    elif chunk.get("is_final", False):
                        # Final chunk - save to database
                        full_response = chunk.get("content", "")
                        
                        # Save assistant response
                        if full_response:
                            await db_adapter.save_message(
                                user_email=user_email,
                                session_id=session_id,
                                content=full_response,
                                role="assistant",
                                firebase_uid=firebase_uid,
                                display_name=display_name,
                                model_used="FILC Agent Optimized"
                            )
                        
                        # Update user status
                        await db_adapter.update_user_status(
                            identifier=user_email, 
                            status="CompletedInteraction", 
                            is_email=True
                        )
                        
                        # Send final chunk
                        yield {
                            "content": full_response,
                            "full_content": full_response,
                            "is_final": True,
                            "success": True
                        }
                        break
                else:
                    # Error chunk
                    error_msg = chunk.get("error", "Unknown error")
                    
                    # Update user status to failed
                    await db_adapter.update_user_status(
                        identifier=user_email, 
                        status="FailedInteraction", 
                        is_email=True
                    )
                    
                    yield {
                        "error": error_msg,
                        "is_final": True,
                        "success": False
                    }
                    break
                    
        except Exception as e:
            print(f"MessageRouter Stream: CRITICAL ERROR for {user_email}, chat {session_id}: {e}")
            
            # Update user status to failed
            try:
                db_adapter = await self._get_db_adapter()
                await db_adapter.update_user_status(identifier=user_email, status="FailedInteraction", is_email=True)
            except Exception as db_error:
                print(f"MessageRouter Stream: Additional error updating user status: {db_error}")
            
            yield {
                "error": f"An unexpected error occurred: {str(e)}",
                "is_final": True,
                "success": False
            }
    
    def _extract_response_text(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract text from FILC Agent API response.
        """
        # print(f"MessageRouter._extract_response_text: Analyzing agent response: {json.dumps(response, indent=2)}")
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