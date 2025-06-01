"""
Singleton Database Manager for FastInnovation
Ensures only one database adapter instance is created and shared across the application.
"""

from utils.unified_database import UnifiedDatabaseAdapter
from typing import Optional

class DatabaseManager:
    """Singleton manager for database adapter instance."""
    
    _instance: Optional[UnifiedDatabaseAdapter] = None
    _initialized: bool = False
    
    @classmethod
    def get_instance(cls) -> UnifiedDatabaseAdapter:
        """Get the singleton database adapter instance."""
        if cls._instance is None:
            print("🔄 Creating shared database adapter instance...")
            cls._instance = UnifiedDatabaseAdapter()
            cls._initialized = True
            print("✅ Shared database adapter instance created successfully")
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing purposes)."""
        if cls._instance:
            # Clean up existing connection pool
            if hasattr(cls._instance, 'connection_pool'):
                cls._instance.connection_pool.closeall()
            cls._instance = None
            cls._initialized = False
            print("🔄 Database adapter instance reset")

# Convenience function for easy import
def get_db() -> UnifiedDatabaseAdapter:
    """Get the shared database adapter instance."""
    return DatabaseManager.get_instance() 