"""Tests for the logging service."""

from unittest.mock import patch

import pytest

import app.services.logging_service


class TestLoggingService:
    """Test BigQuery logging logic."""

    @pytest.fixture(autouse=True)
    def reset_bq_globals(self):
        """Reset global variables in logging_service to ensure clean state."""
        app.services.logging_service._BQ_CLIENT = None
        app.services.logging_service._BQ_TABLE = None
        yield
        app.services.logging_service._BQ_CLIENT = None
        app.services.logging_service._BQ_TABLE = None

    @pytest.fixture
    def mock_bq_client(self):
        with patch("google.cloud.bigquery.Client") as mock_client:
            yield mock_client

    def test_log_request_success(self, mock_bq_client):
        """Should log to BigQuery when client is available."""
        # Setup mock
        mock_instance = mock_bq_client.return_value
        mock_instance.insert_rows_json.return_value = []  # No errors

        # Environment variable needed to trigger BQ path
        with patch.dict("os.environ", {"BIGQUERY_PROJECT": "test-project"}):
            app.services.logging_service.log_request(
                request_id="req-123",
                app_id="test_app",
                user_input="hello",
                output="world",
                pipeline_executed="llm",
                latency_ms=100.5,
                task_detection={"needs_rag": False},
                config={"model": "gemini"},
                session_id="sess_123",
                retrieved_chunks=0,
                guardrail_pass=True,
            )

        # Verify BigQuery client called
        mock_instance.insert_rows_json.assert_called_once()
        call_args = mock_instance.insert_rows_json.call_args
        table_id, rows = call_args[0]

        assert table_id == "test-project.llmops.requests"
        assert len(rows) == 1
        row = rows[0]
        assert row["app_id"] == "test_app"
        assert row["user_input"] == "hello"
        assert row["latency_ms"] == 100.5
        assert row["guardrail_pass"] is True

    def test_log_request_fallback_on_error(self, mock_bq_client):
        """Should fallback to stdout if BigQuery fails."""
        mock_instance = mock_bq_client.return_value
        # Simulate BQ error
        mock_instance.insert_rows_json.side_effect = Exception("BQ Error")

        with patch("app.services.logging_service.logger") as mock_logger:
            with patch.dict("os.environ", {"BIGQUERY_PROJECT": "test-project"}):
                app.services.logging_service.log_request(
                    request_id="req-123",
                app_id="test_app",
                    user_input="hello",
                    output="world",
                    pipeline_executed="llm",
                    latency_ms=100.0,
                    task_detection={},
                    config={},
                )

            # Check that it logged the error and the fallback info
            assert mock_logger.error.called
            assert mock_logger.info.called
            # Verify the info log contains the JSON payload
            info_call_args = mock_logger.info.call_args[0][0]
            assert "INVOKE_LOG:" in info_call_args

    def test_log_request_no_project_env(self, mock_bq_client):
        """Should fallback to stdout if BIGQUERY_PROJECT is not set."""
        with patch("app.services.logging_service.logger") as mock_logger:
            with patch.dict("os.environ", {}, clear=True):
                app.services.logging_service.log_request(
                    request_id="req-123",
                app_id="test_app",
                    user_input="hello",
                    output="world",
                    pipeline_executed="llm",
                    latency_ms=100.0,
                    task_detection={},
                    config={},
                )

        # Verify BigQuery client NOT called
        mock_bq_client.assert_not_called()
        # Verify stdout log
        assert mock_logger.info.called
        info_call_args = mock_logger.info.call_args[0][0]
        assert "INVOKE_LOG:" in info_call_args
