# Dynamic User - FastInnovation Frontend

A modern web application for AI-powered innovation processes with Firebase authentication and Google Cloud SQL integration. Users interact with AI assistants through guided conversation flows to accelerate innovation and decision-making.

## Features

- **Firebase Authentication**: Secure user registration, login, and session management
- **Multi-Conversation Support**: Users can maintain multiple innovation threads simultaneously
- **AI-Powered Guidance**: Integration with LLM services for innovation process facilitation
- **Cloud SQL Integration**: Scalable database backend with Google Cloud SQL support
- **Real-time Analytics**: Integration with analytics API for insights and reporting
- **Responsive UI**: Modern, intuitive interface built with NiceGUI
- **Session Persistence**: Conversation history and progress tracking across sessions

## Tech Stack

- **NiceGUI**: Modern Python web framework for interactive UIs
- **Firebase**: Authentication and user management
- **Google Cloud SQL**: Scalable PostgreSQL database
- **AsyncPG**: High-performance async PostgreSQL driver
- **OpenAI/Anthropic**: AI language model integrations
- **LangChain**: AI workflow orchestration
- **Docker**: Containerized deployment

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Browser  │    │  Dynamic User    │    │  Analytics API  │
│                 │◄──►│   (Frontend)     │◄──►│   (Backend)     │
│ • Authentication│    │                  │    │                 │
│ • Chat Interface│    │ • NiceGUI        │    │ • FastAPI       │
│ • User Sessions │    │ • Firebase Auth  │    │ • Data Analytics│
└─────────────────┘    │ • Cloud SQL      │    │ • AI Processing │
                       └──────────────────┘    └─────────────────┘
                                │                        │
                       ┌────────▼────────┐    ┌─────────▼─────────┐
                       │    Firebase     │    │  Google Cloud SQL │
                       │ Authentication  │    │   (PostgreSQL)    │
                       └─────────────────┘    └───────────────────┘
```

## Database Schema

The application uses a unified schema optimized for Firebase integration:

- **users**: Firebase UID, email, display name, activity tracking
- **conversations**: Chat threads with innovation process stages
- **messages**: Individual messages with role, content, and metadata
- **summaries**: AI-generated conversation summaries
- **analyses**: Advanced analytics and insights

## Setup and Installation

### Prerequisites

- Python 3.9+
- Firebase project with authentication enabled
- PostgreSQL (local) or Google Cloud SQL instance
- OpenAI API key (or other LLM provider)

### Local Development Setup

1. **Clone and Install Dependencies**
   ```bash
   git clone <repository>
   cd dynamic_user
   
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Firebase Configuration**
   ```bash
   # Set up Firebase project at https://console.firebase.google.com
   # Enable Authentication with Email/Password
   # Download service account key JSON file
   
   # Option 1: Save service account JSON file
   cp path/to/serviceaccount.json firebase-serviceaccount.json
   
   # Option 2: Use environment variable
   export FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
   ```

3. **Database Setup**
   ```bash
   # Local PostgreSQL
   createdb fastinnovation
   
   # Or use existing Cloud SQL instance
   # (See Cloud SQL setup section below)
   ```

4. **Environment Configuration**
   ```bash
   cp env.example .env
   # Edit .env with your configuration:
   # - Firebase credentials
   # - Database connection details
   # - OpenAI API key
   ```

5. **Run Application**
   ```bash
   python main.py
   ```
   
   The application will be available at http://localhost:8080

### Google Cloud SQL Setup

1. **Create Cloud SQL Instance**
   ```bash
   # Create PostgreSQL instance
   gcloud sql instances create fastinnovation-db \
     --database-version=POSTGRES_14 \
     --tier=db-f1-micro \
     --region=us-central1
   
   # Create database
   gcloud sql databases create fastinnovation \
     --instance=fastinnovation-db
   
   # Set up user
   gcloud sql users create appuser \
     --instance=fastinnovation-db \
     --password=secure-password
   ```

2. **Update Environment Configuration**
   ```bash
   # .env file
   USE_CLOUD_SQL=true
   CLOUD_SQL_CONNECTION_NAME=your-project:us-central1:fastinnovation-db
   CLOUD_SQL_DATABASE_NAME=fastinnovation
   CLOUD_SQL_USERNAME=appuser
   CLOUD_SQL_PASSWORD=secure-password
   ```

3. **Local Development with Cloud SQL**
   ```bash
   # Install Cloud SQL Proxy
   gcloud sql connections create tcp appuser \
     --instance=fastinnovation-db \
     --port=5432
   
   # Run proxy (in separate terminal)
   cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432
   ```

## Environment Configuration

Key environment variables (see `env.example` for complete list):

```bash
# Environment
ENVIRONMENT=development  # development, staging, production

# Firebase Authentication
FIREBASE_API_KEY=your-firebase-web-api-key
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}

# Database
USE_CLOUD_SQL=false  # Set to true for Cloud SQL
POSTGRES_HOST=localhost
POSTGRES_DB=fastinnovation
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# AI Integration
OPENAI_API_KEY=your-openai-api-key

# Analytics API (optional)
ANALYTICS_API_URL=http://localhost:8000
```

## User Authentication Flow

1. **Registration**
   - User provides email and password
   - Firebase creates user account
   - System creates user record in Cloud SQL with Firebase UID

2. **Login**
   - Firebase authenticates user credentials
   - System validates Firebase ID token
   - User session established with Cloud SQL integration

3. **Session Management**
   - Firebase ID tokens refreshed automatically
   - User activity tracked in database
   - Conversation threads linked to Firebase UID

## 🚀 **Cloud Deployment**

This application is designed for deployment on Google Cloud Run with automated setup.

### **Quick Deployment**

Use the automated deployment script:

```bash
# Make script executable
chmod +x deploy-to-cloud-run.sh

# Deploy to Cloud Run
./deploy-to-cloud-run.sh
```

The script automatically:
- Deploys to Google Cloud Run
- Configures all environment variables
- Sets up Cloud SQL connection
- Grants necessary IAM permissions
- Provides the service URL

### **Service Configuration**
- **Service Name:** `dynamic-user`
- **Region:** `us-central1`
- **Access:** Publicly accessible (unauthenticated)
- **Resources:** 2Gi memory, 2 CPU cores
- **Database:** Cloud SQL PostgreSQL with Python Connector

### **Service URLs**
- **Production:** https://dynamic-user-604277815223.us-central1.run.app
- **Health Check:** https://dynamic-user-604277815223.us-central1.run.app/health

For detailed deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Conversation Management

### Creating New Conversations
- Users can start multiple innovation threads
- Each conversation gets unique thread_id
- Conversations linked to user via Firebase UID

### Message Flow
1. User sends message through UI
2. Message saved to Cloud SQL with conversation context
3. AI processes message and generates response
4. Response saved and displayed to user
5. Conversation state updated

### Analytics Integration
- Real-time conversation analytics
- User engagement tracking
- Innovation process insights
- Integration with analytics API

## Migration from Legacy System

If migrating from the old schema:

1. **Backup Existing Data**
   ```bash
   cd ../analytics_api/migrations
   python migrate_to_unified_schema.py --backup
   ```

2. **User Migration Process**
   - Export user emails from old system
   - Have users register with Firebase using same emails
   - System automatically links new Firebase UIDs to conversation history

3. **Data Mapping**
   - Old session_ids become conversation thread_ids
   - User messages preserved with proper attribution
   - Conversation context maintained

## Deployment

### Docker Deployment
```bash
# Build image
docker build -t dynamic-user .

# Run with environment file
docker run -d \
  --env-file .env \
  -p 8080:8080 \
  dynamic-user
```

### Google Cloud Run Deployment
```bash
# Deploy to Cloud Run
gcloud run deploy dynamic-user \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="USE_CLOUD_SQL=true,ENVIRONMENT=production"

# Connect to Cloud SQL
gcloud run services update dynamic-user \
  --add-cloudsql-instances=PROJECT:REGION:INSTANCE \
  --region=us-central1
```

## Development

### Code Structure
```
dynamic_user/
├── pages/                 # NiceGUI page components
│   ├── login.py          # Authentication pages
│   ├── chat.py           # Main chat interface
│   ├── home.py           # Landing page
│   └── admin.py          # Admin interface
├── utils/                # Core utilities
│   ├── cloud_sql_adapter.py   # Database operations
│   ├── firebase_auth.py       # Authentication logic
│   ├── auth_middleware.py     # Auth decorators
│   └── message_router.py      # Message handling
├── static/               # Static assets
├── main.py              # Application entry point
└── requirements.txt     # Dependencies
```

### Testing
```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=utils tests/
```

### Code Quality
```bash
# Format code
black .
isort .

# Lint
flake8
```

## Security Considerations

- **Authentication**: Firebase handles secure authentication
- **Authorization**: User actions validated against Firebase UID
- **Data Protection**: All database connections encrypted
- **Session Security**: Short-lived tokens with automatic refresh
- **Input Validation**: User inputs sanitized and validated

## Monitoring and Logging

- **Application Logs**: Structured logging with user context
- **Performance Metrics**: Response times and user engagement
- **Error Tracking**: Automatic error reporting and alerting
- **Analytics**: User behavior and conversation insights

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Ensure code quality standards
5. Submit pull request

## License

This project is licensed under the MIT License.
