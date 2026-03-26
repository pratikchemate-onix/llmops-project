#!/bin/bash
# Builds and deploys the trigger service (which runs pipelines) to Cloud Run.

PROJECT_ID=$1
REGION=${2:-us-central1}

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./deploy_trigger_service.sh YOUR_PROJECT_ID [REGION]"
  exit 1
fi

SERVICE_NAME="llmops-trigger"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/llmops-repo/${SERVICE_NAME}"

# Move to project root (xyz folder parent)
cd "$(dirname "$0")/.."

echo "Building and pushing trigger service image..."
gcloud builds submit xyz/trigger_service/ --tag $IMAGE_URI --project $PROJECT_ID

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_URI \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --service-account "llmops-pipeline-runner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars "PIPELINE_LOCATION=${REGION}" \
  --set-env-vars "PIPELINE_ROOT_GCS=gs://${PROJECT_ID}-llmops-pipeline-artifacts" \
  --set-env-vars "MASTER_PIPELINE_URI=gs://${PROJECT_ID}-llmops-pipeline-artifacts/pipelines/master_pipeline.json" \
  --set-env-vars "PIPELINE_SA=llmops-pipeline-runner@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Trigger service deployed successfully to Cloud Run service: $SERVICE_NAME"
