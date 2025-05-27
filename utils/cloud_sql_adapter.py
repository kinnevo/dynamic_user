import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import pytz
import asyncpg
import json
from dotenv import load_dotenv
from utils.database_interface import DatabaseInterface

# Set up timezone
sf_timezone = pytz.timezone('America/Los_Angeles')

def get_sf_time():
    """Get current time in San Francisco timezone"""
    return datetime.now(pytz.utc).astimezone(sf_timezone)

load_dotenv()


class CloudSQLAdapter(DatabaseInterface):
    """
    Cloud SQL adapter with Firebase integration.
    Supports both local development and Google Cloud SQL production deployment.
    """
    
    def __init__(self):
        self.connection_pool = None
        self._init_connection_pool()

    async def _init_connection_pool(self):
        """Initialize async connection pool for Cloud SQL."""
        try:
            # Determine connection method based on environment
            use_cloud_sql = os.getenv("USE_CLOUD_SQL", "false").lower() == "true"
            environment = os.getenv("ENVIRONMENT", "development")
            
            if use_cloud_sql and environment == "production":
                # Production: Unix socket connection for Cloud SQL
                connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")
                if not connection_name:
                    raise ValueError("CLOUD_SQL_CONNECTION_NAME required for production Cloud SQL")
                
                dsn = f"postgresql://{os.getenv('CLOUD_SQL_USERNAME')}:{os.getenv('CLOUD_SQL_PASSWORD')}@/{os.getenv('CLOUD_SQL_DATABASE_NAME')}?host=/cloudsql/{connection_name}"
            
            elif use_cloud_sql:
                # Development with Cloud SQL Proxy
                dsn = f"postgresql://{os.getenv('CLOUD_SQL_USERNAME')}:{os.getenv('CLOUD_SQL_PASSWORD')}@127.0.0.1:5432/{os.getenv('CLOUD_SQL_DATABASE_NAME')}"
            
            else:
                # Local PostgreSQL
                dsn = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
            
            self.connection_pool = await asyncpg.create_pool(
                dsn,
                min_size=1,
                max_size=20,
                command_timeout=60
            )
            
            print(f"✅ Cloud SQL connection pool initialized for environment: {environment}")
            await self._init_db()
            
        except Exception as e:
            print(f"❌ Error initializing Cloud SQL connection pool: {e}")
            raise

    async def _init_db(self):
        """Initialize the database with the new unified schema."""
        async with self.connection_pool.acquire() as conn:
            try:
                # Create users table with Firebase integration
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        firebase_uid VARCHAR(128) UNIQUE NOT NULL,
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
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active);")
                
                # Create conversations table
                await conn.execute("""
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
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_thread_id ON conversations(thread_id);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);")
                
                # Create messages table
                await conn.execute("""
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
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);")
                
                # Create summaries table
                await conn.execute("""
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
                await conn.execute("""
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
                
                print("✅ Database schema initialized successfully")
                
            except Exception as e:
                print(f"❌ Error during database initialization: {e}")
                raise

    async def get_or_create_user_by_firebase_uid(self, firebase_uid: str, email: str, display_name: str = None) -> Optional[int]:
        """
        Get an existing user by Firebase UID or create a new one.
        
        Args:
            firebase_uid: Firebase User ID
            email: User's email address
            display_name: User's display name (optional)
            
        Returns:
            user_id if successful, None otherwise
        """
        async with self.connection_pool.acquire() as conn:
            try:
                # Try to find existing user by Firebase UID
                result = await conn.fetchrow(
                    "SELECT id FROM users WHERE firebase_uid = $1", firebase_uid
                )
                
                if result:
                    user_id = result['id']
                    # Update last_active and email in case it changed
                    await conn.execute(
                        """UPDATE users SET 
                           last_active = $1, 
                           email = $2, 
                           display_name = COALESCE($3, display_name),
                           is_active = TRUE 
                           WHERE id = $4""",
                        get_sf_time(), email, display_name, user_id
                    )
                    print(f"✅ Found existing user {user_id} for Firebase UID {firebase_uid}")
                    return user_id
                else:
                    # Create new user
                    user_id = await conn.fetchval(
                        """INSERT INTO users (firebase_uid, email, display_name, created_at, last_active) 
                           VALUES ($1, $2, $3, $4, $4) RETURNING id""",
                        firebase_uid, email, display_name, get_sf_time()
                    )
                    print(f"✅ Created new user {user_id} for Firebase UID {firebase_uid}")
                    return user_id
                    
            except Exception as e:
                print(f"❌ Error in get_or_create_user_by_firebase_uid: {e}")
                return None

    async def create_conversation(self, user_id: int, title: str = None) -> Optional[str]:
        """
        Create a new conversation for a user.
        
        Args:
            user_id: User's database ID
            title: Optional conversation title
            
        Returns:
            thread_id if successful, None otherwise
        """
        thread_id = str(uuid.uuid4())
        
        async with self.connection_pool.acquire() as conn:
            try:
                conversation_id = await conn.fetchval(
                    """INSERT INTO conversations (thread_id, user_id, title, created_at, updated_at) 
                       VALUES ($1, $2, $3, $4, $4) RETURNING id""",
                    thread_id, user_id, title, get_sf_time()
                )
                
                # Update user's conversation count
                await conn.execute(
                    "UPDATE users SET total_conversations = total_conversations + 1 WHERE id = $1",
                    user_id
                )
                
                print(f"✅ Created conversation {conversation_id} with thread_id {thread_id}")
                return thread_id
                
            except Exception as e:
                print(f"❌ Error creating conversation: {e}")
                return None

    async def save_message(self, firebase_uid: str, thread_id: str, content: str, role: str, model_used: str = None) -> Optional[int]:
        """
        Save a message to the database.
        
        Args:
            firebase_uid: Firebase User ID
            thread_id: Conversation thread ID
            content: Message content
            role: Message role ('user' or 'assistant')
            model_used: AI model used (for assistant messages)
            
        Returns:
            message_id if successful, None otherwise
        """
        async with self.connection_pool.acquire() as conn:
            try:
                # Get user and conversation IDs
                user_result = await conn.fetchrow(
                    "SELECT id FROM users WHERE firebase_uid = $1", firebase_uid
                )
                if not user_result:
                    print(f"❌ User not found for Firebase UID: {firebase_uid}")
                    return None
                
                conversation_result = await conn.fetchrow(
                    "SELECT id, message_count FROM conversations WHERE thread_id = $1", thread_id
                )
                if not conversation_result:
                    print(f"❌ Conversation not found for thread_id: {thread_id}")
                    return None
                
                user_id = user_result['id']
                conversation_id = conversation_result['id']
                message_order = conversation_result['message_count'] + 1
                
                # Insert message
                message_id = await conn.fetchval(
                    """INSERT INTO messages (conversation_id, user_id, content, role, created_at, message_order, model_used) 
                       VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
                    conversation_id, user_id, content, role, get_sf_time(), message_order, model_used
                )
                
                # Update conversation and user statistics
                await conn.execute(
                    """UPDATE conversations SET 
                       message_count = message_count + 1,
                       last_message_at = $1,
                       updated_at = $1 
                       WHERE id = $2""",
                    get_sf_time(), conversation_id
                )
                
                await conn.execute(
                    """UPDATE users SET 
                       total_messages = total_messages + 1,
                       last_active = $1 
                       WHERE id = $2""",
                    get_sf_time(), user_id
                )
                
                print(f"✅ Saved message {message_id} for user {user_id} in conversation {conversation_id}")
                return message_id
                
            except Exception as e:
                print(f"❌ Error saving message: {e}")
                return None

    async def get_conversation_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific thread.
        
        Args:
            thread_id: Conversation thread ID
            
        Returns:
            List of message objects with role and content
        """
        async with self.connection_pool.acquire() as conn:
            try:
                messages = await conn.fetch(
                    """SELECT role, content, created_at 
                       FROM messages m
                       JOIN conversations c ON m.conversation_id = c.id
                       WHERE c.thread_id = $1 
                       ORDER BY m.message_order""",
                    thread_id
                )
                
                return [
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                        "timestamp": msg["created_at"]
                    }
                    for msg in messages
                ]
                
            except Exception as e:
                print(f"❌ Error getting conversation history: {e}")
                return []

    async def get_user_conversations(self, firebase_uid: str) -> List[Dict[str, Any]]:
        """
        Get all conversations for a user.
        
        Args:
            firebase_uid: Firebase User ID
            
        Returns:
            List of conversation objects
        """
        async with self.connection_pool.acquire() as conn:
            try:
                conversations = await conn.fetch(
                    """SELECT c.thread_id, c.title, c.created_at, c.last_message_at, c.message_count
                       FROM conversations c
                       JOIN users u ON c.user_id = u.id
                       WHERE u.firebase_uid = $1 AND c.is_active = TRUE
                       ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC""",
                    firebase_uid
                )
                
                return [dict(conv) for conv in conversations]
                
            except Exception as e:
                print(f"❌ Error getting user conversations: {e}")
                return []

    async def close(self):
        """Close the connection pool."""
        if self.connection_pool:
            await self.connection_pool.close()

    # Legacy methods for backward compatibility
    def get_or_create_user_by_email(self, email: str) -> Optional[int]:
        """Legacy method - use get_or_create_user_by_firebase_uid instead."""
        print("⚠️ Warning: get_or_create_user_by_email is deprecated. Use get_or_create_user_by_firebase_uid.")
        return None

    def save_message(self, user_email: str, session_id: str, content: str, role: str) -> Optional[int]:
        """Legacy method - use async save_message instead."""
        print("⚠️ Warning: Synchronous save_message is deprecated. Use async save_message.")
        return None 