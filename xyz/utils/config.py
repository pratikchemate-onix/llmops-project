"""Environment configuration models for application settings.

This module provides Pydantic models for type-safe environment variable validation
and configuration management. Ensures fail-fast behavior on startup if required
configuration is missing or invalid.
"""

import json
import os
import sys
from typing import Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from dotenv import load_dotenv

T = TypeVar('T', bound=BaseModel)

def initialize_environment(
    model_class: type[T],
    override_dotenv: bool = True,
    print_config: bool = True,
) -> T:
    """Initialize and validate environment configuration.

    Factory function that handles the common initialization pattern: load environment
    variables, validate with Pydantic model, handle errors, and optionally print
    configuration.

    Args:
        model_class: Pydantic model class to validate environment with.
        override_dotenv: Whether to override existing environment variables.
            Defaults to True for consistency and predictability.
        print_config: Whether to call print_config() method if it exists.
            Defaults to True.

    Returns:
        Validated environment configuration instance.

    Raises:
        SystemExit: If validation fails.

    Examples:
        >>> # Simple case (most common)
        >>> env = initialize_environment(ServerEnv)
        >>>
        >>> # Skip printing configuration
        >>> env = initialize_environment(ServerEnv, print_config=False)
    """
    load_dotenv(override=override_dotenv)

    # Load and validate environment configuration
    try:
        env = model_class.model_validate(os.environ)
    except ValidationError as e:
        print("\n❌ Environment validation failed:\n")
        print(e)
        sys.exit(1)

    # Print configuration for user verification if method exists
    if print_config and hasattr(env, "print_config"):
        env.print_config()

    return env


class ServerEnv(BaseModel):
    """Environment configuration for backend server.

    Provides configuration for both local development and Cloud Run deployment,
    with sensible defaults for local development.

    Attributes:
        google_cloud_project: GCP project ID for authentication and services.
        google_cloud_location: Region for Vertex AI and other services.
        bigquery_project: Project ID for BigQuery logging (defaults to google_cloud_project).
        firestore_project: Project ID for Firestore config (defaults to google_cloud_project).
        rag_location: Region for RAG Engine (defaults to google_cloud_location).
        gcs_bucket_docs: GCS bucket name for document storage.
        pipeline_root_gcs: GCS path for KFP pipeline artifacts.
        log_level: Logging verbosity level.
        host: Server host (127.0.0.1 for local, 0.0.0.0 for containers).
        port: Server port.
        allow_origins: JSON array string of allowed CORS origins.
    """

    google_cloud_project: str = Field(
        ...,
        alias="GOOGLE_CLOUD_PROJECT",
        description="GCP project ID for authentication and services",
    )

    google_cloud_location: str = Field(
        default="us-central1",
        alias="GOOGLE_CLOUD_LOCATION",
        description="Region for Vertex AI and other services",
    )

    bigquery_project: str | None = Field(
        default=None,
        alias="BIGQUERY_PROJECT",
        description="Project ID for BigQuery logging (defaults to GOOGLE_CLOUD_PROJECT)",
    )

    firestore_project: str | None = Field(
        default=None,
        alias="FIRESTORE_PROJECT",
        description="Project ID for Firestore config (defaults to GOOGLE_CLOUD_PROJECT)",
    )

    rag_location: str | None = Field(
        default=None,
        alias="RAG_LOCATION",
        description="Region for RAG Engine (defaults to GOOGLE_CLOUD_LOCATION)",
    )

    gcs_bucket_docs: str | None = Field(
        default=None,
        alias="GCS_BUCKET_DOCS",
        description="GCS bucket name for document storage",
    )

    pipeline_root_gcs: str | None = Field(
        default=None,
        alias="PIPELINE_ROOT_GCS",
        description="GCS path for KFP pipeline artifacts (e.g., gs://bucket/path)",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging verbosity level",
    )

    host: str = Field(
        default="127.0.0.1",
        alias="HOST",
        description=(
            "Network interface for uvicorn to bind. "
            "Use 127.0.0.1 (loopback) for local dev, 0.0.0.0 for containers."
        ),
    )

    port: int = Field(
        default=8000,
        alias="PORT",
        description="Server port",
    )

    allow_origins: str = Field(
        default='["http://localhost", "http://localhost:3000", "http://localhost:8000"]',
        alias="ALLOW_ORIGINS",
        description="JSON array string of allowed CORS origins",
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field names and aliases
        extra="ignore",  # Ignore extra env vars (system vars, etc.)
    )

    @field_validator("allow_origins")
    @classmethod
    def validate_allow_origins_format(cls, v: str) -> str:
        """Validate allow_origins is valid JSON array with at least one string."""
        try:
            origins = json.loads(v)
        except json.JSONDecodeError as e:
            msg = f"ALLOW_ORIGINS must be valid JSON: {e}"
            raise ValueError(msg) from e

        if not isinstance(origins, list):
            msg = "ALLOW_ORIGINS must be a JSON array"
            raise ValueError(msg)

        if not origins:
            msg = "ALLOW_ORIGINS must contain at least one origin"
            raise ValueError(msg)

        if not all(isinstance(o, str) for o in origins):
            msg = "ALLOW_ORIGINS must be an array of strings"
            raise ValueError(msg)

        if not all(o.strip() for o in origins):
            msg = "ALLOW_ORIGINS must be an array of non-empty strings"
            raise ValueError(msg)

        return v

    @property
    def bigquery_project_resolved(self) -> str:
        """Get BigQuery project with fallback to google_cloud_project."""
        return self.bigquery_project or self.google_cloud_project

    @property
    def firestore_project_resolved(self) -> str:
        """Get Firestore project with fallback to google_cloud_project."""
        return self.firestore_project or self.google_cloud_project

    @property
    def rag_location_resolved(self) -> str:
        """Get RAG location with fallback to google_cloud_location."""
        return self.rag_location or self.google_cloud_location

    @property
    def allow_origins_list(self) -> list[str]:
        """Parse allow_origins JSON string to list.

        Returns:
            List of allowed origin strings.
        """
        result = json.loads(self.allow_origins)
        # Should never fail due to field_validator, but satisfies type checker
        if not isinstance(result, list):  # pragma: no cover
            msg = "Invalid allow_origins format"
            raise TypeError(msg)
        return result

    def print_config(self) -> None:
        """Print server configuration for user verification."""
        print("\n\n✅ Environment variables loaded for server:\n")
        print(f"GOOGLE_CLOUD_PROJECT:  {self.google_cloud_project}")
        print(f"GOOGLE_CLOUD_LOCATION: {self.google_cloud_location}")
        print(f"BIGQUERY_PROJECT:      {self.bigquery_project_resolved}")
        print(f"FIRESTORE_PROJECT:     {self.firestore_project_resolved}")
        print(f"RAG_LOCATION:          {self.rag_location_resolved}")
        print(f"GCS_BUCKET_DOCS:       {self.gcs_bucket_docs}")
        print(f"PIPELINE_ROOT_GCS:     {self.pipeline_root_gcs}")
        print(f"LOG_LEVEL:             {self.log_level}")
        print(f"HOST:                  {self.host}")
        print(f"PORT:                  {self.port}")
        print(f"ALLOW_ORIGINS:         {self.allow_origins}\n\n")
