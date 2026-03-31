"""
KFP Pipeline: RAG Document Ingestion
Triggered by: GCS file upload (via Pub/Sub + Eventarc)
What it does: Reads a document from GCS and ingests it into the
              Vertex AI RAG Engine corpus for the given app_id.

Deploy with:
  python pipelines/rag_ingestion_pipeline.py --project YOUR_PROJECT --submit
"""

import argparse
import logging
import os
from datetime import timezone
UTC = timezone.utc

import google.cloud.aiplatform as aip
from kfp import dsl

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("PIPELINE_LOCATION", "us-central1")
PIPELINE_ROOT = os.getenv("PIPELINE_ROOT_GCS", "")


# ── KFP Components ────────────────────────────────────────────────────────────


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-firestore",
        "google-cloud-aiplatform",
        "vertexai",
    ],
)
def ingest_document_to_rag(
    gcs_uri: str,
    app_id: str,
    project_id: str,
    location: str,
    display_name: str,
) -> str:
    """
    Ingests a single document from GCS into the Vertex AI RAG Engine corpus.
    The corpus_id is read from Firestore configs/{app_id}.rag_corpus_id.
    Returns the corpus_id on success.
    """
    import logging

    import vertexai
    from google.cloud import firestore
    from vertexai.preview import rag

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Get corpus_id from Firestore
    db = firestore.Client(project=project_id)
    doc = db.collection("configs").document(app_id).get()
    if not doc.exists:
        raise ValueError(f"No config found for app_id: {app_id}")

    config = doc.to_dict()
    corpus_id = config.get("rag_corpus_id", "")
    if not corpus_id:
        raise ValueError(
            f"rag_corpus_id not set in Firestore for {app_id}. Run setup_rag_corpus.py first."
        )

    # Ingest document
    vertexai.init(project=project_id, location=location)

    logger.info(f"Ingesting {gcs_uri} into corpus {corpus_id}")

    rag.upload_file(
        corpus_name=corpus_id,
        path=gcs_uri,
        display_name=display_name,
        description=f"Ingested from {gcs_uri}",
    )

    logger.info(f"Successfully ingested {gcs_uri}")
    return corpus_id


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-firestore"],
)
def update_ingestion_log(
    app_id: str,
    gcs_uri: str,
    corpus_id: str,
    project_id: str,
    status: str = "success",
) -> None:
    """Log the ingestion event to Firestore for audit trail."""
    from datetime import datetime

    from google.cloud import firestore

    db = firestore.Client(project=project_id)
    db.collection("ingestion_log").add(
        {
            "app_id": app_id,
            "gcs_uri": gcs_uri,
            "corpus_id": corpus_id,
            "status": status,
            "timestamp": datetime.now(UTC),
        }
    )


# ── Pipeline definition ───────────────────────────────────────────────────────


@dsl.pipeline(
    name="rag-document-ingestion",
    description="Ingests a document from GCS into Vertex AI RAG Engine corpus",
)
def rag_ingestion_pipeline(
    gcs_uri: str,
    app_id: str = "rag_bot",
    project_id: str = PROJECT_ID,
    location: str = LOCATION,
    display_name: str = "uploaded_document",
):
    ingest_task = ingest_document_to_rag(
        gcs_uri=gcs_uri,
        app_id=app_id,
        project_id=project_id,
        location=location,
        display_name=display_name,
    )

    update_ingestion_log(
        app_id=app_id,
        gcs_uri=gcs_uri,
        corpus_id=ingest_task.output,
        project_id=project_id,
        status="success",
    ).after(ingest_task)


# ── CLI runner ────────────────────────────────────────────────────────────────


def compile_and_submit(project_id: str, gcs_uri: str, app_id: str):
    from kfp import compiler

    compiled_path = "/tmp/rag_ingestion_pipeline.json"
    compiler.Compiler().compile(rag_ingestion_pipeline, compiled_path)

    aip.init(project=project_id, location=LOCATION)

    job = aip.PipelineJob(
        display_name="rag-ingestion-run",
        template_path=compiled_path,
        pipeline_root=PIPELINE_ROOT,
        parameter_values={
            "gcs_uri": gcs_uri,
            "app_id": app_id,
            "project_id": project_id,
            "location": LOCATION,
        },
        enable_caching=False,
    )
    job.submit()
    print(f"Pipeline submitted. Job name: {job.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--gcs_uri", required=True, help="e.g. gs://bucket/file.pdf")
    parser.add_argument("--app_id", default="rag_bot")
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()

    if args.submit:
        compile_and_submit(args.project, args.gcs_uri, args.app_id)
    else:
        from kfp import compiler

        compiler.Compiler().compile(
            rag_ingestion_pipeline, "rag_ingestion_pipeline.json"
        )
        print("Compiled to rag_ingestion_pipeline.json")
