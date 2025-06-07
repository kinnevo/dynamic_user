# 🚀 Cloud SQL Deployment Guide for FastInnovation Dynamic User App

## ✅ Changes Made

### 1. **Dependencies Updated**
- Added `cloud-sql-python-connector>=1.18.0` to `requirements.txt`
- This connector handles secure connections to Cloud SQL from Cloud Run

### 2. **Database Connection Logic Updated**
- **Development**: Uses Cloud SQL Proxy (127.0.0.1:5432) ✅ Working
- **Production**: Uses Cloud SQL Python Connector ✅ Ready for deployment

### 3. **Environment Variable Handling**
- Added `load_dotenv(override=True)` to force reading from .env file
- Fixed environment parsing to handle comments properly

## 🔧 Required for Cloud Run Deployment

### **1. IAM Permissions (CRITICAL)**

Your Cloud Run service account needs the Cloud SQL Client role:

```bash
# Find your service account
gcloud run services describe dynamic-user --region=us-central1 --format="value(spec.template.spec.serviceAccountName)"

# Grant Cloud SQL Client role (replace with your actual service account)
gcloud projects add-iam-policy-binding fast-innovation-460415 \
  --member="serviceAccount:604277815223-compute@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

### **2. Environment Variables for Cloud Run**

```bash
ENVIRONMENT=production
USE_CLOUD_SQL=true
CLOUD_SQL_CONNECTION_NAME=fast-innovation-460415:us-central1:fast-innovation-sandbox
CLOUD_SQL_DATABASE_NAME=fastinnovation
CLOUD_SQL_USERNAME=postgres
CLOUD_SQL_PASSWORD=fast_inn0_%

# Your API URLs (now properly configured)
ADMIN_API_URL_LOCAL=http://localhost:8000/api/v1
ADMIN_API_URL_PRODUCTION=https://fireportes-production.up.railway.app/api/v1
FI_ANALYTICS_API_KEY=your-api-key

FILC_API_URL_LOCAL=http://localhost:3000
FILC_API_URL_PRODUCTION=https://filc-production.up.railway.app
FILC_API_KEY=your-filc-key

# Other required vars
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
OPENAI_API_KEY=your-key
SECRET_KEY=your-secret
STORAGE_SECRET=your-storage-secret
```

### **3. Deploy Command**

```bash
gcloud run deploy dynamic-user \
  --source . \
  --region=us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances="fast-innovation-460415:us-central1:fast-innovation-sandbox" \
  --set-env-vars="ENVIRONMENT=production,USE_CLOUD_SQL=true,CLOUD_SQL_CONNECTION_NAME=fast-innovation-460415:us-central1:fast-innovation-sandbox,CLOUD_SQL_DATABASE_NAME=fastinnovation,CLOUD_SQL_USERNAME=postgres" \
  --set-secrets="CLOUD_SQL_PASSWORD=cloud-sql-password:latest,FIREBASE_SERVICE_ACCOUNT_JSON=firebase-service-account:latest,OPENAI_API_KEY=openai-api-key:latest,FI_ANALYTICS_API_KEY=analytics-api-key:latest,FILC_API_KEY=filc-api-key:latest,SECRET_KEY=app-secret-key:latest,STORAGE_SECRET=storage-secret-key:latest"
```

## 🔍 Verification

### **Local (Development) Mode**
```bash
# This should work now with your cloud_sql_proxy running
python3 -c "from utils.unified_database import UnifiedDatabaseAdapter; db = UnifiedDatabaseAdapter()"
```

**Expected output:**
```
🔧 Database Configuration:
   Environment: development
   Use Cloud SQL: True
   Connection method: Cloud SQL Proxy (127.0.0.1:5432)
✅ Unified database connection pool initialized for environment: development
```

### **Production Mode (on Cloud Run)**
When deployed, you should see:
```
🔧 Database Configuration:
   Environment: production
   Use Cloud SQL: True
   Connection method: Cloud SQL Connector
   Connection name: fast-innovation-460415:us-central1:fast-innovation-sandbox
✅ Unified database connection pool initialized for environment: production
```

## 🎯 What This Fixes

1. **No more Unix socket errors** - Uses Google's recommended Cloud SQL Python Connector
2. **Proper environment handling** - API URLs now correctly switch based on ENVIRONMENT setting
3. **Secure connections** - Connector handles all authentication and encryption
4. **Better error handling** - Clear logging shows which connection method is being used

## 🚨 Important Notes

- **IAM permissions are critical** - Without `roles/cloudsql.client`, you'll get 403 errors
- **Environment variable parsing is fixed** - No more issues with comments in .env
- **API URLs now work correctly** - Both admin and FILC APIs will use production URLs when ENVIRONMENT=production
- **Backward compatible** - Still works with cloud_sql_proxy for local development

## 🧪 Testing

Your admin page should now:
1. ✅ Connect to Cloud SQL properly in production
2. ✅ Use production API URLs when ENVIRONMENT=production  
3. ✅ Show proper configuration in logs
4. ✅ Display user data from the production database

Ready for deployment! 🚀 