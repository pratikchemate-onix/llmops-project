"""
Master Pipeline — The Central Controller for all LLMOps automation.

This is the ONLY pipeline that Cloud Scheduler, Eventarc, and manual
triggers need to call. The trigger_type parameter controls which
branches execute.

trigger_type values:
  "rag_ingestion"  → ingest a document into the RAG corpus
  "evaluation"     → run nightly evaluation + auto config update
  "experiment"     → run model A vs model B comparison + promote winner
  "full_run"       → run evaluation THEN experiment in sequence

Deploy:
  python pipelines/master_pipeline.py --project YOUR_PROJECT --compile
  python pipelines/master_pipeline.py --project YOUR_PROJECT --submit \
    --trigger_type evaluation --app_id default_llm

Architecture:
  master_pipeline
    ├── [rag_ingestion branch]  ingest_document_to_rag
    ├── [evaluation branch]     fetch_logs → judge → write_scores → update_config
    ├── [experiment branch]     load_test → run_a + run_b → compare → promote
    └── [full_run]              evaluation branch → experiment branch (sequential)
"""

import argparse
import os
from datetime import timezone
UTC = timezone.utc

import google.cloud.aiplatform as aip
from kfp import compiler, dsl

from pipelines.components.bigquery_components import (
    fetch_logs_to_gcs,
    write_scores_to_bigquery,
)
from pipelines.components.llm_components import (
    score_responses_with_judge,
    update_active_config,
)
from pipelines.components.rag_components import ingest_document_to_rag

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("PIPELINE_LOCATION", "us-central1")
PIPELINE_ROOT = os.getenv("PIPELINE_ROOT_GCS", "")


# ── Inline experiment components (self-contained) ─────────────────────────────


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-storage==2.18.0"],
)
def load_test_set_from_gcs(
    gcs_test_file: str,
    project_id: str,
    test_data_artifact: dsl.Output[dsl.Artifact],
) -> int:
    """Load test questions from GCS JSON file. Returns number of questions."""
    import json

    from google.cloud import storage

    path = gcs_test_file.replace("gs://", "")
    bucket_name, blob_name = path.split("/", 1)

    client = storage.Client(project=project_id)
    content = client.bucket(bucket_name).blob(blob_name).download_as_text()
    questions = json.loads(content)

    # Write to artifact URI
    out_bucket = test_data_artifact.uri.replace("gs://", "").split("/")[0]
    out_blob = "/".join(test_data_artifact.uri.replace("gs://", "").split("/")[1:])
    client.bucket(out_bucket).blob(out_blob).upload_from_string(
        content, content_type="application/json"
    )
    print(f"Loaded {len(questions)} test questions from {gcs_test_file}")
    return len(questions)


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-generativeai==0.8.3", "google-cloud-storage==2.18.0"],
)
def run_model_inference(
    test_data_artifact: dsl.Input[dsl.Artifact],
    results_artifact: dsl.Output[dsl.Artifact],
    model_name: str,
    app_id: str,
    project_id: str,
    google_api_key: str,
    system_prompt: str,
) -> None:
    """Run a model directly (not via serving API) on the test set.

    This calls the LLM API directly so we can test different models
    independently of what is currently active in the serving config.
    """
    import json
    import time

    import google.generativeai as genai
    from google.cloud import storage

    # Read test data
    in_uri = test_data_artifact.uri
    in_bucket = in_uri.replace("gs://", "").split("/")[0]
    in_blob = "/".join(in_uri.replace("gs://", "").split("/")[1:])
    gcs = storage.Client(project=project_id)
    questions = json.loads(gcs.bucket(in_bucket).blob(in_blob).download_as_text())

    genai.configure(api_key=google_api_key)

    results = []
    for item in questions[:30]:
        question = item.get("question", item.get("user_input", str(item)))
        try:
            model_obj = genai.GenerativeModel(
                model_name,
                system_instruction=system_prompt,
            )
            resp = model_obj.generate_content(question)
            results.append(
                {
                    "question": question,
                    "expected": item.get("expected", ""),
                    "model": model_name,
                    "response": resp.text,
                }
            )
            time.sleep(0.2)
        except Exception as e:
            results.append(
                {
                    "question": question,
                    "model": model_name,
                    "response": f"ERROR: {e}",
                }
            )

    # Write results to artifact
    out_uri = results_artifact.uri
    out_bucket = out_uri.replace("gs://", "").split("/")[0]
    out_blob = "/".join(out_uri.replace("gs://", "").split("/")[1:])
    gcs.bucket(out_bucket).blob(out_blob).upload_from_string(
        json.dumps(results), content_type="application/json"
    )
    print(f"Model {model_name}: ran {len(results)} inferences.")


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "google-generativeai==0.8.3",
        "google-cloud-storage==2.18.0",
        "google-cloud-bigquery==3.25.0",
        "google-cloud-firestore==2.16.0",
    ],
)
def compare_models_and_promote(
    results_a_artifact: dsl.Input[dsl.Artifact],
    results_b_artifact: dsl.Input[dsl.Artifact],
    model_a_name: str,
    model_b_name: str,
    app_id: str,
    experiment_id: str,
    project_id: str,
    google_api_key: str,
    promotion_margin: float,
) -> str:
    """Judge both model result sets, write to BigQuery, promote winner."""
    import json
    import time
    from datetime import datetime

    import google.generativeai as genai
    from google.cloud import bigquery, firestore, storage

    gcs = storage.Client(project=project_id)

    def read_artifact(artifact):
        uri = artifact.uri
        bucket = uri.replace("gs://", "").split("/")[0]
        blob = "/".join(uri.replace("gs://", "").split("/")[1:])
        return json.loads(gcs.bucket(bucket).blob(blob).download_as_text())

    results_a = read_artifact(results_a_artifact)
    results_b = read_artifact(results_b_artifact)

    genai.configure(api_key=google_api_key)
    judge = genai.GenerativeModel("gemini-2.0-pro-exp")

    scores_a, scores_b = [], []
    for ra, rb in zip(results_a, results_b, strict=False):
        try:
            prompt = f"""Compare two AI responses. Return ONLY JSON: {{"score_a": 1-5, "score_b": 1-5}}

Question: {ra["question"][:300]}
Response A ({model_a_name}): {ra["response"][:500]}
Response B ({model_b_name}): {rb["response"][:500]}"""
            resp = judge.generate_content(prompt)
            raw = resp.text.strip().strip("```json").strip("```").strip()
            d = json.loads(raw)
            scores_a.append(d.get("score_a", 3))
            scores_b.append(d.get("score_b", 3))
            time.sleep(0.3)
        except Exception as e:
            print(f"Comparison scoring error: {e}")
            scores_a.append(3)
            scores_b.append(3)

    avg_a = round(sum(scores_a) / len(scores_a), 2) if scores_a else 3.0
    avg_b = round(sum(scores_b) / len(scores_b), 2) if scores_b else 3.0
    margin = abs(avg_a - avg_b)
    winner = (
        model_a_name if avg_a > avg_b else (model_b_name if avg_b > avg_a else "tie")
    )

    now = datetime.now(UTC)

    # Write to BigQuery
    bq = bigquery.Client(project=project_id)
    bq.insert_rows_json(
        f"{project_id}.llmops.experiments",
        [
            {
                "timestamp": now.isoformat(),
                "experiment_id": experiment_id,
                "app_id": app_id,
                "model_a": model_a_name,
                "model_b": model_b_name,
                "avg_score_a": avg_a,
                "avg_score_b": avg_b,
                "winner": winner,
                "promoted": False,
                "sample_size": len(scores_a),
            }
        ],
    )

    # Promote winner if margin is significant
    promoted = False
    if winner != "tie" and margin >= promotion_margin:
        db = firestore.Client(project=project_id)
        db.collection("configs").document(app_id).update(
            {
                "active_model": winner,
                "updated_at": now,
            }
        )
        promoted = True
        print(f"Promoted model {winner} for {app_id} with margin {margin:.2f}")

    result = (
        f"Experiment {experiment_id} complete. "
        f"Winner: {winner} (A={avg_a}, B={avg_b}, margin={margin:.2f}). "
        f"Promoted: {promoted}."
    )
    print(result)
    return result


# ── Master Pipeline ───────────────────────────────────────────────────────────


@dsl.pipeline(
    name="llmops-master-pipeline",
    description=(
        "Central controller for all LLMOps automation. "
        "Controls RAG ingestion, evaluation, experiments, and config updates. "
        "trigger_type determines which branches run."
    ),
)
def master_pipeline(
    # --- Required for all runs ---
    trigger_type: str = "evaluation",  # rag_ingestion | evaluation | experiment | full_run
    app_id: str = "default_llm",
    project_id: str = PROJECT_ID,
    pipeline_root: str = PIPELINE_ROOT,
    # --- For rag_ingestion ---
    gcs_document_uri: str = "",
    document_display_name: str = "uploaded_document",
    rag_location: str = "us-central1",
    # --- For evaluation ---
    judge_model: str = "gemini-2.0-pro-exp",
    lookback_hours: int = 24,
    sample_size: int = 50,
    eval_run_id: str = "eval_auto",
    google_api_key: str = "",
    # --- For experiment ---
    model_a_name: str = "gemini-2.0-flash",
    model_b_name: str = "gemini-2.0-pro-exp",
    gcs_test_file: str = "",
    experiment_id: str = "exp_001",
    experiment_system_prompt: str = "You are a helpful assistant.",
    promotion_margin: float = 0.5,
):
    """Master pipeline with conditional branching based on trigger_type."""

    # ── Branch 1: RAG Ingestion ──────────────────────────────────────────────
    with dsl.If(trigger_type == "rag_ingestion", name="rag-ingestion-branch"):
        ingest_document_to_rag(
            gcs_uri=gcs_document_uri,
            app_id=app_id,
            project_id=project_id,
            location=rag_location,
            display_name=document_display_name,
        )

    # ── Branch 2: Evaluation ─────────────────────────────────────────────────
    with dsl.If(
        (trigger_type == "evaluation") or (trigger_type == "full_run"),
        name="evaluation-branch",
    ):
        fetch_task = fetch_logs_to_gcs(
            project_id=project_id,
            app_id=app_id,
            lookback_hours=lookback_hours,
            sample_size=sample_size,
        )

        score_task = score_responses_with_judge(
            logs_gcs_uri=fetch_task.outputs["output_gcs_uri"],
            judge_model=judge_model,
            google_api_key=google_api_key,
        ).after(fetch_task)

        write_task = write_scores_to_bigquery(
            scored_gcs_uri=score_task.outputs["scored_gcs_uri"],
            project_id=project_id,
            eval_run_id=eval_run_id,
            app_id=app_id,
        ).after(score_task)

        update_active_config(
            app_id=app_id,
            avg_score=write_task.output,
            project_id=project_id,
        ).after(write_task)

    # ── Branch 3: Experiment ─────────────────────────────────────────────────
    with dsl.If(
        (trigger_type == "experiment") or (trigger_type == "full_run"),
        name="experiment-branch",
    ):
        load_task = load_test_set_from_gcs(
            gcs_test_file=gcs_test_file,
            project_id=project_id,
        )

        # Run both models in parallel (after test set is loaded)
        run_a_task = run_model_inference(
            test_data_artifact=load_task.outputs["test_data_artifact"],
            model_name=model_a_name,
            app_id=app_id,
            project_id=project_id,
            google_api_key=google_api_key,
            system_prompt=experiment_system_prompt,
        ).after(load_task)

        run_b_task = run_model_inference(
            test_data_artifact=load_task.outputs["test_data_artifact"],
            model_name=model_b_name,
            app_id=app_id,
            project_id=project_id,
            google_api_key=google_api_key,
            system_prompt=experiment_system_prompt,
        ).after(load_task)

        compare_models_and_promote(
            results_a_artifact=run_a_task.outputs["results_artifact"],
            results_b_artifact=run_b_task.outputs["results_artifact"],
            model_a_name=model_a_name,
            model_b_name=model_b_name,
            app_id=app_id,
            experiment_id=experiment_id,
            project_id=project_id,
            google_api_key=google_api_key,
            promotion_margin=promotion_margin,
        ).after(run_a_task, run_b_task)


# ── CLI ───────────────────────────────────────────────────────────────────────


def compile_pipeline(output_path: str = "master_pipeline.json") -> None:
    compiler.Compiler().compile(master_pipeline, output_path)
    print(f"Master pipeline compiled to: {output_path}")


def submit_pipeline(
    project_id: str,
    trigger_type: str,
    app_id: str,
    extra_params: dict | None = None,
) -> None:
    compiled_path = "/tmp/master_pipeline.json"
    compile_pipeline(compiled_path)

    aip.init(project=project_id, location=LOCATION)

    params = {
        "trigger_type": trigger_type,
        "app_id": app_id,
        "project_id": project_id,
        "pipeline_root": PIPELINE_ROOT,
        "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
    }
    if extra_params:
        params.update(extra_params)

    job = aip.PipelineJob(
        display_name=f"master-{trigger_type}-{app_id}",
        template_path=compiled_path,
        pipeline_root=PIPELINE_ROOT,
        parameter_values=params,
        enable_caching=False,
    )
    job.submit(
        service_account=f"llmops-backend-sa@{project_id}.iam.gserviceaccount.com"
    )
    print(f"Master pipeline submitted. trigger_type={trigger_type}, app_id={app_id}")
    print("Track at: https://console.cloud.google.com/vertex-ai/pipelines")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master LLMOps pipeline CLI")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument(
        "--trigger_type",
        choices=["rag_ingestion", "evaluation", "experiment", "full_run"],
        default="evaluation",
    )
    parser.add_argument("--app_id", default="default_llm")
    parser.add_argument(
        "--compile", action="store_true", help="Compile only, do not submit"
    )
    parser.add_argument(
        "--submit", action="store_true", help="Compile and submit to Vertex AI"
    )
    parser.add_argument("--gcs_document_uri", default="")
    parser.add_argument("--gcs_test_file", default="")
    parser.add_argument("--model_a", default="gemini-2.0-flash")
    parser.add_argument("--model_b", default="gemini-2.0-pro-exp")
    parser.add_argument("--output", default="master_pipeline.json")
    args = parser.parse_args()

    if args.compile:
        compile_pipeline(args.output)
    elif args.submit:
        submit_pipeline(
            project_id=args.project,
            trigger_type=args.trigger_type,
            app_id=args.app_id,
            extra_params={
                "gcs_document_uri": args.gcs_document_uri,
                "gcs_test_file": args.gcs_test_file,
                "model_a_name": args.model_a,
                "model_b_name": args.model_b,
            },
        )
    else:
        parser.print_help()
