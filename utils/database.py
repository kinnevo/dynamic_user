import os
from datetime import datetime
import pytz
from typing import Optional, Dict, Any, List
from nicegui import app
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv
from utils.database_interface import DatabaseInterface

# Set up San Francisco (Pacific Time) timezone
sf_timezone = pytz.timezone('America/Los_Angeles')

def get_sf_time():
    """Get current time in San Francisco timezone"""
    return datetime.now(pytz.utc).astimezone(sf_timezone)

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
                                (session_id, get_sf_time(), 'Active')
                            )
                            user_id = cursor.fetchone()[0]
                            conn.commit()
                    
                    # Update last_active time
                    cursor.execute(
                        "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                        (get_sf_time(), user_id)
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
                            (session_id, get_sf_time(), 'Idle')
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
                                (get_sf_time(), user_id)
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
                                (new_session_id, get_sf_time(), 'Idle')
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
                        (get_sf_time(), row['user_id'])
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
                            (status, get_sf_time(), user_id)
                        )
                    conn.commit()
                    return True
                    
                else:
                    # User exists, update status
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE fi_users SET status = %s, last_active = %s WHERE user_id = %s",
                            (status, get_sf_time(), user['user_id'])
                        )
                    conn.commit()
                    return True
            except Exception as e:
                print(f"Error updating user status: {e}")
                conn.rollback()
                return False
        finally:
            self.connection_pool.putconn(conn)
            
    def get_conversations_by_date_and_users(self, start_date: str, start_hour: int, 
                                           end_date: str, end_hour: int, 
                                           user_ids: list = None) -> List[Dict[str, Any]]:
        """
        Fetch conversations based on date range and user selection
        
        Args:
            start_date: Start date in format 'YYYY-MM-DD'
            start_hour: Start hour (0-23)
            end_date: End date in format 'YYYY-MM-DD'
            end_hour: End hour (0-23)
            user_ids: List of user IDs to filter by, or None for all users
            
        Returns:
            List of conversation data grouped by session_id
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Construct datetime strings for start and end with SF timezone
                # Parse input dates and convert to SF timezone
                try:
                    # Convert string dates to proper datetime objects with SF timezone
                    start_dt = datetime.strptime(f"{start_date} {start_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
                    start_dt = sf_timezone.localize(start_dt)
                    
                    end_dt = datetime.strptime(f"{end_date} {end_hour:02d}:59:59", "%Y-%m-%d %H:%M:%S") 
                    end_dt = sf_timezone.localize(end_dt)
                    
                    # Format for database query
                    start_datetime = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                    end_datetime = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError as e:
                    print(f"Error parsing dates: {e}")
                    # Fallback to simple string construction
                    start_datetime = f"{start_date} {start_hour:02d}:00:00"
                    end_datetime = f"{end_date} {end_hour:02d}:59:59"
                
                # Base query to get all messages within the date range
                query = """
                    SELECT 
                        m.message_id, 
                        m.session_id, 
                        m.user_id, 
                        m.content, 
                        m.role, 
                        m.timestamp,
                        u.session_id as user_session_id
                    FROM 
                        fi_messages m
                    JOIN
                        fi_users u ON m.user_id = u.user_id
                    WHERE 
                        m.timestamp BETWEEN %s AND %s
                """
                params = [start_datetime, end_datetime]
                
                # Add user filtering if specific users were selected
                if user_ids and 'all' not in user_ids:
                    # Handle different types of user_ids input
                    int_user_ids = []
                    for uid in user_ids:
                        # Try to convert to int if it's a string digit
                        if isinstance(uid, str) and uid.isdigit():
                            int_user_ids.append(int(uid))
                        # Already an int
                        elif isinstance(uid, int):
                            int_user_ids.append(uid)
                    
                    # Only add the filter if we have valid user IDs
                    if int_user_ids:
                        placeholders = ','.join(['%s'] * len(int_user_ids))
                        query += f" AND m.user_id IN ({placeholders})"
                        params.extend(int_user_ids)
                
                # Add ordering
                query += " ORDER BY m.session_id, m.timestamp"
                
                # Execute the query
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Group messages by conversation (session_id)
                conversations = {}
                for row in rows:
                    session_id = row['session_id']
                    
                    if session_id not in conversations:
                        conversations[session_id] = {
                            'session_id': session_id,
                            'user_id': row['user_id'],
                            'user_session_id': row['user_session_id'],
                            'start_time': row['timestamp'],
                            'end_time': row['timestamp'],
                            'message_count': 0,
                            'messages': []
                        }
                    
                    # Update conversation metadata
                    conversations[session_id]['message_count'] += 1
                    conversations[session_id]['end_time'] = max(conversations[session_id]['end_time'], row['timestamp'])
                    
                    # Add message to the conversation
                    conversations[session_id]['messages'].append({
                        'message_id': row['message_id'],
                        'content': row['content'],
                        'role': row['role'],
                        'timestamp': row['timestamp']
                    })
                
                # Convert dictionary to list
                return list(conversations.values())
                
        except Exception as e:
            print(f"Error fetching conversations: {e}")
            return []
        finally:
            self.connection_pool.putconn(conn)


