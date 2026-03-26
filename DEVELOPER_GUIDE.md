# Developer Guide - LLMOps Backend

Quick reference for development workflows after agent-foundation integration.

## 🚀 Quick Start

### Setup Development Environment

```bash
cd xyz

# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Copy environment file
cp .env.example .env
# Edit .env and set your GOOGLE_CLOUD_PROJECT
```

### Run Locally

```bash
# Standard way
uvicorn app.main:app --reload

# With debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload

# Backend runs at http://localhost:8000
```

---

## ✅ Code Quality Workflow

**Run these before every commit:**

```bash
# 1. Format code (auto-fixes)
ruff format .

# 2. Lint code (auto-fixes where possible)
ruff check .

# 3. Type check
mypy app utils pipelines --config-file pyproject.toml

# 4. Run tests with coverage
pytest --cov=app --cov=utils --cov=pipelines \
       --cov-report=term-missing \
       --cov-report=html:htmlcov \
       --cov-fail-under=80

# 5. View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**One-liner for pre-commit:**
```bash
ruff format . && ruff check . && mypy app utils pipelines && pytest --cov --cov-fail-under=80
```

---

## 🐳 Docker Workflows

### Standard Dockerfile (Current)
```bash
docker build -t llmops-backend:standard .
docker run -p 8080:8080 --env-file .env llmops-backend:standard
```

### Optimized Dockerfile (Recommended)
```bash
# Build optimized image (~200MB vs ~500MB+)
docker build -f Dockerfile.optimized -t llmops-backend:optimized .

# Run with health check
docker run -p 8080:8080 --env-file .env llmops-backend:optimized

# Check image size
docker images | grep llmops-backend
```

### Docker Compose (if available)
```bash
docker compose up --build
```

---

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/unit/test_llm_provider.py
```

### Run with Verbose Output
```bash
pytest -v
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=term-missing
```

### Run Async Tests Only
```bash
pytest -k async
```

### Run and Stop on First Failure
```bash
pytest -x
```

---

## 🔍 Type Checking

### Check All Code
```bash
mypy app utils pipelines
```

### Check Specific Module
```bash
mypy app/services/llm_provider.py
```

### Show Error Context
```bash
mypy --show-error-context app
```

---

## 🎨 Formatting & Linting

### Auto-Format All Code
```bash
ruff format .
```

### Check Format (No Changes)
```bash
ruff format --check .
```

### Lint and Auto-Fix
```bash
ruff check --fix .
```

### Lint Without Fixes
```bash
ruff check .
```

### See All Violations
```bash
ruff check --select ALL .
```

---

## 📦 Dependency Management

### Add Runtime Dependency
```bash
pip install package-name
pip freeze | grep package-name >> requirements.txt
```

### Add Dev Dependency
```bash
pip install package-name
pip freeze | grep package-name >> requirements-dev.txt
```

### Update All Dependencies
```bash
pip install --upgrade -r requirements.txt -r requirements-dev.txt
pip freeze > requirements-all.txt  # Review changes
```

---

## 🔧 Configuration

### Environment Variables (Required)
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
```

### Environment Variables (Optional with Defaults)
```bash
GOOGLE_CLOUD_LOCATION=us-central1  # Default
BIGQUERY_PROJECT=$GOOGLE_CLOUD_PROJECT  # Auto-resolves
FIRESTORE_PROJECT=$GOOGLE_CLOUD_PROJECT  # Auto-resolves
RAG_LOCATION=$GOOGLE_CLOUD_LOCATION  # Auto-resolves
LOG_LEVEL=INFO  # Default
HOST=127.0.0.1  # Default (use 0.0.0.0 in containers)
PORT=8000  # Default
```

### Using Validated Configuration (Future)
```python
from utils.config import initialize_environment, ServerEnv

# This will fail-fast if required vars are missing
env = initialize_environment(ServerEnv)

# Now you have type-safe, validated config
project_id = env.google_cloud_project  # str, guaranteed
log_level = env.log_level  # Literal["DEBUG" | "INFO" | ...]
```

---

## 📊 Observability

### View Logs Locally
```bash
# Logs go to stdout by default
tail -f nohup.out  # If running in background
```

### View Logs in GCP (Deployed)
```bash
gcloud logging read "resource.type=cloud_run_revision" --limit 50
```

### View Traces in GCP
```bash
# Navigate to Cloud Console > Trace
# Filter by service: llmops-backend
```

### View BigQuery Logs
```sql
SELECT * FROM `your-project.llmops.requests`
ORDER BY timestamp DESC
LIMIT 100;
```

---

## 🚢 Deployment

### Deploy to Cloud Run (via CI/CD)
```bash
# Automatic on merge to main
git push origin main
```

### Manual Deploy
```bash
gcloud run deploy llmops-backend \
  --image us-central1-docker.pkg.dev/PROJECT/llmops-repo/llmops-backend:latest \
  --region us-central1 \
  --platform managed
```

### View Deployment
```bash
gcloud run services describe llmops-backend \
  --region us-central1 \
  --format="value(status.url)"
```

---

## 🐛 Troubleshooting

### Import Errors
```bash
# Make sure you're in the xyz directory
cd xyz
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python -c "import app; print('Success!')"
```

### Type Checking Errors
```bash
# See detailed error
mypy --show-traceback app/services/llm_provider.py
```

### Test Failures
```bash
# Run with verbose output
pytest -vv --tb=short

# Run with print statements visible
pytest -s
```

### Docker Build Failures
```bash
# Build with no cache
docker build --no-cache -f Dockerfile.optimized -t llmops-backend .

# Check layer sizes
docker history llmops-backend
```

### Coverage Below 80%
```bash
# See what's missing
pytest --cov --cov-report=term-missing

# Focus on specific module
pytest --cov=app/services tests/unit/test_llm_provider.py --cov-report=term-missing
```

---

## 📝 Best Practices

### Code Style
- ✅ Use type hints everywhere
- ✅ Keep functions small and focused
- ✅ Use Pydantic models for validation
- ✅ Prefer pathlib over os.path
- ✅ Use async/await for I/O operations

### Testing
- ✅ Aim for 80%+ coverage
- ✅ Test edge cases and error paths
- ✅ Use fixtures for setup
- ✅ Mock external dependencies
- ✅ Write descriptive test names

### Git Workflow
- ✅ Create feature branches
- ✅ Run code quality checks before commit
- ✅ Write clear commit messages
- ✅ Keep PRs focused and small
- ✅ Wait for CI checks before merging

---

## 🔗 Related Documentation

- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) - What was integrated
- [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) - Full integration roadmap
- [00_PHASE2_ARCHITECTURE.md](00_PHASE2_ARCHITECTURE.md) - System architecture
- [xyz/pyproject.toml](xyz/pyproject.toml) - Tool configurations

---

## 🆘 Getting Help

1. Check error messages carefully
2. Review logs with DEBUG level
3. Check relevant test files for examples
4. Review agent-foundation patterns in `agent-foundation-main (1)/`
5. Ask the team!
