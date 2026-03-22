# Backend Architecture & Codebase Documentation

## 1. Project Overview

This project implements a modular **LLMOps (Large Language Model Operations) Pipeline** backend using **FastAPI** and **Python**. It is designed to be a foundational layer for building intelligent applications that require dynamic routing, task detection, and multiple execution strategies (Standard LLM, RAG, and Agents).

**Key Goals:**
*   **Modularity:** Easy to swap components (models, vector stores, pipelines).
*   **Dynamic Orchestration:** Automatically determines if a request needs external data (RAG) or multi-step reasoning (Agent).
*   **Configurability:** Behavior is driven by a central JSON configuration, allowing different "apps" to run on the same backend.

---

## 2. Architecture Diagram

The system follows a linear request processing flow with a branching decision logic at the Orchestrator level.

```mermaid
graph TD
    User[User Request] --> API[FastAPI /invoke Endpoint]
    API --> Config[Config Loader]
    API --> Detector[Task Detector (LLM)]
    
    Config --> Orch[Orchestrator]
    Detector --> Orch
    
    Orch -->|needs_agent=True| Agent[Agent Pipeline]
    Orch -->|needs_rag=True| RAG[RAG Pipeline]
    Orch -->|Default| LLM[Simple LLM Pipeline]
    
    Agent --> Tools[Tool Registry]
    RAG --> Vector[Vector Store]
    
    Agent --> Provider[LLM Provider]
    RAG --> Provider
    LLM --> Provider
    
    Provider --> Model[External Model (Gemini/Claude)]
    
    Agent & RAG & LLM --> Response
    Response --> Logger[Logging Service]
    Logger --> API
    API --> User
```

---

## 3. Core Components & File Analysis

### 3.1. Entry Point & API Layer
*   **`app/main.py`**: The entry point of the application. It initializes the `FastAPI` app, sets up CORS middleware (to allow frontend communication), and includes the main router.
*   **`app/routes.py`**: Defines the API endpoints.
    *   `POST /invoke`: The primary endpoint. It receives an `app_id` and `user_input`. It coordinates the entire lifecycle: loading config, running detection, invoking the orchestrator, executing the pipeline, and logging the result.

### 3.2. Configuration Layer
*   **`config/config.json`**: A central registry of "applications". Each key (e.g., `rag_bot`, `code_agent`) defines a profile with specific settings:
    *   `pipeline`: The base pipeline type (`llm`, `rag`, `agent`).
    *   `model`: The model to use (e.g., `gemini`, `claude`).
    *   `prompt_template`: Custom instructions for that app.
    *   `system_prompt`: Instructions for agents.
*   **`utils/config_loader.py`**: Utility to read and parse `config.json`.

### 3.3. Intelligence Layer (Task Detection)
*   **`app/services/task_detector.py`**: A specialized component that analyzes the user's intent *before* any action is taken.
    *   It asks an LLM (fast model like Gemini Flash) to classify the input into JSON: `{"needs_rag": bool, "needs_agent": bool}`.
    *   **Logic:**
        *   `needs_rag`: True if the user asks for specific files or internal context.
        *   `needs_agent`: True if the user asks for multi-step actions or coding tasks.

### 3.4. Orchestration Layer
*   **`app/orchestrator/router.py`**: The "brain" of the routing logic. It takes the configuration and the task detection result to decide *which* pipeline object to instantiate.
    *   **Priority Logic:**
        1.  **Agent Pipeline:** Highest priority (if `needs_agent` is True).
        2.  **RAG Pipeline:** Second priority (if `needs_rag` is True).
        3.  **LLM Pipeline:** Default fallback.

### 3.5. Execution Pipelines
Located in `app/pipelines/`, these classes implement the specific logic for each strategy.

*   **`llm_pipeline.py` (Simple)**
    *   **Goal:** Direct question-answering.
    *   **Flow:** Formatting the prompt -> Calling LLM -> Returning text.    
*   **`rag_pipeline.py` (Retrieval Augmented Generation)**
    *   **Goal:** Answering questions based on private documents.
    *   **Flow:** 
        1.  **Retrieve:** Search `VectorStore` for top-k relevant chunks.
        2.  **Inject:** Add these chunks into the `context` variable in the prompt.
        3.  **Generate:** Ask the LLM to answer using only that context.

*   **`agent_pipeline.py` (ReAct Agent)**
    *   **Goal:** Complex problem solving using tools.
    *   **Flow:** Implements a loop (Reasoning + Acting).
        1.  **Thought:** The LLM decides what to do next.
        2.  **Action:** The LLM requests to call a specific tool (e.g., "search_web").
        3.  **Observation:** The code executes the tool and feeds the result back to the LLM.
        4.  **Repeat:** Until the LLM produces a "Final Answer".

### 3.6. Service Abstractions
*   **`app/services/llm_provider.py`**: A factory pattern to unify different LLM APIs (Gemini, OpenAI, Claude) under a single `generate()` method. This prevents vendor lock-in.
*   **`app/services/vector_store.py`**: Abstract interface for vector databases (like ChromaDB or Pinecone).
*   **`app/services/logging_service.py`**: Handles structured logging (latency, tokens, pipeline used) for observability.

---

## 4. How to Read the Code (Mental Model)

When you look at the code, follow the **Data Flow**:

1.  **Start at `routes.py`**: See how the `InvokeRequest` comes in.
2.  **Follow the variables**: 
    *   `config` determines *static* behavior (what model to use).
    *   `detection_result` determines *dynamic* behavior (what pipeline to use).
3.  **Dive into `execute()`**: Every pipeline class has an `execute(user_input)` method. This is where the actual work happens.

## 5. Setup & Usage

### Prerequisites
*   Python 3.10+
*   Virtual environment (recommended)

### Installation
```bash
cd xyz
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Server
```bash
uvicorn app.main:app --reload
```
The server will start at `http://127.0.0.1:8000`.

### Testing
You can test it using `curl` or Postman:

```bash
curl -X POST "http://127.0.0.1:8000/invoke" \
     -H "Content-Type: application/json" \
     -d '{"app_id": "rag_bot", "user_input": "What is in the report?"}'
```

```