import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import pytz
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from utils.database_interface import DatabaseInterface

# Set up timezone
sf_timezone = pytz.timezone('America/Los_Angeles')

def get_sf_time():
    """Get current time in San Francisco timezone"""
    return datetime.now(pytz.utc).astimezone(sf_timezone)

load_dotenv()


class UnifiedDatabaseAdapter(DatabaseInterface):
    """
    Unified database adapter using the new schema for both local and cloud environments.
    Uses synchronous methods for backward compatibility with existing codebase.
    """
    
    def __init__(self):
        self.connection_pool = self._create_connection_pool()
        self._init_db()

    def _create_connection_pool(self):
        """Create a connection pool based on environment configuration."""
        try:
            # Determine connection method based on environment
            use_cloud_sql = os.getenv("USE_CLOUD_SQL", "false").lower() == "true"
            environment = os.getenv("ENVIRONMENT", "development")
            
            if use_cloud_sql and environment == "production":
                # Production: Unix socket connection for Cloud SQL
                connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")
                if not connection_name:
                    raise ValueError("CLOUD_SQL_CONNECTION_NAME required for production Cloud SQL")
                
                # Unix socket connection
                host = f"/cloudsql/{connection_name}"
                dsn = f"host={host} dbname={os.getenv('CLOUD_SQL_DATABASE_NAME')} user={os.getenv('CLOUD_SQL_USERNAME')} password={os.getenv('CLOUD_SQL_PASSWORD')}"
                
            elif use_cloud_sql:
                # Development with Cloud SQL Proxy
                dsn = f"host=127.0.0.1 port=5432 dbname={os.getenv('CLOUD_SQL_DATABASE_NAME')} user={os.getenv('CLOUD_SQL_USERNAME')} password={os.getenv('CLOUD_SQL_PASSWORD')}"
                
            else:
                # Local PostgreSQL
                dsn = f"host={os.getenv('POSTGRES_HOST')} port={os.getenv('POSTGRES_PORT')} dbname={os.getenv('POSTGRES_DB')} user={os.getenv('POSTGRES_USER')} password={os.getenv('POSTGRES_PASSWORD')}"
            
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,  # min and max connections
                dsn
            )
            
            print(f"✅ Unified database connection pool initialized for environment: {environment}")
            return connection_pool
            
        except Exception as e:
            print(f"❌ Error creating connection pool: {e}")
            raise

    def __del__(self):
        """Clean up the connection pool when the object is destroyed."""
        if hasattr(self, 'connection_pool'):
            self.connection_pool.closeall()

    def _init_db(self):
        """Initialize the database with the new unified schema."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Create users table with Firebase integration
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        firebase_uid VARCHAR(128) UNIQUE,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        display_name VARCHAR(255),
                        status VARCHAR(50) DEFAULT 'active',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        is_active BOOLEAN DEFAULT TRUE,
                        total_conversations INTEGER DEFAULT 0,
                        total_messages INTEGER DEFAULT 0
                    );
                """)
                
                # Create indexes for users table
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active);")
                
                # Create conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(255) UNIQUE NOT NULL,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        title VARCHAR(255),
                        description TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_message_at TIMESTAMP WITH TIME ZONE,
                        status VARCHAR(50) DEFAULT 'active',
                        is_active BOOLEAN DEFAULT TRUE,
                        message_count INTEGER DEFAULT 0,
                        process_stage VARCHAR(100),
                        completion_percentage INTEGER DEFAULT 0
                    );
                """)
                
                # Create indexes for conversations table
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_thread_id ON conversations(thread_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);")
                
                # Create messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        content TEXT NOT NULL,
                        role VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        message_order INTEGER NOT NULL,
                        token_count INTEGER,
                        model_used VARCHAR(100),
                        processing_time INTEGER
                    );
                """)
                
                # Create indexes for messages table
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);")
                
                # Create summaries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS summaries (
                        id SERIAL PRIMARY KEY,
                        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        title VARCHAR(255),
                        summary TEXT NOT NULL,
                        summary_type VARCHAR(50) DEFAULT 'conversation',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        message_count INTEGER NOT NULL,
                        model_used VARCHAR(100),
                        token_count INTEGER,
                        processing_time INTEGER
                    );
                """)
                
                # Create analyses table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analyses (
                        id SERIAL PRIMARY KEY,
                        summary_id INTEGER NOT NULL REFERENCES summaries(id) UNIQUE,
                        analysis_data JSONB NOT NULL,
                        analysis_type VARCHAR(50) DEFAULT 'comprehensive',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        model_used VARCHAR(100),
                        token_count INTEGER,
                        processing_time INTEGER,
                        sentiment_score INTEGER,
                        topics_count INTEGER,
                        confidence_score INTEGER
                    );
                """)
                
            conn.commit()
            print("✅ Unified database schema initialized successfully")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error during database initialization: {e}")
            raise
        finally:
            self.connection_pool.putconn(conn)

    def get_or_create_user_by_email(self, email: str, firebase_uid: str = None, display_name: str = None) -> Optional[int]:
        """
        Get an existing user by email or create a new one.
        
        Args:
            email: User's email address
            firebase_uid: Firebase User ID (optional)
            display_name: User's display name (optional)
            
        Returns:
            user_id if successful, None otherwise
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Try to find existing user by email
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                result = cursor.fetchone()
                
                if result:
                    user_id = result['id']
                    # Update last_active and Firebase UID if provided
                    update_values = [get_sf_time(), user_id]
                    update_query = "UPDATE users SET last_active = %s, is_active = TRUE"
                    
                    if firebase_uid:
                        update_query += ", firebase_uid = %s"
                        update_values.insert(-1, firebase_uid)
                    if display_name:
                        update_query += ", display_name = %s"
                        update_values.insert(-1, display_name)
                    
                    update_query += " WHERE id = %s"
                    cursor.execute(update_query, update_values)
                    conn.commit()
                    print(f"✅ Found existing user {user_id} for email {email}")
                    return user_id
                else:
                    # Create new user
                    cursor.execute(
                        """INSERT INTO users (email, firebase_uid, display_name, created_at, last_active) 
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (email, firebase_uid, display_name, get_sf_time(), get_sf_time())
                    )
                    user_id = cursor.fetchone()['id']
                    conn.commit()
                    print(f"✅ Created new user {user_id} for email {email}")
                    return user_id
                    
        except Exception as e:
            print(f"❌ Error in get_or_create_user_by_email: {e}")
            if conn: 
                conn.rollback()
            return None
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user information by email."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            print(f"Error getting user by email {email}: {e}")
            return None
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    def create_conversation(self, user_id: int, title: str = None) -> Optional[str]:
        """Create a new conversation for a user."""
        thread_id = str(uuid.uuid4())
        
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO conversations (thread_id, user_id, title, created_at, updated_at) 
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (thread_id, user_id, title, get_sf_time(), get_sf_time())
                )
                conversation_id = cursor.fetchone()[0]
                
                # Update user's conversation count
                cursor.execute(
                    "UPDATE users SET total_conversations = total_conversations + 1 WHERE id = %s",
                    (user_id,)
                )
                
            conn.commit()
            print(f"✅ Created conversation {conversation_id} with thread_id {thread_id}")
            return thread_id
            
        except Exception as e:
            print(f"❌ Error creating conversation: {e}")
            if conn: 
                conn.rollback()
            return None
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    def save_message(self, user_email: str, session_id: str, content: str, role: str, model_used: str = None) -> Optional[int]:
        """
        Save a message to the database.
        
        Args:
            user_email: User's email address
            session_id: Conversation thread ID (session_id = thread_id)
            content: Message content
            role: Message role ('user' or 'assistant')
            model_used: AI model used (for assistant messages)
            
        Returns:
            message_id if successful, None otherwise
        """
        # Get or create user
        user_id = self.get_or_create_user_by_email(user_email)
        if not user_id:
            print(f"❌ Could not get or create user for email {user_email}")
            return None
        
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Get or create conversation
                cursor.execute(
                    "SELECT id, message_count FROM conversations WHERE thread_id = %s", 
                    (session_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    conversation_id, message_count = result
                else:
                    # Create new conversation
                    cursor.execute(
                        """INSERT INTO conversations (thread_id, user_id, created_at, updated_at) 
                           VALUES (%s, %s, %s, %s) RETURNING id""",
                        (session_id, user_id, get_sf_time(), get_sf_time())
                    )
                    conversation_id = cursor.fetchone()[0]
                    message_count = 0
                    
                    # Update user's conversation count
                    cursor.execute(
                        "UPDATE users SET total_conversations = total_conversations + 1 WHERE id = %s",
                        (user_id,)
                    )
                
                message_order = message_count + 1
                
                # Insert message
                cursor.execute(
                    """INSERT INTO messages (conversation_id, user_id, content, role, created_at, message_order, model_used) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (conversation_id, user_id, content, role, get_sf_time(), message_order, model_used)
                )
                message_id = cursor.fetchone()[0]
                
                # Update conversation and user statistics
                cursor.execute(
                    """UPDATE conversations SET 
                       message_count = message_count + 1,
                       last_message_at = %s,
                       updated_at = %s 
                       WHERE id = %s""",
                    (get_sf_time(), get_sf_time(), conversation_id)
                )
                
                cursor.execute(
                    """UPDATE users SET 
                       total_messages = total_messages + 1,
                       last_active = %s 
                       WHERE id = %s""",
                    (get_sf_time(), user_id)
                )
                
            conn.commit()
            print(f"✅ Saved message {message_id} for user {user_id} in conversation {conversation_id}")
            return message_id
            
        except Exception as e:
            print(f"❌ Error saving message: {e}")
            if conn: 
                conn.rollback()
            return None
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a specific thread."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    """SELECT m.role, m.content, m.created_at 
                       FROM messages m
                       JOIN conversations c ON m.conversation_id = c.id
                       WHERE c.thread_id = %s 
                       ORDER BY m.message_order""",
                    (session_id,)
                )
                rows = cursor.fetchall()
                
                return [
                    {
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["created_at"]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            print(f"❌ Error getting conversation history: {e}")
            return []
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    def get_recent_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent messages for a session (for backward compatibility)."""
        return self.get_conversation_history(session_id)[-limit:]

    def get_chat_sessions_for_user(self, user_email: str) -> List[Dict[str, Any]]:
        """
        Get all distinct chat sessions for a user, ordered by most recent message.
        
        Args:
            user_email: The email of the user
            
        Returns:
            List of dictionaries representing chat sessions
        """
        user = self.get_user_by_email(user_email)
        if not user:
            print(f"❌ No user found for email {user_email}")
            return []
        
        user_id = user['id']
        
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    """SELECT 
                           c.thread_id as session_id,
                           c.last_message_at as last_message_timestamp,
                           c.created_at,
                           c.message_count,
                           c.title,
                           (SELECT content FROM messages m 
                            WHERE m.conversation_id = c.id AND m.role = 'user' 
                            ORDER BY m.message_order LIMIT 1) as first_message_content
                       FROM conversations c
                       WHERE c.user_id = %s AND c.is_active = TRUE
                       ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC""",
                    (user_id,)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            print(f"❌ Error getting chat sessions for user: {e}")
            return []
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    # Legacy compatibility methods
    def update_user_status(self, identifier: str, status: str, is_email: bool = True) -> bool:
        """Update user status (backward compatibility)."""
        if not is_email:
            print("⚠️ Warning: session_id-based user lookup is deprecated")
            return False
            
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET status = %s, last_active = %s WHERE email = %s",
                    (status, get_sf_time(), identifier)
                )
                success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"❌ Error updating user status: {e}")
            if conn: 
                conn.rollback()
            return False
        finally:
            if conn: 
                self.connection_pool.putconn(conn)

    # Abstract method implementations for backward compatibility
    def create_user(self, session_id: str) -> int:
        """Legacy method: Create user by session_id (deprecated)."""
        print("⚠️ Warning: create_user with session_id is deprecated. Use get_or_create_user_by_email instead.")
        # This is a legacy method that doesn't fit the new schema well
        # We'll create a minimal user with session_id as email for compatibility
        fake_email = f"session_{session_id}@deprecated.local"
        user_id = self.get_or_create_user_by_email(
            email=fake_email,
            display_name=f"Legacy User {session_id[:8]}"
        )
        return user_id if user_id else -1

    def get_user(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Legacy method: Get user by session_id (deprecated)."""
        print("⚠️ Warning: get_user with session_id is deprecated. Use get_user_by_email instead.")
        # Try to find user by fake email based on session_id
        fake_email = f"session_{session_id}@deprecated.local"
        return self.get_user_by_email(fake_email) 