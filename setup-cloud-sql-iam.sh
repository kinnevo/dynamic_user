#!/bin/bash

# Cloud SQL IAM Setup Script
# This grants the necessary permissions for your Cloud Run service to access Cloud SQL

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔐 Setting up Cloud SQL IAM permissions...${NC}"

# Get project ID
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ No active gcloud project found. Please run: gcloud config set project YOUR_PROJECT_ID${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Project ID: ${PROJECT_ID}${NC}"

# Get the default Compute Engine service account
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
COMPUTE_SERVICE_ACCOUNT="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

echo -e "${YELLOW}🔧 Service Accounts:${NC}"
echo -e "   App Engine: ${SERVICE_ACCOUNT}"
echo -e "   Compute Engine: ${COMPUTE_SERVICE_ACCOUNT}"

# Grant Cloud SQL Client role to both service accounts
echo -e "${GREEN}🔑 Granting Cloud SQL Client role...${NC}"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudsql.client" \
    --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${COMPUTE_SERVICE_ACCOUNT}" \
    --role="roles/cloudsql.client" \
    --condition=None

echo -e "${GREEN}✅ IAM permissions configured successfully!${NC}"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo -e "   1. Deploy your app with: gcloud run deploy"
echo -e "   2. Make sure to include --add-cloudsql-instances flag"
echo -e "   3. Set ENVIRONMENT=production in your Cloud Run environment variables"
echo ""
echo -e "${GREEN}🚀 You're ready to deploy!${NC}" 