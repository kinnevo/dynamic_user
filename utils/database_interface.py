from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class DatabaseInterface(ABC):
    """
    Abstract interface for database operations
    Provides a common interface that can be implemented for different database backends
    """
    
    @abstractmethod
    def save_message(self, session_id: str, user_id: int, content: str, role: str) -> int:
        """
        Save a message to the database
        
        Args:
            session_id: Unique session identifier
            user_id: User ID associated with the message
            content: Message content
            role: Message role (user or assistant)
            
        Returns:
            message_id: ID of the saved message
        """
        pass
    
    @abstractmethod
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of message objects with role and content
        """
        pass
    
    @abstractmethod
    def create_user(self, session_id: str) -> int:
        """
        Create a new user for a session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            user_id: ID of the created user
        """
        pass
    
    @abstractmethod
    def get_user(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by session ID
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            User data dictionary or None if not found
        """
        pass
    
    @abstractmethod
    def update_user_status(self, session_id: str, status: str) -> bool:
        """
        Update the status of a user
        
        Args:
            session_id: Unique session identifier
            status: New status value
            
        Returns:
            Success boolean
        """
        pass
    
    @abstractmethod
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent messages for a session
        
        Args:
            session_id: Unique session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        pass