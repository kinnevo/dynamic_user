import sqlite3
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.database_interface import DatabaseInterface

class SQLiteAdapter(DatabaseInterface):
    """
    SQLite implementation of the database interface
    """
    def __init__(self):
        # Use SQLite for now, with design for future PostgreSQL migration
        self.db_path = os.getenv("SQLITE_DB_PATH", "chatapp.db")
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'Idle',
                last_active TIMESTAMP,
                explorations_completed INTEGER DEFAULT 0,
                full_exploration BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                role TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO messages (session_id, user_id, content, role) VALUES (?, ?, ?, ?)",
            (session_id, user_id, content, role)
        )
        
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return message_id
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of message objects with role and content
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        
        rows = cursor.fetchall()
        history = [dict(row) for row in rows]
        conn.close()
        
        # Format history for Langflow
        formatted_history = []
        for msg in history:
            formatted_history.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            
        return formatted_history
    
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent messages for a session
        
        Args:
            session_id: Unique session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        
        rows = cursor.fetchall()
        recent_messages = [dict(row) for row in rows]
        conn.close()
        
        # Reverse to get chronological order
        recent_messages.reverse()
        
        return recent_messages
    
    def create_user(self, session_id: str) -> int:
        """
        Create a new user for a session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            user_id: ID of the created user
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO users (session_id, last_active) VALUES (?, ?)",
                (session_id, datetime.now().isoformat())
            )
            
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            # User already exists, get the ID
            cursor.execute("SELECT user_id FROM users WHERE session_id = ?", (session_id,))
            user_id = cursor.fetchone()[0]
            return user_id
        finally:
            conn.close()
    
    def get_user(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by session ID
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            User data dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_user_status(self, session_id: str, status: str) -> bool:
        """
        Update the status of a user
        
        Args:
            session_id: Unique session identifier
            status: New status value
            
        Returns:
            Success boolean
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE users SET status = ?, last_active = ? WHERE session_id = ?",
            (status, datetime.now().isoformat(), session_id)
        )
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success