from utils.database import PostgresAdapter
from datetime import datetime, timezone
import uuid

# Singleton instance for database operations
db = PostgresAdapter()

def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())

def check_or_create_user(browser_cookie_id: str | None = None) -> dict:
    """
    Check if user exists or create a new one based on browser cookie.
    Returns user info including session_id and visit count.
    """
    conn = db.connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            if browser_cookie_id:
                # Check for existing user
                cursor.execute("""
                    SELECT user_id, session_id, logged, explorations_completed 
                    FROM fi_users 
                    WHERE session_id = %s
                """, (browser_cookie_id,))
                user = cursor.fetchone()
                
                if user:
                    user_id, session_id, is_logged, visits = user
                    if not is_logged:
                        # User exists but is logged out - create new session
                        new_session_id = generate_session_id()
                        cursor.execute("""
                            UPDATE fi_users 
                            SET session_id = %s, 
                                last_active = %s,
                                explorations_completed = 1,
                                status = 'Active'
                            WHERE user_id = %s
                        """, (new_session_id, datetime.now(timezone.utc), user_id))
                        conn.commit()
                        return {
                            'user_id': user_id,
                            'session_id': new_session_id,
                            'visits': 1,
                            'is_new': False
                        }
                    else:
                        # User exists and is logged in - increment visits
                        cursor.execute("""
                            UPDATE fi_users 
                            SET last_active = %s,
                                explorations_completed = explorations_completed + 1
                            WHERE user_id = %s
                        """, (datetime.now(timezone.utc), user_id))
                        conn.commit()
                        return {
                            'user_id': user_id,
                            'session_id': session_id,
                            'visits': visits + 1,
                            'is_new': False
                        }

            # No cookie or user not found - create new user
            new_session_id = generate_session_id()
            cursor.execute("""
                INSERT INTO fi_users (
                    session_id, 
                    status,
                    last_active,
                    explorations_completed,
                    logged
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING user_id
            """, (new_session_id, 'Active', datetime.now(timezone.utc), 1, True))
            user_id = cursor.fetchone()[0]
            conn.commit()
            
            return {
                'user_id': user_id,
                'session_id': new_session_id,
                'visits': 1,
                'is_new': True
            }
    finally:
        db.connection_pool.putconn(conn)

def logout_user(session_id: str) -> bool:
    """
    Logout user, updating their status and logged flag.
    Returns success status.
    """
    conn = db.connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE fi_users 
                SET status = 'Idle',
                    logged = false,
                    last_active = %s
                WHERE session_id = %s
            """, (datetime.now(timezone.utc), session_id))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        db.connection_pool.putconn(conn)

def get_user_visit_count(session_id: str) -> int:
    """Get the number of visits for a user."""
    conn = db.connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT explorations_completed 
                FROM fi_users 
                WHERE session_id = %s
            """, (session_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    finally:
        db.connection_pool.putconn(conn)

def get_all_users():
    """Get all users (returns list of dicts)."""
    # You may want to add this to PostgresAdapter if not present
    conn = db.connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM fi_users ORDER BY user_id")
            rows = cursor.fetchall()
            return [dict(zip([desc[0] for desc in cursor.description], row)) for row in rows]
    finally:
        db.connection_pool.putconn(conn)

def remove_user(session_id: str) -> bool:
    """Remove a user by session_id."""
    conn = db.connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM fi_users WHERE session_id = %s", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        db.connection_pool.putconn(conn)

