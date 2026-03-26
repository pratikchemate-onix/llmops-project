#!/bin/bash
# Builds and deploys the backend service to Cloud Run.

PROJECT_ID=$1
REGION=${2:-us-central1}
RAG_LOCATION=${3:-us-central1}

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./deploy_backend.sh YOUR_PROJECT_ID [REGION] [RAG_LOCATION]"
  exit 1
fi

SERVICE_NAME="llmops-backend"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/llmops-repo/${SERVICE_NAME}"

# Move to project root (xyz folder parent)
cd "$(dirname "$0")/.."

echo "Building and pushing backend image..."
gcloud builds submit . --tag $IMAGE_URI --project $PROJECT_ID

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_URI \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --service-account "llmops-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "BIGQUERY_PROJECT=${PROJECT_ID}" \
  --set-env-vars "FIRESTORE_PROJECT=${PROJECT_ID}" \
  --set-env-vars "RAG_LOCATION=${RAG_LOCATION}" \
  --set-env-vars "PIPELINE_ROOT_GCS=gs://${PROJECT_ID}-llmops-pipeline-artifacts" \
  --set-env-vars "GCS_BUCKET_DOCS=${PROJECT_ID}-llmops-docs"

echo "Backend deployed successfully to Cloud Run service: $SERVICE_NAME"
