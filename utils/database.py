import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from nicegui import app
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv
from utils.database_interface import DatabaseInterface

load_dotenv()

class PostgresAdapter(DatabaseInterface):
    def __init__(self):
        self.connection_pool = self._create_connection_pool()
        self._init_db()

    def _create_connection_pool(self):
        """Create a connection pool for PostgreSQL."""
        return SimpleConnectionPool(
            1,  # minconn
            20,  # maxconn
            host=os.getenv('POSTGRES_HOST'),
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )

    def __del__(self):
        """Clean up the connection pool when the object is destroyed."""
        if hasattr(self, 'connection_pool'):
            self.connection_pool.closeall()

    def _init_db(self):
        """Initialize the database with the required tables."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL UNIQUE,
                        status TEXT DEFAULT 'Idle',
                        last_active TIMESTAMP,
                        explorations_completed INTEGER DEFAULT 0,
                        full_exploration BOOLEAN DEFAULT FALSE
                    );
                    
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        role TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    );
                ''')
            conn.commit()
        finally:
            self.connection_pool.putconn(conn)
    
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
        conn = self.connection_pool.getconn()
        try:
            try:
                # First check if user exists
                with conn.cursor() as cursor:
                    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
                    result = cursor.fetchone()
                    
                    # If user doesn't exist, create a new one
                    if not result:
                        print(f"User {user_id} not found, creating new user for session {session_id}")
                        cursor.execute(
                            "INSERT INTO users (user_id, session_id, last_active, status) VALUES (%s, %s, %s, %s)",
                            (user_id, session_id, datetime.now(), 'Active')
                        )
                        conn.commit()
                
                # Now save the message
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO messages (session_id, user_id, content, role) VALUES (%s, %s, %s, %s) RETURNING message_id",
                        (session_id, user_id, content, role)
                    )
                    message_id = cursor.fetchone()[0]
                conn.commit()
                return message_id
            except Exception as e:
                conn.rollback()
                print(f"Error saving message: {e}")
                raise
        finally:
            self.connection_pool.putconn(conn)
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of message objects with role and content
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM messages WHERE session_id = %s ORDER BY timestamp",
                    (session_id,)
                )
                rows = cursor.fetchall()
                history = [dict(row) for row in rows]
                
                # Format history for Langflow
                formatted_history = []
                for msg in history:
                    formatted_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                    
                return formatted_history
        finally:
            self.connection_pool.putconn(conn)
    
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent messages for a session
        
        Args:
            session_id: Unique session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM messages WHERE session_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (session_id, limit)
                )
                rows = cursor.fetchall()
                recent_messages = [dict(row) for row in rows]
                
                # Reverse to get chronological order
                recent_messages.reverse()
                
                return recent_messages
        finally:
            self.connection_pool.putconn(conn)
    
    def create_user(self, session_id: str) -> int:
        """
        Create a new user for a session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            user_id: ID of the created user
        """
        conn = self.connection_pool.getconn()
        try:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (session_id, last_active, status) VALUES (%s, %s, %s) RETURNING user_id",
                        (session_id, datetime.now(), 'Idle')
                    )
                    user_id = cursor.fetchone()[0]
                conn.commit()
                return user_id
            except psycopg2.errors.UniqueViolation:
                # User already exists, get the ID
                conn.rollback()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT user_id FROM users WHERE session_id = %s", (session_id,))
                    result = cursor.fetchone()
                    if result:
                        user_id = result[0]
                        # Update last_active time
                        cursor.execute(
                            "UPDATE users SET last_active = %s WHERE user_id = %s",
                            (datetime.now(), user_id)
                        )
                        conn.commit()
                        return user_id
                    else:
                        # This should not happen, but just in case
                        cursor.execute(
                            "INSERT INTO users (session_id, last_active, status) VALUES (%s, %s, %s) RETURNING user_id",
                            (session_id, datetime.now(), 'Idle')
                        )
                        user_id = cursor.fetchone()[0]
                        conn.commit()
                        return user_id
            except Exception as e:
                print(f"Error creating user: {e}")
                conn.rollback()
                return -1
        finally:
            self.connection_pool.putconn(conn)
    
    def get_user(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by session ID
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            User data dictionary or None if not found
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM users WHERE session_id = %s", (session_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
        finally:
            self.connection_pool.putconn(conn)
    
    def update_user_status(self, session_id: str, status: str) -> bool:
        """
        Update the status of a user
        
        Args:
            session_id: Unique session identifier
            status: New status value
            
        Returns:
            Success boolean
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET status = %s, last_active = %s WHERE session_id = %s",
                    (status, datetime.now(), session_id)
                )
                success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            self.connection_pool.putconn(conn)