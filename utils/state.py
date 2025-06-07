"""
Global application state management for FastInnovation.
"""

import json
import uuid
from datetime import datetime
import base64
import bcrypt
import time
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from nicegui import app, ui
from utils.firebase_auth import FirebaseAuth
from utils.database_singleton import get_db
from pytz import timezone

# Initialize timezone for San Francisco
sf_timezone = timezone('America/Los_Angeles')

# Initialize components using singleton database - made lazy to avoid module-level initialization
# db_adapter = get_db()

# Global state variables
logout = False

def get_user_logout_state():
    return logout

def set_user_logout_state(value: bool):
    global logout
    logout = value


# User status tracking
async def update_user_status(identifier: str, status: str, is_email: bool = False):
    """Update the status of a user in the database.
       If is_email is False, identifier is treated as a legacy session_id.
    """
    # Get async database adapter
    db_adapter = await get_db()
    await db_adapter.update_user_status(identifier, status, is_email=is_email)
