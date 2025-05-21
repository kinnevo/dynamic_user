import os
from datetime import datetime
import pytz
import openai
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
    # Create a timezone-aware UTC datetime and then convert it to SF timezone
    return datetime.now(pytz.utc).astimezone(sf_timezone)

# Configure OpenAI API
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

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
                # User table: email is the primary identifier for a person
                # session_id here might become a default or last active session_id if needed,
                # or removed if chat sessions are managed separately.
                # For now, making it nullable and not necessarily unique at the user level.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fi_users (
                        user_id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE, -- User's email, main identifier
                        session_id TEXT NULL,      -- This will now be session_id
                        status TEXT DEFAULT 'Idle',
                        last_active TIMESTAMP,
                        explorations_completed INTEGER DEFAULT 0,
                        full_exploration BOOLEAN DEFAULT FALSE,
                        logged BOOLEAN DEFAULT FALSE -- Might represent if user is Firebase-logged-in
                    );
                """)
                
                # Add email column to fi_users if it doesn't exist (for migration)
                cursor.execute("""
                    ALTER TABLE fi_users
                    ADD COLUMN IF NOT EXISTS email VARCHAR(255) NULL;
                """)
                # Add UNIQUE constraint to email if not already present (handle potential errors if duplicates exist)
                # For a clean setup, this unique constraint is important.
                # However, for migration, if duplicate emails *could* exist due to old data, this needs care.
                # We might need a separate step to clean up duplicates before applying this.
                # For now, let's assume we want to enforce it.
                # cursor.execute("""
                #     DO $$
                #     BEGIN
                #         IF NOT EXISTS (
                #             SELECT 1 FROM pg_constraint
                #             WHERE conname = 'fi_users_email_key' AND conrelid = 'fi_users'::regclass
                #         ) THEN
                #             ALTER TABLE fi_users ADD CONSTRAINT fi_users_email_key UNIQUE (email);
                #         END IF;
                #     END $$;
                # """)
                # Make session_id nullable in fi_users if it's not already (for migration)
                cursor.execute("""
                    ALTER TABLE fi_users
                    ALTER COLUMN session_id DROP NOT NULL;
                """)
                # Remove UNIQUE constraint from session_id in fi_users if it exists
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'fi_users_session_id_key' AND conrelid = 'fi_users'::regclass
                        ) THEN
                            ALTER TABLE fi_users DROP CONSTRAINT fi_users_session_id_key;
                        END IF;
                    END $$;
                """)

                # Messages table: session_id is the session_id
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fi_messages (
                        message_id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL, -- Renamed from session_id for clarity
                        user_id INTEGER NOT NULL,      -- References fi_users.user_id
                        content TEXT NOT NULL,
                        role TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES fi_users(user_id)
                    );
                """)
                # Rename session_id to session_id in fi_messages if it exists
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fi_messages' AND column_name='session_id')
                           AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fi_messages' AND column_name='session_id')
                        THEN
                            ALTER TABLE fi_messages RENAME COLUMN session_id TO session_id;
                        END IF;
                    END $$;
                """)

                # Summary table: session_id is the session_id
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fi_summary (
                        summary_id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL, -- Renamed from session_id
                        user_id INTEGER NOT NULL,      -- References fi_users.user_id
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        summary TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES fi_users(user_id)
                    );
                """)
                # Rename session_id to session_id in fi_summary if it exists
                cursor.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fi_summary' AND column_name='session_id')
                           AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='fi_summary' AND column_name='session_id')
                        THEN
                            ALTER TABLE fi_summary RENAME COLUMN session_id TO session_id;
                        END IF;
                    END $$;
                """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error during DB initialization or migration: {e}")
            # Potentially raise or handle more gracefully
        finally:
            self.connection_pool.putconn(conn)
    
    def get_or_create_user_by_email(self, email: str) -> Optional[int]:
        """
        Get an existing user by email or create a new one.
        Sets user as logged=TRUE and updates last_active.
        Args:
            email: User's email address.
        Returns:
            user_id if successful, None otherwise.
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT user_id FROM fi_users WHERE email = %s", (email,))
                result = cursor.fetchone()
                
                if result:
                    user_id = result['user_id']
                    print(f"Found existing user {user_id} for email {email}")
                    cursor.execute(
                        "UPDATE fi_users SET last_active = %s, logged = TRUE, status = 'Active' WHERE user_id = %s",
                        (get_sf_time(), user_id)
                    )
                    # Optionally, update fi_users.session_id to store last active chat if needed later
                    # For now, main user identification is via email.
                    conn.commit()
                    return user_id
                else:
                    print(f"Creating new user for email {email}")
                    cursor.execute(
                        "INSERT INTO fi_users (email, last_active, status, logged) VALUES (%s, %s, %s, TRUE) RETURNING user_id",
                        (email, get_sf_time(), 'Active')
                    )
                    user_id = cursor.fetchone()['user_id']
                    conn.commit()
                    print(f"Created new user {user_id} for email {email}")
                    return user_id
        except psycopg2.Error as e:
            print(f"Database error in get_or_create_user_by_email for {email}: {e}")
            if conn: conn.rollback()
            return None
        except Exception as e:
            print(f"Unexpected error in get_or_create_user_by_email for {email}: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: self.connection_pool.putconn(conn)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by email.
        Args:
            email: User's email address.
        Returns:
            User data dictionary or None if not found.
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM fi_users WHERE email = %s", (email,))
                row = cursor.fetchone()
                if row:
                    # Example: Update last_active on fetching user, if desired
                    # cursor.execute(
                    #     "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                    #     (get_sf_time(), row['user_id'])
                    # )
                    # conn.commit()
                    return dict(row)
                return None
        except Exception as e:
            print(f"Error getting user by email {email}: {e}")
            return None
        finally:
            if conn: self.connection_pool.putconn(conn)

    def save_message(self, user_email: str, session_id: str, content: str, role: str) -> Optional[int]:
        """
        Save a message to the database, associating it with a user (by email) and a specific chat session.
        
        Args:
            user_email: Email of the user sending the message.
            session_id: Unique identifier for the chat session.
            content: Message content.
            role: Message role ('user' or 'assistant').
            
        Returns:
            message_id if successful, None otherwise.
        """
        user_id = self.get_or_create_user_by_email(user_email)
        if user_id is None:
            print(f"Error: Could not get or create user for email {user_email}. Message not saved.")
            return None

        conn = self.connection_pool.getconn()
        try:
            # Ensure last_active is updated for the user.
            # get_or_create_user_by_email already does this, but an explicit update here ensures it for this exact event.
            with conn.cursor() as cursor:
                 cursor.execute(
                     "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                     (get_sf_time(), user_id)
                 )
            # Optional: Update fi_users.session_id to this session_id to mark as last active chat for this user
            # This could be useful for quickly resuming the user's last chat.
            # For example:
            # with conn.cursor() as cursor:
            #     cursor.execute(
            #         "UPDATE fi_users SET session_id = %s WHERE user_id = %s",
            #         (session_id, user_id)
            #     )
            # conn.commit() # Commit if session_id in fi_users is updated

            # Now save the message
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fi_messages (session_id, user_id, content, role, timestamp) VALUES (%s, %s, %s, %s, %s) RETURNING message_id",
                    (session_id, user_id, content, role, get_sf_time())
                )
                message_id = cursor.fetchone()[0]
            conn.commit()
            print(f"Message saved for user_id {user_id} in session_id {session_id}. Message ID: {message_id}")
            return message_id
        except psycopg2.Error as e:
            print(f"Database error saving message for user_email {user_email}, session_id {session_id}: {e}")
            if conn: conn.rollback()
            return None
        except Exception as e:
            print(f"Unexpected error saving message for user_email {user_email}, session_id {session_id}: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: self.connection_pool.putconn(conn)
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific chat session
        
        Args:
            session_id: Unique chat session identifier
            
        Returns:
            List of message objects with role and content
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT role, content FROM fi_messages WHERE session_id = %s ORDER BY timestamp", # Querying by session_id
                    (session_id,)
                )
                rows = cursor.fetchall()
                # history = [dict(row) for row in rows] # Original, might include more fields than needed
                
                # Format history for common use (e.g., LLM context)
                formatted_history = []
                for row in rows:
                    formatted_history.append({
                        "role": row["role"],
                        "content": row["content"]
                    })
                    
                return formatted_history
        except Exception as e:
            print(f"Error in get_conversation_history for session_id {session_id}: {e}")
            return []
        finally:
            if conn: self.connection_pool.putconn(conn)
    
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent fi_messages for a specific chat session
        
        Args:
            session_id: Unique chat session identifier
            limit: Maximum number of fi_messages to return
            
        Returns:
            List of recent fi_messages
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT role, content, timestamp FROM fi_messages WHERE session_id = %s ORDER BY timestamp DESC LIMIT %s", # Querying by session_id
                    (session_id, limit)
                )
                rows = cursor.fetchall()
                recent_messages = [dict(row) for row in rows]
                
                # Reverse to get chronological order
                recent_messages.reverse()
                
                return recent_messages
        except Exception as e:
            print(f"Error in get_recent_messages for session_id {session_id}: {e}")
            return []
        finally:
            if conn: self.connection_pool.putconn(conn)
    
    def create_user(self, session_id: str) -> int: # DEPRECATED: Use get_or_create_user_by_email
        """
        DEPRECATED: Create a new user based on old session_id model.
        Prefer get_or_create_user_by_email.
        This method will now mostly serve to find an existing user by legacy session_id
        or log a warning, as new user creation is email-gated.
        """
        print(f"WARNING: Deprecated create_user called with session_id: {session_id}. User creation is now email-based.")
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM fi_users WHERE session_id = %s", (session_id,))
                result = cursor.fetchone()
                if result:
                    user_id = result[0]
                    print(f"Found existing user {user_id} via legacy session_id {session_id}")
                    # Optionally update last_active, but primarily this is for lookup now
                    cursor.execute(
                        "UPDATE fi_users SET last_active = %s WHERE user_id = %s",
                        (get_sf_time(), user_id)
                    )
                    conn.commit()
                    return user_id
                else:
                    print(f"No user found for legacy session_id {session_id}. Cannot create new user without email.")
                    return -1 # Indicate failure or user not found
        except Exception as e:
            print(f"Error in deprecated create_user for session_id {session_id}: {e}")
            if conn: conn.rollback()
            return -1
        finally:
            if conn: self.connection_pool.putconn(conn)
    
    def get_user(self, session_id: str) -> Optional[Dict[str, Any]]: # DEPRECATED: Use get_user_by_email
        """
        DEPRECATED: Get user information by old session_id model.
        Prefer get_user_by_email.
        This will attempt to find a user by legacy session_id.
        """
        print(f"WARNING: Deprecated get_user called with session_id: {session_id}.")
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("SELECT * FROM fi_users WHERE session_id = %s", (session_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            print(f"Error in deprecated get_user for session_id {session_id}: {e}")
            return None
        finally:
            if conn: self.connection_pool.putconn(conn)
    
    def update_user_status(self, identifier: str, status: str, is_email: bool = True) -> bool:
        """
        Update the status of a user, identified by email (preferred) or legacy session_id.
        New user creation is not supported here; user must exist.

        Args:
            identifier: User's email address or legacy session_id.
            status: New status value (e.g., 'Active', 'Idle').
            is_email: True if identifier is an email, False if it's a legacy session_id.
            
        Returns:
            True if status updated, False otherwise.
        """
        user_data: Optional[Dict[str, Any]] = None
        if is_email:
            user_data = self.get_user_by_email(identifier)
            if not user_data:
                print(f"update_user_status: User not found with email {identifier}. Cannot update status.")
                # If we wanted to create user here: user_id = self.get_or_create_user_by_email(identifier)
                # But for now, let's assume status updates are for existing users.
                return False
        else: # Legacy session_id
            user_data = self.get_user(identifier) # Uses deprecated get_user
            if not user_data:
                print(f"update_user_status: User not found with legacy session_id {identifier}. Cannot update status.")
                return False
        
        user_id = user_data['user_id']

        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE fi_users SET status = %s, last_active = %s WHERE user_id = %s",
                    (status, get_sf_time(), user_id)
                )
            conn.commit()
            print(f"Status for user_id {user_id} ({identifier}) updated to {status}.")
            return True
        except psycopg2.Error as e:
            print(f"Database error updating status for user_id {user_id} ({identifier}): {e}")
            if conn: conn.rollback()
            return False
        except Exception as e:
            print(f"Unexpected error updating status for user_id {user_id} ({identifier}): {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: self.connection_pool.putconn(conn)

    def get_chat_sessions_for_user(self, user_email: str) -> List[Dict[str, Any]]:
        """
        Get all distinct chat sessions for a user, ordered by the most recent message in each session.
        Args:
            user_email: The email of the user.
        Returns:
            A list of dictionaries, each representing a chat session 
            (e.g., {'session_id': str, 'last_message_timestamp': datetime, 'first_message_preview': str}).
        """
        user = self.get_user_by_email(user_email)
        if not user:
            print(f"get_chat_sessions_for_user: No user found for email {user_email}")
            return []
        user_id = user['user_id']

        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # This query finds all session_ids for the user,
                # the timestamp of the last message in each session,
                # and the content of the first message in each session for preview.
                cursor.execute("""
                    WITH UserChatSessions AS (
                        SELECT DISTINCT session_id
                        FROM fi_messages
                        WHERE user_id = %s
                    ),
                    LastMessageInSession AS (
                        SELECT 
                            session_id, 
                            MAX(timestamp) as last_message_timestamp
                        FROM fi_messages
                        WHERE user_id = %s
                        GROUP BY session_id
                    ),
                    FirstMessageInSession AS (
                        SELECT 
                            session_id, 
                            content as first_message_content,
                            ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp ASC) as rn
                        FROM fi_messages
                        WHERE user_id = %s
                    )
                    SELECT 
                        ucs.session_id,
                        lmis.last_message_timestamp,
                        fmis.first_message_content
                    FROM UserChatSessions ucs
                    JOIN LastMessageInSession lmis ON ucs.session_id = lmis.session_id
                    LEFT JOIN FirstMessageInSession fmis ON ucs.session_id = fmis.session_id AND fmis.rn = 1
                    ORDER BY lmis.last_message_timestamp DESC;
                """, (user_id, user_id, user_id))
                
                sessions = cursor.fetchall()
                return [dict(session) for session in sessions]
        except Exception as e:
            print(f"Error in get_chat_sessions_for_user for email {user_email}: {e}")
            return []
        finally:
            if conn: self.connection_pool.putconn(conn)
            
    def get_conversations_by_date_and_users(self, start_date: str, start_hour: int, 
                                           end_date: str, end_hour: int, 
                                           user_ids: list = None, min_messages: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch conversations based on date range and user selection
        
        Args:
            start_date: Start date in format 'YYYY-MM-DD'
            start_hour: Start hour (0-23)
            end_date: End date in format 'YYYY-MM-DD'
            end_hour: End hour (0-23)
            user_ids: List of user IDs to filter by, or None for all users
            min_messages: Minimum number of messages for a conversation to be included (default: 1)
            
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
                    # We need to create naive datetimes first, then make them timezone-aware
                    start_dt = datetime.strptime(f"{start_date} {start_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
                    # Use localize to add timezone info without conversion
                    start_dt = sf_timezone.localize(start_dt)
                    
                    end_dt = datetime.strptime(f"{end_date} {end_hour:02d}:59:59", "%Y-%m-%d %H:%M:%S") 
                    end_dt = sf_timezone.localize(end_dt)
                    
                    # Format for database query - make sure it's in the correct timezone format
                    # We'll use ISO format which includes timezone information
                    start_datetime = start_dt.strftime("%Y-%m-%d %H:%M:%S %z")
                    end_datetime = end_dt.strftime("%Y-%m-%d %H:%M:%S %z")
                    
                    print(f"Using timezone-aware dates: {start_datetime} to {end_datetime}")
                except ValueError as e:
                    print(f"Error parsing dates: {e}")
                    # Fallback to simple string construction
                    start_datetime = f"{start_date} {start_hour:02d}:00:00"
                    end_datetime = f"{end_date} {end_hour:02d}:59:59"
                
                # Base query to get all messages within the date range
                query = """
                    SELECT 
                        m.message_id, 
                        m.session_id,  -- Changed from m.session_id
                        m.user_id, 
                        m.content, 
                        m.role, 
                        m.timestamp,
                        u.email as user_email, -- Added user_email
                        u.session_id as user_legacy_session_id -- Clarified u.session_id
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
                    session_id = row['session_id'] # Changed from session_id
                    
                    if session_id not in conversations:
                        conversations[session_id] = {
                            'session_id': session_id, # Changed from session_id
                            'user_id': row['user_id'],
                            'user_email': row['user_email'], # Added
                            'user_legacy_session_id': row['user_legacy_session_id'], # Added for context
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
                
                # Filter out conversations with fewer than min_messages
                filtered_conversations = []
                for conv in conversations.values():
                    if conv['message_count'] >= min_messages:
                        filtered_conversations.append(conv)
                    else:
                        print(f"Skipping conversation {conv['session_id']} with only {conv['message_count']} message(s)") # Changed from session_id
                
                return filtered_conversations
                
        except Exception as e:
            print(f"Error fetching conversations: {e}")
            return []
        finally:
            self.connection_pool.putconn(conn)
    
    def create_conversation_summary(self, session_id: str, user_email: str) -> Optional[str]: # Added user_email, session_id is now session_id
        """
        Create a summary for a conversation using GPT-4o
        
        Args:
            session_id: The chat session ID of the conversation
            user_email: The email of the user associated with the conversation.
            
        Returns:
            Summary text if successful, None if failed
        """
        user_info = self.get_user_by_email(user_email)
        if not user_info:
            print(f"Cannot create summary: User not found for email {user_email}")
            return None
        user_id = user_info['user_id']

        conn = self.connection_pool.getconn()
        try:
            # First check if summary already exists
            with conn.cursor() as cursor:
                cursor.execute("SELECT summary_id FROM fi_summary WHERE session_id = %s AND user_id = %s", (session_id, user_id)) # Check with user_id too
                if cursor.fetchone():
                    print(f"Summary already exists for chat {session_id} by user {user_id}")
                    return None # Or fetch existing summary
                
                # Check if there are any messages in this conversation
                cursor.execute("SELECT COUNT(*) FROM fi_messages WHERE session_id = %s AND user_id = %s", (session_id, user_id))
                message_count = cursor.fetchone()[0]
                if message_count == 0:
                    print(f"Skipping summary generation for chat {session_id}: No messages found")
                    return None
            
            # Get all messages for this session
            messages_text = self.get_messages_for_summary(session_id, user_id) # Pass user_id for context
            if not messages_text:
                print(f"No messages found for chat {session_id}")
                return None
            
            # Generate summary using GPT-4o
            try:
                summary_content = self.generate_summary_with_gpt4o(messages_text)
                
                # Store summary in database
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO fi_summary (session_id, user_id, created_at, summary) VALUES (%s, %s, %s, %s) RETURNING summary_id",
                        (session_id, user_id, get_sf_time(), summary_content)
                    )
                    summary_id = cursor.fetchone()[0]
                conn.commit()
                print(f"Summary created for chat {session_id}, user_id {user_id}. Summary ID: {summary_id}")
                return summary_content
            except Exception as e:
                print(f"Error generating summary: {e}")
                return None
                
        except Exception as e:
            print(f"Error creating summary: {e}")
            if 'conn' in locals():
                conn.rollback()
            return None
        finally:
            self.connection_pool.putconn(conn)
    
    def get_messages_for_summary(self, session_id: str, user_id: Optional[int] = None) -> str: # user_id is optional but recommended
        """
        Get all messages for a session formatted for summarization
        
        Args:
            session_id: The chat session ID to get messages for
            user_id: Optional user_id to scope messages further if needed.
            
        Returns:
            Formatted string of all messages
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                query = "SELECT role, content, timestamp FROM fi_messages WHERE session_id = %s"
                params = [session_id]
                if user_id is not None: # If user_id is provided, add it to the query
                    query += " AND user_id = %s"
                    params.append(user_id)
                query += " ORDER BY timestamp"
                
                cursor.execute(query, tuple(params))
                messages = cursor.fetchall()
                
                if not messages:
                    return ""
                
                # Format messages for the summary
                formatted_messages = []
                for role, content, timestamp in messages:
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "Unknown time"
                    formatted_messages.append(f"[{time_str}] {role.upper()}: {content}")
                
                return "\n\n".join(formatted_messages)
        except Exception as e:
            print(f"Error getting messages for summary: {e}")
            return ""
        finally:
            self.connection_pool.putconn(conn)
    
    def generate_summary_with_gpt4o(self, messages_text: str) -> str:
        """
        Generate a summary of conversation using OpenAI GPT-4o
        
        Args:
            messages_text: Formatted text of all messages in the conversation
            
        Returns:
            Generated summary
        """
        try:
            prompt = f"""Please summarize the following conversation in a concise, professional manner. 
Focus on the main topics discussed, key questions, and important conclusions or actions.
Keep the summary under 200 words.

CONVERSATION:
{messages_text}

SUMMARY:"""

            # Call OpenAI API with GPT-4o
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations accurately and concisely."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10000,
                temperature=0.5
            )
            
            # Extract the summary from the response
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return f"Failed to generate summary: {str(e)}"
    
    def get_summaries_for_sessions(self, session_ids: List[str]) -> Dict[str, str]:
        """
        Get existing summaries for a list of session IDs
        
        Args:
            session_ids: List of session IDs to get summaries for
            
        Returns:
            Dictionary mapping session_id to summary
        """
        if not session_ids:
            return {}
            
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(session_ids))
                query = f"SELECT session_id, summary FROM fi_summary WHERE session_id IN ({placeholders})"
                cursor.execute(query, session_ids)
                
                results = cursor.fetchall()
                return {row[0]: row[1] for row in results}
        except Exception as e:
            print(f"Error fetching summaries: {e}")
            return {}
        finally:
            self.connection_pool.putconn(conn)
            
    def get_all_summaries(self, limit: int = 100, with_user_info: bool = True) -> List[Dict[str, Any]]:
        """
        Get all conversation summaries from the database
        
        Args:
            limit: Maximum number of summaries to retrieve
            with_user_info: Whether to include user information
            
        Returns:
            List of summary objects with metadata
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                if with_user_info:
                    # Query with user info joined
                    query = """
                        SELECT 
                            s.summary_id, 
                            s.session_id, -- Changed from s.session_id
                            s.user_id, 
                            s.created_at, 
                            s.summary,
                            u.email as user_email, -- Added user_email
                            u.status,
                            u.last_active,
                            u.logged
                        FROM 
                            fi_summary s
                        LEFT JOIN 
                            fi_users u ON s.user_id = u.user_id
                        ORDER BY 
                            s.created_at DESC
                        LIMIT %s
                    """
                else:
                    # Simple query without user info
                    query = """
                        SELECT 
                            summary_id, 
                            session_id, -- Changed from session_id
                            user_id, 
                            created_at, 
                            summary
                        FROM 
                            fi_summary
                        ORDER BY 
                            created_at DESC
                        LIMIT %s
                    """
                
                cursor.execute(query, (limit,))
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                summaries = [dict(row) for row in results]
                
                return summaries
        except Exception as e:
            print(f"Error fetching all summaries: {e}")
            return []
        finally:
            self.connection_pool.putconn(conn)
            
    def get_summaries_by_date_range(self, start_date: str, start_hour: int, 
                                   end_date: str, end_hour: int,
                                   user_ids: list = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get summaries filtered by date range and user IDs
        
        Args:
            start_date: Start date in format 'YYYY-MM-DD'
            start_hour: Start hour (0-23)
            end_date: End date in format 'YYYY-MM-DD'
            end_hour: End hour (0-23)
            user_ids: List of user IDs to filter by, or None for all users
            limit: Maximum number of summaries to retrieve
            
        Returns:
            List of summary objects with metadata
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Parse input dates and convert to SF timezone
                try:
                    # Convert string dates to proper datetime objects with SF timezone
                    start_dt = datetime.strptime(f"{start_date} {start_hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
                    start_dt = sf_timezone.localize(start_dt)
                    
                    end_dt = datetime.strptime(f"{end_date} {end_hour:02d}:59:59", "%Y-%m-%d %H:%M:%S") 
                    end_dt = sf_timezone.localize(end_dt)
                    
                    # Format for database query
                    start_datetime = start_dt.strftime("%Y-%m-%d %H:%M:%S %z")
                    end_datetime = end_dt.strftime("%Y-%m-%d %H:%M:%S %z")
                    
                    print(f"Using timezone-aware dates: {start_datetime} to {end_datetime}")
                except ValueError as e:
                    print(f"Error parsing dates: {e}")
                    # Fallback to simple string construction
                    start_datetime = f"{start_date} {start_hour:02d}:00:00"
                    end_datetime = f"{end_date} {end_hour:02d}:59:59"
                
                # Base query
                query = """
                    SELECT 
                        s.summary_id, 
                        s.session_id, -- Changed from s.session_id 
                        s.user_id, 
                        s.created_at, 
                        s.summary,
                        u.email as user_email, -- Added user_email
                        u.status,
                        u.last_active,
                        u.logged
                    FROM 
                        fi_summary s
                    LEFT JOIN 
                        fi_users u ON s.user_id = u.user_id
                    WHERE 
                        s.created_at BETWEEN %s AND %s
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
                        query += f" AND s.user_id IN ({placeholders})"
                        params.extend(int_user_ids)
                
                # Add ordering and limit
                query += """
                    ORDER BY 
                        s.created_at DESC
                    LIMIT %s
                """
                params.append(limit)
                
                # Execute query
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                summaries = [dict(row) for row in results]
                
                return summaries
        except Exception as e:
            print(f"Error fetching summaries by date range: {e}")
            return []
        finally:
            self.connection_pool.putconn(conn)
    
    def save_analysis_results(self, analysis_results: List[Dict[str, Any]]) -> bool:
        """
        Save analysis results for multiple summaries
        
        Args:
            analysis_results: List of analysis result dictionaries, each containing summary_id and analysis data
            
        Returns:
            Success boolean
        """
        if not analysis_results:
            return False
            
        conn = self.connection_pool.getconn()
        try:
            # Create fi_analysis table if it doesn't exist
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fi_analysis (
                        analysis_id SERIAL PRIMARY KEY,
                        summary_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        analysis JSONB NOT NULL,
                        FOREIGN KEY (summary_id) REFERENCES fi_summary(summary_id)
                    );
                """)
                conn.commit()
                
                # Insert analysis results
                for result in analysis_results:
                    if 'summary_id' not in result or 'analysis' not in result:
                        print(f"Skipping analysis result - missing required fields")
                        continue
                        
                    # Check if analysis already exists for this summary
                    cursor.execute(
                        "SELECT analysis_id FROM fi_analysis WHERE summary_id = %s",
                        (result['summary_id'],)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing analysis
                        cursor.execute(
                            "UPDATE fi_analysis SET analysis = %s, created_at = %s WHERE summary_id = %s",
                            (result['analysis'], get_sf_time(), result['summary_id'])
                        )
                    else:
                        # Insert new analysis
                        cursor.execute(
                            "INSERT INTO fi_analysis (summary_id, created_at, analysis) VALUES (%s, %s, %s)",
                            (result['summary_id'], get_sf_time(), result['analysis'])
                        )
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving analysis results: {e}")
            if 'conn' in locals():
                conn.rollback()
            return False
        finally:
            self.connection_pool.putconn(conn)
    
    def get_analysis_for_summary(self, summary_id: int) -> Optional[Dict[str, Any]]:
        """
        Get analysis results for a specific summary
        
        Args:
            summary_id: ID of the summary to get analysis for
            
        Returns:
            Analysis data dictionary or None if not found
        """
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM fi_analysis WHERE summary_id = %s",
                    (summary_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    return dict(result)
                else:
                    return None
        except Exception as e:
            print(f"Error fetching analysis for summary {summary_id}: {e}")
            return None
        finally:
            self.connection_pool.putconn(conn)


