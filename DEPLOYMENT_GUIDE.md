# 🚀 FastInnovation Dynamic User App - Cloud Run Deployment Guide

## 📋 **Overview**

This guide provides step-by-step instructions for deploying the FastInnovation Dynamic User App to Google Cloud Run with Cloud SQL integration using the automated deployment script.

## ✅ **Prerequisites**

Before deploying, ensure you have:

1. **Google Cloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project fast-innovation-460415
   ```

2. **Required APIs enabled** in your Google Cloud project:
   - Cloud Run API
   - Cloud SQL Admin API  
   - Cloud Build API
   - IAM API

3. **Cloud SQL instance** already created:
   - Instance name: `fast-innovation-sandbox`
   - Database: `fastinnovation`
   - User: `postgres` with password

4. **Firebase project** configured with:
   - Authentication enabled
   - Service account credentials
   - Web app configured

## 🔧 **Environment Configuration**

The deployment script automatically configures the following environment variables:

### **Database Configuration**
- `ENVIRONMENT=production`
- `USE_CLOUD_SQL=true`
- `CLOUD_SQL_CONNECTION_NAME=fast-innovation-460415:us-central1:fast-innovation-sandbox`
- `CLOUD_SQL_DATABASE_NAME=fastinnovation`
- `CLOUD_SQL_USERNAME=postgres`
- `CLOUD_SQL_PASSWORD=fast_inn0_%`

### **Firebase Configuration**
- `FIREBASE_API_KEY`
- `FIREBASE_AUTH_DOMAIN`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_MESSAGING_SENDER_ID`
- `FIREBASE_APP_ID`
- `FIREBASE_MEASUREMENT_ID`
- `FIREBASE_SERVICE_ACCOUNT_JSON` (configured in script)

### **API Integration**
- `OPENAI_API_KEY` (configured in script)
- `FILC_API_KEY`
- `FI_ANALYTICS_API_KEY`
- `ADMIN_API_URL_PRODUCTION`
- `FILC_API_URL_PRODUCTION`

## 🚀 **Deployment Steps**

### **Step 1: Prepare Deployment**

1. Navigate to your project directory:
   ```bash
   cd /path/to/dynamic_user
   ```

2. Ensure the deployment script is executable:
   ```bash
   chmod +x deploy-to-cloud-run.sh
   ```

3. Verify the Firebase service account JSON is embedded in the script (already configured).

### **Step 2: Run Deployment**

Execute the deployment script:
```bash
./deploy-to-cloud-run.sh
```

The script will:
- Set the Google Cloud project
- Deploy the application to Cloud Run
- Configure all environment variables
- Set up Cloud SQL connection
- Grant necessary IAM permissions
- Display the service URL

### **Step 3: Verify Deployment**

1. **Check deployment status:**
   ```bash
   gcloud run services list --region=us-central1
   ```

2. **Test health endpoint:**
   ```bash
   curl https://dynamic-user-604277815223.us-central1.run.app/health
   ```

3. **Access the application:**
   Open: `https://dynamic-user-604277815223.us-central1.run.app`

## 🔒 **IAM Permissions**

The deployment script automatically grants the required permissions:

```bash
# Cloud SQL Client role for database access
gcloud projects add-iam-policy-binding fast-innovation-460415 \
  --member="serviceAccount:604277815223-compute@developer.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

## 📊 **Service Configuration**

The Cloud Run service is configured with:

- **Memory:** 2Gi
- **CPU:** 2 cores
- **Max Instances:** 10
- **Timeout:** 300 seconds
- **Port:** 8080
- **Access:** Unauthenticated (publicly accessible)
- **Cloud SQL:** Connected via Python Connector

## 🔧 **Deployment Script Details**

The `deploy-to-cloud-run.sh` script includes:

### **Configuration Variables**
```bash
PROJECT_ID="fast-innovation-460415"
REGION="us-central1"
SERVICE_NAME="dynamic-user"
CLOUD_SQL_INSTANCE="fast-innovation-sandbox"
CLOUD_SQL_CONNECTION_NAME="fast-innovation-460415:us-central1:fast-innovation-sandbox"
```

### **Key Features**
- Automated environment variable configuration
- Cloud SQL connection setup
- IAM permission management
- Service health verification
- Deployment status reporting

## 🛠 **Troubleshooting**

### **Common Issues**

1. **Permission Denied:**
   ```bash
   # Make script executable
   chmod +x deploy-to-cloud-run.sh
   ```

2. **Cloud SQL Connection Issues:**
   ```bash
   # Verify Cloud SQL instance is running
   gcloud sql instances describe fast-innovation-sandbox
   ```

3. **Firebase Authentication Issues:**
   - Verify Firebase service account JSON is correctly embedded
   - Check Firebase project configuration

4. **Container Failed to Start:**
   ```bash
   # Check service logs
   gcloud run services logs read dynamic-user --region=us-central1 --limit=20
   ```

### **Verification Commands**

```bash
# Check service status
gcloud run services describe dynamic-user --region=us-central1

# View environment variables
gcloud run services describe dynamic-user --region=us-central1 \
  --format="value(spec.template.spec.template.spec.containers[0].env[].name)"

# Check IAM permissions
gcloud projects get-iam-policy fast-innovation-460415 \
  --flatten="bindings[].members" \
  --filter="bindings.members:*compute@developer.gserviceaccount.com"
```

## 📈 **Performance Optimization**

The application includes several performance optimizations:

- **Async Database Operations:** Using asyncpg with Cloud SQL Python Connector
- **Connection Pooling:** Optimized database connection management
- **Parallel Processing:** Background operations for non-critical tasks
- **Health Monitoring:** Built-in health endpoint for monitoring

## 🔄 **Updates and Redeployment**

To update the application:

1. Make your code changes
2. Run the deployment script again:
   ```bash
   ./deploy-to-cloud-run.sh
   ```

The script will create a new revision and automatically route traffic to it.

## 📞 **Support**

For deployment issues:
1. Check the Cloud Build logs (URL provided during deployment)
2. Review Cloud Run service logs
3. Verify environment variables are set correctly
4. Ensure all required APIs are enabled

---

## 🎉 **Success Indicators**

After successful deployment, you should see:
- ✅ Health endpoint returns `{"status":"healthy"}`
- ✅ Service URL is accessible
- ✅ Environment shows "production"
- ✅ Cloud SQL shows "Enabled"
- ✅ No errors in service logs

**Service URL:** https://dynamic-user-604277815223.us-central1.run.app