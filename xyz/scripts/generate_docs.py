"""
Auto-generates documentation for a coding session.
Run after each coding section to capture what was built.

Usage:
  python scripts/generate_docs.py --section \"Run A: BigQuery + Firestore\"
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
UTC = timezone.utc
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs" / "decisions"
API_DOCS_DIR = Path(__file__).parent.parent / "docs" / "api"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
API_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def get_git_diff_summary() -> str:
    """Get a list of files changed since last commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        return result.stdout.strip() or "No uncommitted changes."
    except Exception:
        return "Git not available."


def get_test_coverage_summary() -> str:
    """Run pytest with coverage and return summary."""
    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "--cov=app",
                "--cov-report=term-missing",
                "-q",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        lines = result.stdout.split("\n")
        # Return last 10 lines (summary)
        return "\n".join(lines[-10:])
    except Exception as e:
        return f"Could not run tests: {e}"


def export_openapi_schema() -> None:
    """Export FastAPI OpenAPI schema to docs/api/openapi.json."""
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app.main import app

        schema = app.openapi()
        out = API_DOCS_DIR / "openapi.json"
        out.write_text(json.dumps(schema, indent=2))
        print(f"API schema exported to {out}")
    except Exception as e:
        print(f"Could not export OpenAPI schema: {e}")


def generate_decision_doc(section: str, notes: str = "") -> Path:
    """Generate a decision document for this coding session."""
    now = datetime.now(UTC)
    slug = section.lower().replace(" ", "_").replace(":", "").replace("/", "_")[:50]
    filename = f"{now.strftime('%Y%m%d')}_{slug}.md"
    out = DOCS_DIR / filename

    diff_summary = get_git_diff_summary()
    test_summary = get_test_coverage_summary()

    content = f"""# {section}
Generated: {now.isoformat()}

## What Was Built
{notes or "See file changes below."}

## Files Changed
```
{diff_summary}
```

## Test Coverage
```
{test_summary}
```

## Next Step
See the next Run prompt in the llmops-prompts/ folder.
"""
    out.write_text(content)
    print(f"Decision doc written to: {out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--section", required=True, help="Section name, e.g. 'Run A: BigQuery'"
    )
    parser.add_argument(
        "--notes", default="", help="Optional notes about what was built"
    )
    args = parser.parse_args()

    export_openapi_schema()
    generate_decision_doc(args.section, args.notes)
    print("Documentation generated successfully.")
