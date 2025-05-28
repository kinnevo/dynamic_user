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
from utils.unified_database import UnifiedDatabaseAdapter
from pytz import timezone

# Initialize timezone for San Francisco
sf_timezone = timezone('America/Los_Angeles')

# Global database adapter instance
db_adapter = UnifiedDatabaseAdapter()

# Global state variables
logout = False

def get_user_logout_state():
    return logout

def set_user_logout_state(value: bool):
    global logout
    logout = value


# User status tracking
def update_user_status(identifier: str, status: str, is_email: bool = False):
    """Update the status of a user in the database.
       If is_email is False, identifier is treated as a legacy session_id.
    """
    db_adapter.update_user_status(identifier, status, is_email=is_email)
