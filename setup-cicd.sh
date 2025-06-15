#!/bin/bash

# Cloud Run CI/CD Setup Script
# This script helps you set up CI/CD for your dynamic_user project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project configuration
PROJECT_ID="fast-innovation-460415"
REGION="us-central1"
SERVICE_NAME="dynamic-user"
REPO_NAME="dynamic_user"  
GITHUB_OWNER="Rico-Vari"  # Replace with your GitHub username

echo -e "${BLUE}Setting up CI/CD for Cloud Run...${NC}"

# 1. Enable required APIs
echo -e "${YELLOW}1. Enabling required Google Cloud APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com \
    sourcerepo.googleapis.com \
    --project=$PROJECT_ID

# 2. Grant Cloud Build permissions
echo -e "${YELLOW}2. Setting up Cloud Build service account permissions...${NC}"
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

# 3. Create secrets in Secret Manager
echo -e "${YELLOW}3. Creating secrets in Secret Manager...${NC}"
echo -e "${RED}You need to manually create these secrets with your actual values:${NC}"

cat << EOF

# Create secrets with these commands (replace with your actual values):

echo "your-cloud-sql-password" | gcloud secrets create cloud-sql-password --data-file=- --project=$PROJECT_ID
echo "your-postgres-password" | gcloud secrets create postgres-password --data-file=- --project=$PROJECT_ID
echo "your-openai-api-key" | gcloud secrets create openai-api-key --data-file=- --project=$PROJECT_ID
echo "your-app-secret-key" | gcloud secrets create app-secret-key --data-file=- --project=$PROJECT_ID
echo "your-storage-secret-key" | gcloud secrets create storage-secret-key --data-file=- --project=$PROJECT_ID
echo "your-analytics-api-key" | gcloud secrets create analytics-api-key --data-file=- --project=$PROJECT_ID

# For Firebase service account (create from the JSON file):
gcloud secrets create firebase-service-account --data-file=firebase-serviceaccount.json --project=$PROJECT_ID

EOF

# 4. Connect GitHub repository
echo -e "${YELLOW}4. Connecting GitHub repository...${NC}"
echo -e "${BLUE}Please follow these steps to connect your GitHub repository:${NC}"

cat << EOF

1. Go to Cloud Build in Google Cloud Console:
   https://console.cloud.google.com/cloud-build/triggers?project=$PROJECT_ID

2. Click "Connect Repository"

3. Select "GitHub (Cloud Build GitHub App)"

4. Authenticate and select your repository: $GITHUB_OWNER/$REPO_NAME

5. Create a trigger with these settings:
   - Name: deploy-main-branch
   - Event: Push to a branch
   - Source: ^main$
   - Configuration: Cloud Build configuration file (yaml or json)
   - Cloud Build configuration file location: cloudbuild.yaml

EOF

# 5. Initial deployment (manual)
echo -e "${YELLOW}5. Performing initial deployment...${NC}"
read -p "Do you want to perform the initial deployment now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Building and deploying...${NC}"
    gcloud builds submit --config cloudbuild.yaml --project=$PROJECT_ID .
else
    echo -e "${YELLOW}Skipping initial deployment. You can deploy later with:${NC}"
    echo "gcloud builds submit --config cloudbuild.yaml --project=$PROJECT_ID ."
fi

echo -e "${GREEN}✅ CI/CD setup complete!${NC}"

cat << EOF

${GREEN}Next steps:${NC}
1. Create the secrets in Secret Manager with your actual values
2. Connect your GitHub repository in Cloud Build console
3. Push changes to the main branch to trigger automatic deployments

${BLUE}Your Cloud Run service will be available at:${NC}
https://$SERVICE_NAME-[hash]-$REGION.a.run.app

${BLUE}Monitor deployments at:${NC}
https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID

EOF 