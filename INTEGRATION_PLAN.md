# Agent-Foundation Integration Plan

## Executive Summary

This document outlines the integration of production-grade features from agent-foundation into the llmops codebase. The analysis shows that **observability is already integrated**, and the remaining work focuses on testing, CI/CD, deployment optimization, and code quality.

## Current State Analysis

### ✅ Already Integrated

1. **OpenTelemetry Observability** (`xyz/utils/observability.py`)
   - Cloud Trace integration via OTLP
   - Cloud Logging with trace correlation
   - Google Gen AI SDK instrumentation
   - Resource attributes with process-level tracking
   - **Status**: Identical to agent-foundation implementation

2. **BigQuery Logging** (`xyz/app/services/logging_service.py`)
   - Structured request logging
   - Fallback to stdout
   - Schema includes: timestamp, app_id, latency_ms, model, prompt_version, etc.
   - **Status**: Production-ready

3. **OpenTelemetry Dependencies**
   - All required packages in requirements.txt
   - **Status**: Up to date

### 🔧 Needs Integration

## 1. Testing Framework Enhancement

**Current State:**
- Basic pytest fixtures in `xyz/tests/conftest.py`
- Using `unittest.mock` for patching
- Tests exist but no coverage measurement
- No type hints in test fixtures

**Agent-Foundation Pattern:**
- `pytest-mock` with `MockerFixture` and `MockType`
- 100% test coverage requirement (excluding specific files)
- Comprehensive ADK mock objects
- Strict type hints even in tests
- Factory pattern for fixtures

**Integration Tasks:**
- [ ] Add `pytest-cov` and `pytest-mock` to dev dependencies
- [ ] Migrate from `unittest.mock` to `pytest-mock` patterns
- [ ] Add coverage configuration to `pyproject.toml`
- [ ] Create comprehensive mock objects for Google Cloud services
- [ ] Add type hints to test fixtures
- [ ] Set coverage target (start at 80%, aim for 100%)

**Files to Create/Modify:**
```
xyz/pyproject.toml          # Add [tool.coverage] and [tool.pytest]
xyz/tests/conftest.py       # Enhance with typed fixtures
xyz/requirements-dev.txt    # Or add dev dependencies section
```

---

## 2. CI/CD Workflow Modernization

**Current State:**
- Separate workflows: `backend-deploy.yml`, `frontend-deploy.yml`, `trigger-deploy.yml`
- Direct `gcloud run deploy` commands
- No Terraform plan on PRs
- Image tagged with `:latest` and `:sha`
- No image digest verification

**Agent-Foundation Pattern:**
- Modular workflow architecture (metadata → build → plan → apply)
- Terraform plan comments on PRs
- Deploy by immutable digest (not tag)
- Image promotion between environments
- Workload Identity Federation
- Production mode support (dev → stage → prod)

**Integration Tasks:**
- [ ] Create modular workflow structure:
  - `.github/workflows/metadata-extract.yml`
  - `.github/workflows/docker-build.yml`
  - `.github/workflows/terraform-plan-apply.yml`
  - `.github/workflows/code-quality.yml`
- [ ] Enhance `backend-deploy.yml` to use digest-based deployment
- [ ] Add Terraform plan comments on PRs
- [ ] Add code quality checks (ruff, mypy, pytest)
- [ ] Configure GitHub Environments (dev, stage, prod)

**Migration Strategy:**
1. Start with code-quality workflow (non-breaking)
2. Add docker-build workflow (parallel to existing)
3. Migrate terraform commands from shell to reusable workflow
4. Switch backend-deploy to use digest URIs
5. Deprecate old workflows

---

## 3. Dockerfile Optimization

**Current State:**
```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```
- Single-stage build
- pip-based dependency installation
- Root user
- ~500MB+ image size
- No layer caching optimization

**Agent-Foundation Pattern:**
```dockerfile
# Multi-stage with uv
FROM python:3.13-slim AS builder
# Install dependencies with cache mount (~80% speedup)
# Separate layers for deps vs code
FROM python:3.13-slim AS runtime
# Non-root user (app:app)
# ~200MB final image
```

**Integration Tasks:**
- [ ] Convert to multi-stage Dockerfile
- [ ] Migrate from pip to `uv` for dependency management
- [ ] Add cache mounts for build optimization
- [ ] Create non-root user `app:app`
- [ ] Upgrade to Python 3.13
- [ ] Separate dependency and code layers
- [ ] Add `.dockerignore` optimization

**Migration Strategy:**
1. Create `Dockerfile.optimized` alongside existing
2. Test locally with `docker build -f Dockerfile.optimized`
3. Compare image sizes: `docker images | grep llmops-backend`
4. Test Cloud Run deployment with optimized image
5. Replace `Dockerfile` once validated

---

## 4. Code Quality Infrastructure

**Current State:**
- No linting in CI
- No type checking
- No formatting enforcement
- No coverage requirements

**Agent-Foundation Pattern:**
- `ruff` for formatting and linting (88 char, strict rules)
- `mypy` for strict type checking
- 100% test coverage on production code
- Pre-commit validation

**Integration Tasks:**
- [ ] Add `pyproject.toml` with tool configurations:
  ```toml
  [tool.ruff]
  target-version = "py311"
  line-length = 88

  [tool.ruff.lint]
  select = ["E", "F", "I", "B", "C4", "UP", "N", "S", "SIM", "PTH"]

  [tool.mypy]
  python_version = "3.11"
  disallow_untyped_defs = true
  strict_equality = true

  [tool.coverage.report]
  fail_under = 80  # Start at 80%, increase gradually
  ```
- [ ] Add dev dependencies: `ruff`, `mypy`, `pytest-cov`
- [ ] Create `.github/workflows/code-quality.yml`
- [ ] Add type hints to existing code (start with new code)
- [ ] Run `ruff format` on codebase

**Migration Strategy:**
1. Add tools to dev environment (no breaking changes)
2. Run `ruff format` to auto-format existing code
3. Add code-quality workflow (make it non-blocking initially)
4. Fix critical mypy errors incrementally
5. Make workflow blocking once baseline is clean

---

## 5. Environment Configuration Validation

**Current State:**
- Environment variables read directly with `os.getenv()`
- No validation at startup
- No type safety
- No documentation of required vs optional vars

**Agent-Foundation Pattern:**
```python
from pydantic import BaseModel, Field

class ServerEnv(BaseModel):
    google_cloud_project: str = Field(..., alias="GOOGLE_CLOUD_PROJECT")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # ... with validation

env = initialize_environment(ServerEnv)
```

**Integration Tasks:**
- [ ] Create `xyz/utils/config.py` with Pydantic models
- [ ] Define `ServerEnv` with all required/optional fields
- [ ] Add field validators for complex types (JSON arrays, URIs)
- [ ] Add `initialize_environment()` helper
- [ ] Update `app/main.py` to use validated config
- [ ] Document all environment variables

**Migration Strategy:**
1. Create config.py without changing existing code
2. Add validation to one service at a time
3. Test with .env.example
4. Update main.py startup to use validated config
5. Remove direct `os.getenv()` calls

---

## 6. Deployment & Infrastructure Improvements

**Current State:**
- Terraform not integrated with CI/CD
- Manual terraform commands
- No state management visibility
- No health checks on Cloud Run

**Agent-Foundation Pattern:**
- Terraform in CI/CD with plan on PR, apply on merge
- Health check probes (startup, liveness)
- Cloud SQL Auth Proxy sidecar pattern
- Service account with least-privilege IAM

**Integration Tasks:**
- [ ] Add startup probe to Cloud Run service
- [ ] Configure health check endpoint (GET /health)
- [ ] Review IAM permissions (least-privilege)
- [ ] Add Terraform plan output to PR comments
- [ ] Document deployment process

---

## Implementation Priority

### Phase 1: Foundation (Week 1)
1. ✅ Observability (already done)
2. Add code quality tools (ruff, mypy, pytest-cov)
3. Create `pyproject.toml` configuration
4. Add code-quality.yml workflow

### Phase 2: Testing (Week 2)
1. Enhance test fixtures with pytest-mock
2. Add coverage measurement
3. Improve test coverage to 80%+
4. Add type hints to test files

### Phase 3: Build Optimization (Week 3)
1. Create optimized Dockerfile with uv
2. Test multi-stage build locally
3. Migrate to Python 3.13
4. Implement non-root user

### Phase 4: CI/CD Enhancement (Week 4)
1. Add modular workflow structure
2. Implement digest-based deployments
3. Add Terraform plan on PRs
4. Configure GitHub Environments

### Phase 5: Configuration & Deployment (Week 5)
1. Add Pydantic environment validation
2. Add health check endpoint
3. Configure Cloud Run probes
4. Document deployment process

---

## Success Metrics

- [ ] Test coverage ≥ 80% (aim for 100% on new code)
- [ ] All new code passes ruff + mypy strict checks
- [ ] Docker image size < 300MB (from ~500MB+)
- [ ] Build time < 2 minutes (from ~5 minutes)
- [ ] CI/CD runs Terraform plan on every PR
- [ ] Zero failed deployments due to environment misconfiguration

---

## Risk Mitigation

1. **Breaking Changes**: All enhancements are additive; existing code continues to work
2. **Rollback Plan**: Keep existing Dockerfile and workflows during migration
3. **Testing**: Test each change in dev environment before prod
4. **Documentation**: Update README.md with new patterns as they're added

---

## Files Requiring Attention

### Create New Files
```
xyz/pyproject.toml                           # Tool configurations
xyz/.dockerignore                            # Docker optimization
xyz/Dockerfile.optimized                     # Multi-stage build
xyz/utils/config.py                          # Pydantic validation
.github/workflows/code-quality.yml           # Linting/typing checks
.github/workflows/metadata-extract.yml       # Shared metadata
.github/workflows/docker-build.yml           # Reusable build
.github/workflows/terraform-plan-apply.yml   # Reusable Terraform
```

### Modify Existing Files
```
xyz/requirements.txt                    # Add uv_build
xyz/tests/conftest.py                   # Enhanced fixtures
xyz/app/main.py                         # Pydantic config
.github/workflows/backend-deploy.yml    # Digest deployment
```

---

## Next Steps

1. Review this plan with the team
2. Create GitHub issues for each phase
3. Set up project board for tracking
4. Start with Phase 1 (code quality foundation)
5. Iterate and adjust based on learnings

---

## References

- Agent-Foundation Repo: `agent-foundation-main (1)/agent-foundation-main/`
- Current Implementation: `xyz/`
- Phase 2 Architecture: `00_PHASE2_ARCHITECTURE.md`
