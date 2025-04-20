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
                    CREATE TABLE IF NOT EXISTS fi_users (
                        user_id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL UNIQUE,
                        status TEXT DEFAULT 'Idle',
                        last_active TIMESTAMP,
                        explorations_completed INTEGER DEFAULT 0,
                        full_exploration BOOLEAN DEFAULT FALSE,
                        logged BOOLEAN DEFAULT FALSE
                    );
                    
                    CREATE TABLE IF NOT EXISTS fi_messages (
                        message_id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        role TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES fi_users(user_id)
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
                # First check if user exists by user_id
                with conn.cursor() as cursor:
                    cursor.execute("SELECT user_id, session_id FROM fi_users WHERE user_id = %s", (user_id,))
                    result = cursor.fetchone()
                    
                    # If user exists but has different session_id, use the found user's session_id
                    if result and result[1] != session_id:
                        print(f"User {user_id} found with different session_id, using existing session")
                        session_id = result[1]
                    
                    # If user doesn't exist, check if session exists with different user_id
                    if not result:
                        cursor.execute("SELECT user_id FROM fi_users WHERE session_id = %s", (session_id,))
                        session_result = cursor.fetchone()
                        
                        if session_result:
                            # Session exists, use that user_id
                            print(f"Session {session_id} exists with user_id {session_result[0]}, using existing user")
                            user_id = session_result[0]
                        else:
                            # Neither user nor session exists, create new user
                            print(f"Creating new user for session {session_id}")
                            cursor.execute(
                                "INSERT INTO fi_users (session_id, last_active, status) VALUES (%s, %s, %s) RETURNING user_id",
                                (session_id, datetime.now(), 'Active')
                            )
                            user_id = cursor.fetchone()[0]
                            conn.commit()
                    
                    # Update last_active time
                    cursor.execute(
                        "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                        (datetime.now(), user_id)
                    )
                    conn.commit()
                
                # Now save the message
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO fi_messages (session_id, user_id, content, role) VALUES (%s, %s, %s, %s) RETURNING message_id",
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
                    "SELECT * FROM fi_messages WHERE session_id = %s ORDER BY timestamp",
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
        Get recent fi_messages for a session
        
        Args:
            session_id: Unique session identifier
            limit: Maximum number of fi_messages to return
            
        Returns:
            List of recent fi_messages
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM fi_messages WHERE session_id = %s ORDER BY timestamp DESC LIMIT %s",
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
        Create a new user for a session or get existing user
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            user_id: ID of the created or existing user
        """
        conn = self.connection_pool.getconn()
        try:
            # First check if the session already exists
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM fi_users WHERE session_id = %s", (session_id,))
                result = cursor.fetchone()
                
                if result:
                    # Session exists, update last_active time
                    user_id = result[0]
                    print(f"Found existing user {user_id} for session {session_id}")
                    cursor.execute(
                        "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                        (datetime.now(), user_id)
                    )
                    conn.commit()
                    return user_id
                else:
                    # Session doesn't exist, create new user
                    try:
                        cursor.execute(
                            "INSERT INTO fi_users (session_id, last_active, status) VALUES (%s, %s, %s) RETURNING user_id",
                            (session_id, datetime.now(), 'Idle')
                        )
                        user_id = cursor.fetchone()[0]
                        print(f"Created new user {user_id} for session {session_id}")
                        conn.commit()
                        return user_id
                    except psycopg2.errors.UniqueViolation:
                        # This might happen in rare race conditions
                        conn.rollback()
                        cursor.execute("SELECT user_id FROM fi_users WHERE session_id = %s", (session_id,))
                        result = cursor.fetchone()
                        if result:
                            user_id = result[0]
                            cursor.execute(
                                "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                                (datetime.now(), user_id)
                            )
                            conn.commit()
                            return user_id
                        else:
                            # Generate a new unique session_id as fallback
                            import uuid
                            new_session_id = f"{session_id}-{str(uuid.uuid4())[:8]}"
                            print(f"Session collision, creating with new session_id: {new_session_id}")
                            cursor.execute(
                                "INSERT INTO fi_users (session_id, last_active, status) VALUES (%s, %s, %s) RETURNING user_id",
                                (new_session_id, datetime.now(), 'Idle')
                            )
                            user_id = cursor.fetchone()[0]
                            conn.commit()
                            return user_id
        except Exception as e:
            print(f"Error creating user: {e}")
            if 'conn' in locals():
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
                cursor.execute("SELECT * FROM fi_users WHERE session_id = %s", (session_id,))
                row = cursor.fetchone()
                
                if row:
                    # Update last active time
                    cursor.execute(
                        "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                        (datetime.now(), row['user_id'])
                    )
                    conn.commit()
                    return dict(row)
                
                # If no user is found with this session_id, check if there's a session
                # that matches part of this session_id (for generated fallback session IDs)
                if '-' in session_id:
                    base_session_id = session_id.split('-')[0]
                    cursor.execute("SELECT * FROM fi_users WHERE session_id LIKE %s", (f"{base_session_id}%",))
                    row = cursor.fetchone()
                    if row:
                        return dict(row)
                        
                return None
        except Exception as e:
            print(f"Error getting user: {e}")
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
            try:
                # First check if the user exists
                user = self.get_user(session_id)
                
                if not user:
                    # User doesn't exist, create one
                    user_id = self.create_user(session_id)
                    if user_id == -1:
                        return False
                    
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE fi_users SET status = %s, last_active = %s WHERE user_id = %s",
                            (status, datetime.now(), user_id)
                        )
                    conn.commit()
                    return True
                    
                else:
                    # User exists, update status
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE fi_users SET status = %s, last_active = %s WHERE user_id = %s",
                            (status, datetime.now(), user['user_id'])
                        )
                    conn.commit()
                    return True
            except Exception as e:
                print(f"Error updating user status: {e}")
                conn.rollback()
                return False
        finally:
            self.connection_pool.putconn(conn)


