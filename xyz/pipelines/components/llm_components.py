"""Reusable KFP components for LLM operations (judge scoring, model calls)."""

from datetime import datetime, timezone

from kfp import dsl

UTC = timezone.utc


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-generativeai==0.8.3", "google-cloud-storage==2.18.0"],
)
def score_responses_with_judge(
    logs_gcs_uri: dsl.Input[dsl.Artifact],
    scored_gcs_uri: dsl.Output[dsl.Artifact],
    judge_model: str,
    google_api_key: str,
) -> None:
    """LLM-as-judge: score each response. Read from GCS, write scored JSON to GCS."""
    import json
    import time

    import google.generativeai as genai
    from google.cloud import storage

    # Read logs from GCS
    gcs_in = logs_gcs_uri.uri
    bucket_in = gcs_in.replace("gs://", "").split("/")[0]
    blob_in = "/".join(gcs_in.replace("gs://", "").split("/")[1:])
    gcs_client = storage.Client()
    logs = json.loads(gcs_client.bucket(bucket_in).blob(blob_in).download_as_text())

    if not logs:
        # Write empty result
        gcs_out = scored_gcs_uri.uri
        bucket_out = gcs_out.replace("gs://", "").split("/")[0]
        blob_out = "/".join(gcs_out.replace("gs://", "").split("/")[1:])
        gcs_client.bucket(bucket_out).blob(blob_out).upload_from_string(
            json.dumps([]), content_type="application/json"
        )
        return

    genai.configure(api_key=google_api_key)
    model = genai.GenerativeModel(judge_model)

    JUDGE_PROMPT = """You are an expert AI quality evaluator. Evaluate this response.
Return ONLY valid JSON, nothing else. No preamble, no markdown fences.

User Question: {user_input}
AI Response: {output}

Score each from 1 (worst) to 5 (best):
- correctness: Is the response factually accurate?
- relevance: Does it directly address what the user asked?
- completeness: Is the answer complete?

Return exactly: {{"correctness": N, "relevance": N, "completeness": N, "explanation": "..."}}"""

    scored = []
    for row in logs:
        try:
            prompt = JUDGE_PROMPT.format(
                user_input=row.get("user_input", "")[:500],
                output=row.get("output", "")[:1000],
            )
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            # Strip any accidental markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            scores = json.loads(raw.strip())
            avg = round(
                (
                    scores.get("correctness", 3)
                    + scores.get("relevance", 3)
                    + scores.get("completeness", 3)
                )
                / 3,
                2,
            )
            scored.append(
                {
                    **row,
                    "correctness_score": scores.get("correctness", 3),
                    "relevance_score": scores.get("relevance", 3),
                    "completeness_score": scores.get("completeness", 3),
                    "avg_score": avg,
                    "judge_model": judge_model,
                    "judge_explanation": scores.get("explanation", "")[:500],
                }
            )
            time.sleep(0.3)
        except Exception as e:
            print(f"Scoring failed for row: {e}")
            scored.append(
                {
                    **row,
                    "avg_score": 3.0,
                    "judge_model": judge_model,
                    "correctness_score": 3,
                    "relevance_score": 3,
                    "completeness_score": 3,
                    "judge_explanation": f"parse_error: {e}",
                }
            )

    # Write scored results to GCS
    gcs_out = scored_gcs_uri.uri
    bucket_out = gcs_out.replace("gs://", "").split("/")[0]
    blob_out = "/".join(gcs_out.replace("gs://", "").split("/")[1:])
    gcs_client.bucket(bucket_out).blob(blob_out).upload_from_string(
        json.dumps(scored), content_type="application/json"
    )
    print(f"Scored {len(scored)} responses. Written to {gcs_out}")


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["google-cloud-firestore==2.16.0"],
)
def update_active_config(
    app_id: str,
    avg_score: float,
    project_id: str,
) -> str:
    """Promote best candidate prompt if avg_score < threshold. Returns action taken."""

    from google.cloud import firestore

    db = firestore.Client(project=project_id)
    config_ref = db.collection("configs").document(app_id)
    config = config_ref.get().to_dict() or {}

    threshold = float(config.get("evaluation_threshold", 4.0))
    current_version = config.get("active_prompt_version", "v1")

    if avg_score >= threshold:
        msg = f"Score {avg_score:.2f} >= threshold {threshold}. No change needed."
        print(msg)
        return msg

    print(
        f"Score {avg_score:.2f} < threshold {threshold}. Searching for better prompt..."
    )

    candidates = (
        config_ref.collection("prompts").where("status", "==", "candidate").stream()
    )

    best_version = None
    best_score = avg_score

    for p in candidates:
        pd = p.to_dict()
        candidate_score = float(pd.get("score", 0))
        if candidate_score > best_score:
            best_score = candidate_score
            best_version = p.id

    if best_version:
        now = datetime.now(UTC)
        config_ref.update({"active_prompt_version": best_version, "updated_at": now})
        config_ref.collection("prompts").document(current_version).update(
            {"status": "retired"}
        )
        config_ref.collection("prompts").document(best_version).update(
            {"status": "active"}
        )
        msg = f"Promoted prompt {best_version} (score {best_score:.2f}). Retired {current_version}."
        print(msg)
        return msg

    msg = f"No candidate found with score > {avg_score:.2f}. Manual review needed for {app_id}."
    print(msg)
    return msg
