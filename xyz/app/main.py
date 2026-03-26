import logging
import os

from dotenv import load_dotenv

# Load environment variables from .env file immediately
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.routes import router  # noqa: E402
from utils.observability import setup_opentelemetry  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLMOps Pipeline", version="1.0.0")

# CORS
# Handled by ServerEnv now
# allowed_origins is loaded later
# We defer CORS setup until startup when env is loaded, 
# or we load a basic env here for module-level execution.
try:
    from utils.config import initialize_environment, ServerEnv
    _env = initialize_environment(ServerEnv, print_config=False)
    _origins = _env.allow_origins_list
except Exception:
    _origins = ["*"] # Fallback for build time

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_checks() -> None:
    from utils.config import initialize_environment, ServerEnv
    env = initialize_environment(ServerEnv, print_config=False)
    project_id = env.google_cloud_project
    
    # Check for Google Cloud Project ID for Vertex AI
    if not project_id:
        logger.warning(
            "GOOGLE_CLOUD_PROJECT not set. Only mock_app will work (Gemini/Vertex AI requires this)."
        )
    else:
        # Initialize OpenTelemetry observability
        try:
            setup_opentelemetry(
                project_id=project_id,
                agent_name="llmops-backend",
                log_level=env.log_level
            )
            logger.info("OpenTelemetry observability initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenTelemetry (likely permissions): {e}")
            pass


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "message": "LLMOps Pipeline is running"}


app.include_router(router)
