"""Reusable KFP components for RAG operations."""

from datetime import datetime, timezone

from kfp import dsl

UTC = timezone.utc


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-cloud-aiplatform[all]>=1.60.0",
        "google-cloud-firestore==2.16.0",
    ],
)
def ingest_document_to_rag(
    gcs_uri: str,
    app_id: str,
    project_id: str,
    location: str,
    display_name: str,
) -> str:
    """Ingest a GCS document into the Vertex AI RAG Engine corpus for app_id."""
    import logging

    from google.cloud import firestore

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Get corpus_id from Firestore
    db = firestore.Client(project=project_id)
    doc = db.collection("configs").document(app_id).get()
    if not doc.exists:
        raise ValueError(f"No Firestore config found for app_id: {app_id}")

    config = doc.to_dict()
    corpus_id = config.get("rag_corpus_id", "")
    if not corpus_id:
        raise ValueError(
            f"rag_corpus_id not set in Firestore for {app_id}. "
            "Run scripts/setup_rag_corpus.py first."
        )

    # Use Vertex AI RAG Engine
    import vertexai
    from vertexai.preview import rag

    vertexai.init(project=project_id, location=location)

    logger.info(f"Ingesting {gcs_uri} into corpus {corpus_id}")

    rag.upload_file(
        corpus_name=corpus_id,
        path=gcs_uri,
        display_name=display_name,
        description=f"Auto-ingested from {gcs_uri}",
    )

    # Log ingestion to Firestore

    db.collection("ingestion_log").add(
        {
            "app_id": app_id,
            "gcs_uri": gcs_uri,
            "corpus_id": corpus_id,
            "status": "success",
            "timestamp": datetime.now(UTC),
        }
    )

    logger.info(f"Ingestion complete: {gcs_uri}")
    return corpus_id
