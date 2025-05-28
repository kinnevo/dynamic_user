#!/usr/bin/env python3
"""
Test script for the unified database adapter.
This will help verify the new schema is working correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.unified_database import UnifiedDatabaseAdapter

def test_database_connection():
    """Test the database connection and basic operations."""
    print("🚀 Testing Unified Database Adapter...")
    
    try:
        # Initialize the adapter
        print("1️⃣ Initializing UnifiedDatabaseAdapter...")
        db = UnifiedDatabaseAdapter()
        print("✅ Database adapter initialized successfully!")
        
        # Test user creation
        print("\n2️⃣ Testing user creation...")
        test_email = "test@example.com"
        user_id = db.get_or_create_user_by_email(
            email=test_email,
            firebase_uid="test_firebase_uid_123",
            display_name="Test User"
        )
        
        if user_id:
            print(f"✅ User created/found with ID: {user_id}")
        else:
            print("❌ Failed to create/find user")
            return False
        
        # Test conversation creation
        print("\n3️⃣ Testing conversation creation...")
        thread_id = db.create_conversation(
            user_id=user_id,
            title="Test Conversation"
        )
        
        if thread_id:
            print(f"✅ Conversation created with thread_id: {thread_id}")
        else:
            print("❌ Failed to create conversation")
            return False
        
        # Test message saving
        print("\n4️⃣ Testing message saving...")
        message_id = db.save_message(
            user_email=test_email,
            session_id=thread_id,
            content="Hello, this is a test message!",
            role="user"
        )
        
        if message_id:
            print(f"✅ Message saved with ID: {message_id}")
        else:
            print("❌ Failed to save message")
            return False
        
        # Test getting conversation history
        print("\n5️⃣ Testing conversation history retrieval...")
        history = db.get_conversation_history(thread_id)
        
        if history and len(history) > 0:
            print(f"✅ Retrieved conversation history: {len(history)} messages")
            for msg in history:
                print(f"   - {msg['role']}: {msg['content'][:50]}...")
        else:
            print("❌ Failed to retrieve conversation history")
            return False
        
        # Test getting user sessions
        print("\n6️⃣ Testing user sessions retrieval...")
        sessions = db.get_chat_sessions_for_user(test_email)
        
        if sessions:
            print(f"✅ Retrieved {len(sessions)} chat sessions for user")
            for session in sessions:
                print(f"   - Session: {session['session_id'][:8]}... ({session.get('message_count', 0)} messages)")
        else:
            print("⚠️ No chat sessions found (this might be expected)")
        
        print("\n🎉 All tests passed! The unified database is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_environment():
    """Check if environment variables are properly set."""
    print("🔍 Checking environment configuration...")
    
    load_dotenv()
    
    # Check for required environment variables
    required_vars = [
        'POSTGRES_HOST',
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'POSTGRES_PORT'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Make sure you have a .env file with the required database configuration.")
        return False
    
    use_cloud_sql = os.getenv("USE_CLOUD_SQL", "false").lower() == "true"
    environment = os.getenv("ENVIRONMENT", "development")
    
    print(f"✅ Environment: {environment}")
    print(f"✅ Use Cloud SQL: {use_cloud_sql}")
    
    if use_cloud_sql:
        print("🌩️ Cloud SQL mode enabled")
        cloud_vars = ['CLOUD_SQL_USERNAME', 'CLOUD_SQL_PASSWORD', 'CLOUD_SQL_DATABASE_NAME']
        if environment == "production":
            cloud_vars.append('CLOUD_SQL_CONNECTION_NAME')
        
        missing_cloud_vars = [var for var in cloud_vars if not os.getenv(var)]
        if missing_cloud_vars:
            print(f"❌ Missing Cloud SQL variables: {', '.join(missing_cloud_vars)}")
            return False
    else:
        print("🏠 Local PostgreSQL mode enabled")
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("         UNIFIED DATABASE ADAPTER TEST")
    print("=" * 60)
    
    # Check environment first
    if not check_environment():
        print("\n❌ Environment check failed. Please fix configuration and try again.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    
    # Run database tests
    if test_database_connection():
        print("\n🎉 SUCCESS: All database tests passed!")
        sys.exit(0)
    else:
        print("\n❌ FAILURE: Some database tests failed!")
        sys.exit(1) 