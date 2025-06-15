"""
Singleton Database Manager for FastInnovation
Ensures only one database adapter instance is created and shared across the application.
"""

import asyncio
from utils.async_database import AsyncDatabaseAdapter
from typing import Optional

class DatabaseManager:
    """Singleton manager for async database adapter instance."""
    
    _instance: Optional[AsyncDatabaseAdapter] = None
    _initialized: bool = False
    
    @classmethod
    async def get_instance(cls) -> AsyncDatabaseAdapter:
        """Get the singleton async database adapter instance."""
        if cls._instance is None:
            print("🔄 Creating shared async database adapter instance...")
            cls._instance = AsyncDatabaseAdapter()
            await cls._instance.init_pool()
            cls._initialized = True
            print("✅ Shared async database adapter instance created successfully")
        return cls._instance
    
    @classmethod
    async def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing purposes)."""
        if cls._instance:
            # Clean up existing connection pool
            await cls._instance.close()
            cls._instance = None
            cls._initialized = False
            print("🔄 Async database adapter instance reset")

# Convenience function for easy import
async def get_db() -> AsyncDatabaseAdapter:
    """Get the shared async database adapter instance."""
    return await DatabaseManager.get_instance() 