#!/bin/bash
# Compile and upload KFP pipelines to GCS for Cloud Scheduler to use.
# Run after: terraform apply

PROJECT_ID=$1
BUCKET="${PROJECT_ID}-llmops-pipeline-artifacts"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: ./deploy_pipelines.sh YOUR_PROJECT_ID"
  exit 1
fi

# Move to project root (xyz folder parent)
cd "$(dirname "$0")/.."

# Install kfp if not present (although it should be in venv)
pip install kfp==2.7.0 -q

# Compile pipelines
echo "Compiling pipelines..."
python pipelines/master_pipeline.py --project $PROJECT_ID --compile
python pipelines/evaluation_pipeline.py --project $PROJECT_ID
python pipelines/rag_ingestion_pipeline.py --project $PROJECT_ID
python pipelines/experiment_pipeline.py --project $PROJECT_ID 2>/dev/null || true

# Upload to GCS
echo "Uploading pipelines to gs://$BUCKET/pipelines/..."
gsutil cp master_pipeline.json       gs://$BUCKET/pipelines/
gsutil cp evaluation_pipeline.json   gs://$BUCKET/pipelines/
gsutil cp rag_ingestion_pipeline.json gs://$BUCKET/pipelines/
gsutil cp experiment_pipeline.json   gs://$BUCKET/pipelines/ 2>/dev/null || true

echo "Pipelines deployed to gs://$BUCKET/pipelines/"
