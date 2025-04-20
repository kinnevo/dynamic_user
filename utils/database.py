import os
from datetime import datetime
from typing import Optional, Dict, Any
from nicegui import app
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()

class UserDB:
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
        """Initialize the database with the conversations table."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS fi_conversations (
                        session_id VARCHAR(255) PRIMARY KEY,
                        username VARCHAR(255) NOT NULL,
                        save_time TIMESTAMP NOT NULL,
                        conversation_history TEXT
                    );
                    CREATE TABLE IF NOT EXISTS fi_users (
                        user_id SERIAL PRIMARY KEY,
                        session_id VARCHAR(255) NOT NULL,
                        logged BOOLEAN NOT NULL DEFAULT FALSE
                    );
                ''')
            conn.commit()
        finally:
            self.connection_pool.putconn(conn)

    def create_conversation(self, session_id: str, username: str, conversation_history: str) -> bool:
        """Create a new conversation record."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO fi_conversations (session_id, username, save_time, conversation_history)
                    VALUES (%s, %s, %s, %s)
                ''', (session_id, username, datetime.now(), conversation_history))
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            return False
        finally:
            self.connection_pool.putconn(conn)

    def update_conversation(self, session_id: str, conversation_history: str) -> bool:
        """Update an existing conversation with new history."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE fi_conversations 
                    SET conversation_history = %s 
                    WHERE session_id = %s
                ''', (conversation_history, session_id))
            conn.commit()
            return True
        except psycopg2.Error:
            return False
        finally:
            self.connection_pool.putconn(conn)

    def get_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation details by session_id."""
        conn = self.connection_pool.getconn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute('SELECT * FROM fi_conversations WHERE session_id = %s', (session_id,))
                result = cursor.fetchone()
                if result:
                    return dict(result)
            return None
        finally:
            self.connection_pool.putconn(conn)

# Create a global instance
user_db = UserDB()

def save_db():
    session_id = app.storage.browser['session_id']
    username = app.storage.browser.get('username', 'Unknown User')
    conversation = str(app.storage.browser['conversation_history'])
    
    # Try to update first
    if not user_db.update_conversation(session_id, conversation):
        # If update fails, create new conversation
        user_db.create_conversation(session_id, username, conversation) 

def get_conversation(session_id: str) -> Optional[Dict[str, Any]]:
    """Get conversation details by session_id."""
    conn = user_db.connection_pool.getconn()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('SELECT * FROM conversations WHERE session_id = %s', (session_id,))
            result = cursor.fetchone()
            if result:
                return dict(result)
            return None
    finally:
        user_db.connection_pool.putconn(conn)

def create_user(session_id: str, logged: bool = True) -> int:
    """Create a new user and return the generated user_id."""
    conn = user_db.connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO fi_users (session_id, logged)
                VALUES (%s, %s)
                RETURNING user_id
            ''', (session_id, logged))
            user_id = cursor.fetchone()[0]
            conn.commit()
            return user_id
        
    finally:
        user_db.connection_pool.putconn(conn)

def get_user(session_id: str) -> Optional[Dict[str, Any]]:
    conn = user_db.connection_pool.getconn()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('SELECT * FROM fi_users WHERE session_id = %s', (session_id,))
            result = cursor.fetchone()
            if result:
                return dict(result) 
    finally:
        user_db.connection_pool.putconn(conn)
