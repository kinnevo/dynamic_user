# Cloud Run CI/CD Deployment Guide

This guide explains how to set up automated CI/CD for your dynamic_user project using Google Cloud Build and Cloud Run.

## Prerequisites

1. Google Cloud Project: `fast-innovation-460415`
2. GitHub repository with your code
3. `gcloud` CLI installed and authenticated
4. Docker installed (for local testing)

## Overview

The CI/CD pipeline will:
- Trigger on every push to the `main` branch
- Build a Docker container
- Deploy to Cloud Run automatically
- Use Google Secret Manager for sensitive data

## Quick Setup (Recommended)

### Step 1: Make the setup script executable
```bash
chmod +x setup-cicd.sh
```

### Step 2: Update the configuration
Edit `setup-cicd.sh` and update these variables:
```bash
REPO_NAME="your-actual-repo-name"        # Your GitHub repository name
GITHUB_OWNER="your-github-username"      # Your GitHub username/organization
```

### Step 3: Run the setup script
```bash
./setup-cicd.sh
```

This script will:
- Enable required Google Cloud APIs
- Set up IAM permissions for Cloud Build
- Provide commands to create secrets
- Guide you through GitHub repository connection

## Manual Setup (Step by Step)

### Step 1: Enable Google Cloud APIs

```bash
gcloud services enable cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com
```

### Step 2: Grant Cloud Build Permissions

```bash
PROJECT_ID="fast-innovation-460415"
CLOUD_BUILD_SA=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")@cloudbuild.gserviceaccount.com

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CLOUD_BUILD_SA" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 3: Create Secrets in Secret Manager

Create the following secrets with your actual values:

```bash
# Database secrets
echo "your-actual-cloud-sql-password" | gcloud secrets create cloud-sql-password --data-file=-
echo "your-actual-postgres-password" | gcloud secrets create postgres-password --data-file=-

# API keys
echo "your-actual-openai-api-key" | gcloud secrets create openai-api-key --data-file=-
echo "your-actual-analytics-api-key" | gcloud secrets create analytics-api-key --data-file=-

# Application secrets
echo "your-actual-app-secret-key" | gcloud secrets create app-secret-key --data-file=-
echo "your-actual-storage-secret-key" | gcloud secrets create storage-secret-key --data-file=-

# Firebase service account (from your JSON file)
gcloud secrets create firebase-service-account --data-file=firebase-serviceaccount.json
```

### Step 4: Connect GitHub Repository

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Click **"Connect Repository"**
3. Select **"GitHub (Cloud Build GitHub App)"**
4. Authenticate with GitHub and select your repository
5. Create a trigger with these settings:
   - **Name**: `deploy-main-branch`
   - **Event**: `Push to a branch`
   - **Source**: `^main$` (regex for main branch)
   - **Configuration**: `Cloud Build configuration file (yaml)`
   - **Location**: `cloudbuild.yaml`

### Step 5: Test the Pipeline

Push a change to your main branch:

```bash
git add .
git commit -m "Setup CI/CD pipeline"
git push origin main
```

## Configuration Files Explained

### `cloudbuild.yaml`
Complete CI/CD configuration with secrets management. This is the production-ready version that:
- Builds and pushes Docker images
- Deploys to Cloud Run with all environment variables
- Uses Secret Manager for sensitive data

### `cloudbuild-simple.yaml`
Minimal configuration for testing without secrets. Use this for initial testing:
```bash
gcloud builds submit --config cloudbuild-simple.yaml .
```

### `launch.json` (Updated)
VS Code configuration for local development and debugging:
- Added Python debugging configuration
- Added missing environment variables (`PORT`, `STORAGE_SECRET`)
- Improved resource allocation

## Environment Variables

The deployment uses these environment variables:

**Public Environment Variables** (set directly):
- `ENVIRONMENT=production`
- `PORT=8080`
- `USE_CLOUD_SQL=true`
- Firebase configuration
- Database connection settings

**Secret Environment Variables** (from Secret Manager):
- `CLOUD_SQL_PASSWORD`
- `POSTGRES_PASSWORD`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `OPENAI_API_KEY`
- `SECRET_KEY`
- `STORAGE_SECRET`
- `ANALYTICS_API_KEY`

## Monitoring and Debugging

### View Build Logs
```bash
gcloud builds list
gcloud builds log [BUILD_ID]
```

### View Cloud Run Logs
```bash
gcloud run logs tail dynamic-user --region us-central1
```

### Cloud Console Links
- [Cloud Build History](https://console.cloud.google.com/cloud-build/builds)
- [Cloud Run Services](https://console.cloud.google.com/run)
- [Secret Manager](https://console.cloud.google.com/security/secret-manager)

## Troubleshooting

### Common Issues

1. **Build fails with permission errors**
   - Ensure Cloud Build service account has proper IAM roles
   - Check that APIs are enabled

2. **Secrets not found**
   - Verify secrets exist in Secret Manager
   - Check secret names match exactly in `cloudbuild.yaml`

3. **Cloud Run deployment fails**
   - Check memory/CPU limits
   - Verify port configuration
   - Review application logs

### Manual Deployment
If automated deployment fails, you can deploy manually:

```bash
# Build and push image
gcloud builds submit --tag gcr.io/fast-innovation-460415/dynamic-user .

# Deploy to Cloud Run
gcloud run deploy dynamic-user \
    --image gcr.io/fast-innovation-460415/dynamic-user \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

## Security Notes

1. **Never commit secrets to version control**
2. **Use Secret Manager for sensitive data**
3. **Regularly rotate API keys and passwords**
4. **Review IAM permissions periodically**
5. **Enable audit logging for production**

## Next Steps

1. Set up environment-specific deployments (staging/production)
2. Add automated testing to the pipeline
3. Configure custom domains
4. Set up monitoring and alerting
5. Implement blue-green deployments 