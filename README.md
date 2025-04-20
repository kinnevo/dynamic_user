# Dynamic User Chat Application

A web application for dynamic user chat sessions powered by Langflow API integration.

## Features

- User session management with automatic registration
- Chat interface with Langflow API integration
- PostgreSQL database for persistent storage
- Singleton pattern for efficient resource management
- Responsive web UI built with NiceGUI

## Setup and Installation

### Setup the virtual environment

```bash
# Install uv package manager
pip install uv

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### Database Configuration

The application now uses PostgreSQL instead of SQLite. Make sure you have PostgreSQL installed and configured properly before running the application.

Set the following environment variables for database connection:
- `DB_USER`: PostgreSQL username
- `DB_PASSWORD`: PostgreSQL password
- `DB_HOST`: PostgreSQL host (default: localhost)
- `DB_PORT`: PostgreSQL port (default: 5432)
- `DB_NAME`: PostgreSQL database name

### Run the application

```bash
python main.py
```

The application will be accessible at http://localhost:8080

To deactivate the virtual environment when done:
```bash
deactivate
```

## Technical Architecture

- **Framework**: NiceGUI for building the web interface
- **Database**: PostgreSQL with connection pooling
- **API Integration**: Langflow client with singleton pattern for efficient connection management
- **State Management**: Global application state
- **UI Components**: Modular page components with consistent styling

## Recent Changes

- Migrated from SQLite to PostgreSQL for improved performance and scalability
- Implemented singleton pattern for LangflowClient to prevent multiple API connections
- Added foreign key constraints for data integrity
- Improved session handling and connection pooling
- Updated application navigation structure with home page as landing screen
- Enhanced navigation menu with consistent access to all pages

## Application Structure

- **Home Page** (`/home`): Landing page with application introduction and "Get Started" button
- **Chat Page** (`/chat`): Interactive chat interface with Langflow API integration
- **Reports Page** (`/reportes`): Analytics and administration features

The navigation flow starts at the home page, with users being directed to the chat interface when they click the main call-to-action button.
