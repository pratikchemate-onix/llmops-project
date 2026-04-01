"""
Agent Pipeline — uses Google ADK to run a ReAct agent with tools.
ADK manages the think → act → observe loop automatically.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any

from app.pipelines.base import BasePipeline
from app.services import llm_provider

logger = logging.getLogger(__name__)


# ── Tool definitions ──────────────────────────────────────────────────────────


def bigquery_query(sql_query: str) -> str:
    """Execute a read-only SQL query against BigQuery and return results as text.

    Args:
        sql_query: A SELECT SQL statement. Only SELECT is allowed.

    Returns:
        Query results as a formatted string, max 20 rows.
    """
    # Validate SQL query for safety
    if not _is_safe_select_query(sql_query):
        return "Error: Only safe SELECT queries are allowed. Query contains forbidden keywords or syntax."

    project = os.getenv("BIGQUERY_PROJECT")
    if not project:
        return "BigQuery not configured. BIGQUERY_PROJECT env var not set."

    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=project)
        # Use dry_run to validate query before execution
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        client.query(sql_query, job_config=job_config)  # Validation pass

        # Execute the actual query
        query_job = client.query(sql_query)
        rows = list(query_job.result())

        if not rows:
            return "Query returned no results."

        # Format as text table (max 20 rows)
        headers = list(rows[0].keys())
        lines = [" | ".join(headers)]
        lines.append("-" * len(lines[0]))
        for row in rows[:20]:
            lines.append(" | ".join(str(row[h]) for h in headers))

        result = "\n".join(lines)
        if len(rows) > 20:
            result += f"\n... and {len(rows) - 20} more rows."
        return result

    except Exception as e:
        return f"Query failed: {str(e)}"


def _is_safe_select_query(sql_query: str) -> bool:
    """Validate that SQL query is a safe SELECT statement.

    Args:
        sql_query: The SQL query to validate.

    Returns:
        True if the query is safe, False otherwise.
    """
    # Normalize query for checking
    normalized = sql_query.strip().upper()

    # Must start with SELECT
    if not normalized.startswith("SELECT"):
        return False

    # Forbidden keywords that indicate write operations or dangerous commands
    forbidden_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
        "EXEC", "EXECUTE", "CALL", "SCRIPT", "PROCEDURE"
    ]

    # Check for semicolons (multi-statement injection)
    # Allow semicolon only at the very end (common SQL convention)
    semicolon_count = sql_query.count(";")
    if semicolon_count > 1:
        return False
    if semicolon_count == 1 and not sql_query.rstrip().endswith(";"):
        return False

    # Remove the trailing semicolon for keyword checking
    query_to_check = sql_query.rstrip(";").strip()

    # Check for forbidden keywords in the query
    for keyword in forbidden_keywords:
        # Use word boundaries to avoid false positives (e.g., "DESCRIPTION" contains "DROP")
        if re.search(r'\b' + keyword + r'\b', query_to_check.upper()):
            return False

    # Check for comment-based injection attempts (-- or /* */)
    # These could be used to comment out validation checks
    return not ("--" in sql_query or "/*" in sql_query or "*/" in sql_query)


def list_gcs_files(bucket_name: str, prefix: str = "") -> str:
    """List files in a GCS bucket with an optional prefix filter.

    Args:
        bucket_name: The GCS bucket name (without gs:// prefix).
        prefix: Optional path prefix to filter files.

    Returns:
        List of file names as a formatted string.
    """
    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        blobs = client.list_blobs(bucket_name, prefix=prefix, max_results=50)
        names = [b.name for b in blobs]
        if not names:
            return f"No files found in {bucket_name}/{prefix}"
        return f"Files in gs://{bucket_name}/{prefix}:\n" + "\n".join(
            f"  - {n}" for n in names
        )
    except Exception as e:
        return f"GCS listing failed: {str(e)}"


def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression using AST parsing.

    Args:
        expression: A mathematical expression string (e.g., '25 * 4 + 10').

    Returns:
        The result as a string.
    """
    import ast
    import operator

    # Supported operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def eval_node(node):
        """Recursively evaluate AST nodes safely."""
        if isinstance(node, ast.Num):  # Python 3.7 compatibility
            return node.n
        elif isinstance(node, ast.Constant):  # Python 3.8+
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only numeric constants allowed")
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            op = operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")

    try:
        # Parse the expression into an AST
        tree = ast.parse(expression, mode='eval')
        # Evaluate the AST safely
        result = eval_node(tree.body)
        return str(result)
    except SyntaxError:
        return "Error: Invalid expression syntax."
    except ValueError as e:
        return f"Error: {str(e)}"
    except ZeroDivisionError:
        return "Error: Division by zero."
    except Exception as e:
        return f"Calculation error: {str(e)}"



# ── Pipeline class ────────────────────────────────────────────────────────────


class AgentPipeline(BasePipeline):
    """ADK-powered ReAct agent pipeline with real tools."""

    TOOLS = [bigquery_query, list_gcs_files, calculate]

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.max_iterations = int(config.get("max_iterations", 5))

        base_prompt = config.get(
            "system_prompt",
            "You are an expert assistant. Use available tools when needed. Think step by step.",
        )
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        self.system_prompt = f"System Info: Today is {current_date}.\n\n{base_prompt}"

    def _get_adk_model_name(self) -> str:
        """Map our model names to ADK model names."""
        # We pass the exact model name because our config now uses valid Vertex IDs
        # or keys that map 1:1 in llm_provider.
        # For ADK, we'll try to use the same key, assuming it accepts the model ID.
        mapping = {
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.0-flash": "gemini-2.0-flash-001",
            "mock": "gemini-2.0-flash-001",  # ADK needs a real model
        }
        return mapping.get(self.model, "gemini-2.0-flash-001")

    def execute(self, user_input: str) -> str:
        """Execute the agent pipeline using ADK.

        Falls back to simple LLM if ADK is not available or model is mock.
        """
        if self.model == "mock":
            return f"[MOCK AGENT] I would use tools to answer: {user_input[:100]}"

        try:
            return self._run_adk_agent(user_input)
        except ImportError:
            logger.warning("ADK not installed. Falling back to simple LLM.")
            return self._run_simple_fallback(user_input)
        except Exception as e:
            logger.warning(f"ADK agent failed: {e}")
            return self._run_simple_fallback(user_input)

    def _run_adk_agent(self, user_input: str) -> str:
        """Run the full ADK ReAct agent."""
        import google.genai.types as genai_types
        from google.adk.agents import Agent
        from google.adk.artifacts import InMemoryArtifactService
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        from app.pipelines.callbacks import LoggingCallbacks

        logging_callbacks = LoggingCallbacks()

        agent = Agent(
            name="llmops_agent",
            model=self._get_adk_model_name(),
            instruction=self.system_prompt,
            tools=self.TOOLS,
            before_agent_callback=logging_callbacks.before_agent,
            after_agent_callback=logging_callbacks.after_agent,
            before_model_callback=logging_callbacks.before_model,
            after_model_callback=logging_callbacks.after_model,
            before_tool_callback=logging_callbacks.before_tool,
            after_tool_callback=logging_callbacks.after_tool,
        )

        session_service = InMemorySessionService()
        artifact_service = InMemoryArtifactService()
        runner = Runner(
            agent=agent,
            session_service=session_service,
            artifact_service=artifact_service,
        )

        session = session_service.create_session(
            app_name="llmops_agent", user_id="system"
        )

        content = genai_types.Content(
            role="user", parts=[genai_types.Part(text=user_input)]
        )

        final_response = ""
        for event in runner.run(
            user_id="system",
            session_id=session.id,
            new_message=content,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if part.text:
                        final_response += part.text

        return final_response or "Agent completed but produced no text output."

    def _run_simple_fallback(self, user_input: str) -> str:
        """Simple LLM fallback if ADK is unavailable."""
        prompt = f"{self.system_prompt}\n\nUser: {user_input}\nAssistant:"
        return llm_provider.generate(prompt, self.model)
