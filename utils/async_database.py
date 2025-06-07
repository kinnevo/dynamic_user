import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
import pytz
import asyncpg
from dotenv import load_dotenv

# Set up timezone
sf_timezone = pytz.timezone('America/Los_Angeles')

def get_sf_time():
    """Get current time in San Francisco timezone"""
    return datetime.now(pytz.utc).astimezone(sf_timezone)

load_dotenv(override=True)


class AsyncDatabaseAdapter:
    """
    Modern async database adapter using asyncpg with Cloud SQL Python Connector.
    Much cleaner than the synchronous wrapper approach.
    """
    
    def __init__(self):
        self.pool = None
        self.connector = None
    
    async def init_pool(self):
        """Initialize the connection pool."""
        if self.pool:
            return
            
        use_cloud_sql = os.getenv("USE_CLOUD_SQL", "false").lower() == "true"
        environment = os.getenv("ENVIRONMENT", "development")
        
        print(f"🔧 Async Database Configuration:")
        print(f"   Environment: {environment}")
        print(f"   Use Cloud SQL: {use_cloud_sql}")
        
        if use_cloud_sql and environment == "production":
            # Production: Use Cloud SQL Python Connector
            from google.cloud.sql.connector import Connector
            
            connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")
            if not connection_name:
                raise ValueError("CLOUD_SQL_CONNECTION_NAME required for production Cloud SQL")
            
            print(f"   Connection method: Cloud SQL Connector (asyncpg)")
            print(f"   Connection name: {connection_name}")
            
            self.connector = Connector()
            
            # Create a simple connection manager instead of a full pool
            class CloudSQLConnectionManager:
                def __init__(self, connector, connection_name, user, password, db):
                    self.connector = connector
                    self.connection_name = connection_name
                    self.user = user
                    self.password = password
                    self.db = db
                    
                def acquire(self):
                    """Get a connection wrapper that can be used as async context manager."""
                    return CloudSQLConnectionWrapper(self)
                    
                async def _get_connection(self):
                    """Internal method to get actual connection."""
                    conn = await self.connector.connect_async(
                        self.connection_name,
                        "asyncpg",
                        user=self.user,
                        password=self.password,
                        db=self.db,
                    )
                    return conn
                    
                async def close(self):
                    """Close the connector."""
                    await self.connector.close_async()
            
            class CloudSQLConnectionWrapper:
                """Wrapper to provide context manager support."""
                def __init__(self, manager):
                    self.manager = manager
                    self.conn = None
                    
                async def __aenter__(self):
                    self.conn = await self.manager._get_connection()
                    return self.conn
                    
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    if self.conn:
                        await self.conn.close()
                        self.conn = None
            
            self.pool = CloudSQLConnectionManager(
                self.connector,
                connection_name,
                os.getenv('CLOUD_SQL_USERNAME'),
                os.getenv('CLOUD_SQL_PASSWORD'),
                os.getenv('CLOUD_SQL_DATABASE_NAME')
            )
            
        elif use_cloud_sql:
            # Development with Cloud SQL Proxy
            print(f"   Connection method: Cloud SQL Proxy (127.0.0.1:5432)")
            dsn = f"postgresql://{os.getenv('CLOUD_SQL_USERNAME')}:{os.getenv('CLOUD_SQL_PASSWORD')}@127.0.0.1:5432/{os.getenv('CLOUD_SQL_DATABASE_NAME')}"
            
            self.pool = await asyncpg.create_pool(
                dsn,
                min_size=1,
                max_size=20,
                command_timeout=60
            )
            
        else:
            # Local PostgreSQL
            print(f"   Connection method: Local PostgreSQL")
            dsn = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
            
            self.pool = await asyncpg.create_pool(
                dsn,
                min_size=1,
                max_size=20,
                command_timeout=60
            )
        
        print(f"✅ Async database pool initialized")
        await self._init_db()
    
    async def close(self):
        """Close the connection pool and connector."""
        if self.pool:
            if hasattr(self.pool, 'close') and callable(self.pool.close):
                # Cloud SQL connection manager
                await self.pool.close()
            else:
                # Regular asyncpg pool
                await self.pool.close()
        if self.connector:
            await self.connector.close_async()
    
    async def _init_db(self):
        """Initialize the database schema."""
        async with self.pool.acquire() as conn:
            # Create users table
            await conn.execute("""
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
            
            # Create indexes
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
            
            # Create indexes for conversations
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_thread_id ON conversations(thread_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);")
            
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
            
            # Create indexes for messages
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);")
            
            print("✅ Async database schema initialized")
    
    async def get_or_create_user_by_email(self, email: str, firebase_uid: str = None, display_name: str = None) -> Optional[int]:
        """Get or create user by email."""
        async with self.pool.acquire() as conn:
            # Try to find existing user
            user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            
            if user:
                user_id = user['id']
                # Update last active
                await conn.execute(
                    "UPDATE users SET last_active = $1, is_active = TRUE WHERE id = $2",
                    get_sf_time(), user_id
                )
                if firebase_uid:
                    await conn.execute(
                        "UPDATE users SET firebase_uid = $1 WHERE id = $2",
                        firebase_uid, user_id
                    )
                if display_name:
                    await conn.execute(
                        "UPDATE users SET display_name = $1 WHERE id = $2",
                        display_name, user_id
                    )
                return user_id
            else:
                # Create new user
                user_id = await conn.fetchval(
                    """INSERT INTO users (email, firebase_uid, display_name, created_at, last_active) 
                       VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                    email, firebase_uid, display_name, get_sf_time(), get_sf_time()
                )
                print(f"✅ Created new user {user_id} for email {email}")
                return user_id
    
    async def save_message(self, user_email: str, session_id: str, content: str, role: str, 
                          model_used: str = None, firebase_uid: str = None, display_name: str = None,
                          token_count: int = None, processing_time: int = None) -> Optional[int]:
        """Save a message to the database."""
        # Get or create user
        user_id = await self.get_or_create_user_by_email(
            email=user_email,
            firebase_uid=firebase_uid,
            display_name=display_name
        )
        if not user_id:
            return None
        
        async with self.pool.acquire() as conn:
            # Get or create conversation
            conversation = await conn.fetchrow(
                "SELECT id, message_count FROM conversations WHERE thread_id = $1", 
                session_id
            )
            
            if conversation:
                conversation_id, message_count = conversation['id'], conversation['message_count']
            else:
                # Create new conversation
                conversation_id = await conn.fetchval(
                    """INSERT INTO conversations (thread_id, user_id, created_at, updated_at) 
                       VALUES ($1, $2, $3, $4) RETURNING id""",
                    session_id, user_id, get_sf_time(), get_sf_time()
                )
                message_count = 0
                
                # Update user's conversation count
                await conn.execute(
                    "UPDATE users SET total_conversations = total_conversations + 1 WHERE id = $1",
                    user_id
                )
            
            # Insert message
            message_id = await conn.fetchval(
                """INSERT INTO messages (conversation_id, user_id, content, role, created_at, message_order, model_used, token_count, processing_time) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id""",
                conversation_id, user_id, content, role, get_sf_time(), message_count + 1, model_used, token_count, processing_time
            )
            
            # Update conversation and user stats
            await conn.execute(
                """UPDATE conversations SET 
                   message_count = message_count + 1,
                   last_message_at = $1,
                   updated_at = $2 
                   WHERE id = $3""",
                get_sf_time(), get_sf_time(), conversation_id
            )
            
            await conn.execute(
                """UPDATE users SET 
                   total_messages = total_messages + 1,
                   last_active = $1 
                   WHERE id = $2""",
                get_sf_time(), user_id
            )
            
            print(f"✅ Saved message {message_id}")
            return message_id
    
    async def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT m.role, m.content, m.created_at 
                   FROM messages m
                   JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.thread_id = $1 
                   ORDER BY m.message_order""",
                session_id
            )
            
            return [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["created_at"].isoformat() if row["created_at"] else None
                }
                for row in rows
            ]
    
    async def get_chat_sessions_for_user(self, user_email: str) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user."""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", user_email)
            if not user:
                return []
            
            rows = await conn.fetch(
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
                   WHERE c.user_id = $1 AND c.is_active = TRUE
                   ORDER BY c.last_message_at DESC NULLS LAST, c.created_at DESC""",
                user['id']
            )
            
            sessions = []
            for row in rows:
                session_dict = dict(row)
                if session_dict['last_message_timestamp']:
                    session_dict['last_message_timestamp'] = session_dict['last_message_timestamp'].isoformat()
                if session_dict['created_at']:
                    session_dict['created_at'] = session_dict['created_at'].isoformat()
                sessions.append(session_dict)
            
            return sessions
    
    async def update_user_status(self, identifier: str, status: str, is_email: bool = True) -> bool:
        """Update user status by email or other identifier."""
        async with self.pool.acquire() as conn:
            if is_email:
                # Update by email
                result = await conn.execute(
                    "UPDATE users SET status = $1, last_active = $2 WHERE email = $3",
                    status, get_sf_time(), identifier
                )
            else:
                # Update by ID (if needed for legacy support)
                try:
                    user_id = int(identifier)
                    result = await conn.execute(
                        "UPDATE users SET status = $1, last_active = $2 WHERE id = $3",
                        status, get_sf_time(), user_id
                    )
                except ValueError:
                    print(f"Invalid user identifier for status update: {identifier}")
                    return False
            
            # Check if any rows were affected
            return result.split()[-1] != '0' if result else False
    
    async def get_recent_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent messages for a session."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT m.role, m.content, m.created_at, m.model_used, m.processing_time
                   FROM messages m
                   JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.thread_id = $1 
                   ORDER BY m.message_order DESC
                   LIMIT $2""",
                session_id, limit
            )
            
            messages = []
            for row in rows:
                message_dict = dict(row)
                if message_dict['created_at']:
                    message_dict['created_at'] = message_dict['created_at'].isoformat()
                messages.append(message_dict)
            
            # Reverse to get chronological order
            return list(reversed(messages))


# Global instance
db = AsyncDatabaseAdapter() 