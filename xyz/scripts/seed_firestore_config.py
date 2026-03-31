"""
Run this once to migrate config.json to Firestore.
Usage: python scripts/seed_firestore_config.py --project YOUR_PROJECT_ID
"""

import argparse
from datetime import datetime, timezone

UTC = timezone.utc

from google.cloud import firestore

CONFIGS = {
    "mock_app": {
        "pipeline": "llm",
        "active_model": "mock",
        "active_prompt_version": "v1",
        "evaluation_threshold": 3.0,
        "top_k": 3,
        "description": "Mock app for testing without API keys",
    },
    "default_llm": {
        "pipeline": "llm",
        "active_model": "gemini-2.5-flash",
        "active_prompt_version": "v1",
        "evaluation_threshold": 4.0,
        "description": "General purpose LLM assistant",
    },
    "rag_bot": {
        "pipeline": "rag",
        "active_model": "gemini-2.5-flash",
        "active_prompt_version": "v1",
        "evaluation_threshold": 4.0,
        "top_k": 3,
        "rag_corpus_id": "",  # Fill after creating RAG corpus
        "description": "Document Q&A with RAG retrieval",
    },
    "code_agent": {
        "pipeline": "agent",
        "active_model": "gemini-2.5-flash",
        "active_prompt_version": "v1",
        "evaluation_threshold": 4.0,
        "max_iterations": 5,
        "description": "Agentic coding assistant with tool use",
    },
}

PROMPTS = {
    "mock_app": {
        "v1": {
            "system_prompt": "You are a helpful assistant.",
            "prompt_template": "User asked: {user_input}",
            "status": "active",
        }
    },
    "default_llm": {
        "v1": {
            "system_prompt": "You are a helpful, accurate, and concise general assistant.",
            "prompt_template": "You are a helpful general assistant.\n\nUser: {user_input}\nAssistant:",
            "status": "active",
        }
    },
    "rag_bot": {
        "v1": {
            "system_prompt": "You are a document assistant. Answer ONLY from the provided context. If the context does not contain the answer, say: I could not find that in the provided documents.",
            "prompt_template": "Context from documents:\n{context}\n\nUser question: {user_input}\n\nAnswer based only on the context above:",
            "status": "active",
        }
    },
    "code_agent": {
        "v1": {
            "system_prompt": "You are an expert coding assistant. Think step by step. Use available tools when needed. Always explain your reasoning.",
            "prompt_template": "User request: {user_input}",
            "status": "active",
        }
    },
}


def seed(project_id: str) -> None:
    db = firestore.Client(project=project_id)
    now = datetime.now(UTC)

    for app_id, config in CONFIGS.items():
        doc_ref = db.collection("configs").document(app_id)
        doc_ref.set({**config, "updated_at": now})
        print(f"Config written for {app_id}")

        for version, prompt_data in PROMPTS.get(app_id, {}).items():
            prompt_ref = doc_ref.collection("prompts").document(version)
            prompt_ref.set(
                {**prompt_data, "version": version, "created_at": now, "score": None}
            )
            print(f"  Prompt {version} written for {app_id}")

    print("Firestore seeding complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    seed(args.project)
