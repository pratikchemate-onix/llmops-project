"""
Tests for agent pipeline tools (BigQuery, GCS, Calculator).
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestBigQueryTool:
    """Tests for the bigquery_query tool."""

    @patch.dict(os.environ, {"BIGQUERY_PROJECT": "test-project"})
    @patch("app.pipelines.agent_pipeline.bigquery.Client")
    def test_bigquery_query_success(self, mock_client):
        """Test successful BigQuery query execution."""
        from app.pipelines.agent_pipeline import bigquery_query

        # Mock query results
        mock_row = {"user_id": "123", "count": 42}
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([mock_row])
        mock_result.keys.return_value = ["user_id", "count"]

        mock_job = MagicMock()
        mock_job.result.return_value = [mock_row]

        mock_client_instance = MagicMock()
        mock_client_instance.query.return_value = mock_job
        mock_client.return_value = mock_client_instance

        result = bigquery_query("SELECT user_id, count FROM users LIMIT 10")

        assert "user_id" in result
        assert "count" in result
        assert "123" in result
        assert "42" in result
        mock_client_instance.query.assert_called_once()

    def test_bigquery_query_non_select(self):
        """Test that non-SELECT queries are rejected."""
        from app.pipelines.agent_pipeline import bigquery_query

        result = bigquery_query("DELETE FROM users WHERE id = 1")

        assert "Error" in result
        assert "Only SELECT" in result

    def test_bigquery_query_insert_rejected(self):
        """Test that INSERT queries are rejected."""
        from app.pipelines.agent_pipeline import bigquery_query

        result = bigquery_query("INSERT INTO users VALUES (1, 'test')")

        assert "Error" in result
        assert "Only SELECT" in result

    @patch.dict(os.environ, {}, clear=True)
    def test_bigquery_query_no_project(self):
        """Test handling when BIGQUERY_PROJECT is not set."""
        from app.pipelines.agent_pipeline import bigquery_query

        result = bigquery_query("SELECT * FROM users")

        assert "BigQuery not configured" in result
        assert "BIGQUERY_PROJECT" in result

    @patch.dict(os.environ, {"BIGQUERY_PROJECT": "test-project"})
    @patch("app.pipelines.agent_pipeline.bigquery.Client")
    def test_bigquery_query_no_results(self, mock_client):
        """Test handling of queries that return no results."""
        from app.pipelines.agent_pipeline import bigquery_query

        mock_job = MagicMock()
        mock_job.result.return_value = []

        mock_client_instance = MagicMock()
        mock_client_instance.query.return_value = mock_job
        mock_client.return_value = mock_client_instance

        result = bigquery_query("SELECT * FROM users WHERE 1=0")

        assert "no results" in result.lower()

    @patch.dict(os.environ, {"BIGQUERY_PROJECT": "test-project"})
    @patch("app.pipelines.agent_pipeline.bigquery.Client")
    def test_bigquery_query_exception(self, mock_client):
        """Test handling of query execution errors."""
        from app.pipelines.agent_pipeline import bigquery_query

        mock_client_instance = MagicMock()
        mock_client_instance.query.side_effect = Exception("Connection timeout")
        mock_client.return_value = mock_client_instance

        result = bigquery_query("SELECT * FROM users")

        assert "Query failed" in result
        assert "Connection timeout" in result

    @patch.dict(os.environ, {"BIGQUERY_PROJECT": "test-project"})
    @patch("app.pipelines.agent_pipeline.bigquery.Client")
    def test_bigquery_query_many_rows(self, mock_client):
        """Test that results are limited to 20 rows."""
        from app.pipelines.agent_pipeline import bigquery_query

        # Create 30 mock rows
        mock_rows = [{"id": i, "name": f"user{i}"} for i in range(30)]

        mock_job = MagicMock()
        mock_job.result.return_value = mock_rows

        mock_client_instance = MagicMock()
        mock_client_instance.query.return_value = mock_job
        mock_client.return_value = mock_client_instance

        result = bigquery_query("SELECT * FROM users")

        # Should mention that there are more rows
        assert "10 more rows" in result or "and 10 more" in result


class TestGCSTool:
    """Tests for the list_gcs_files tool."""

    @patch("app.pipelines.agent_pipeline.storage.Client")
    def test_list_gcs_files_success(self, mock_client):
        """Test successful GCS file listing."""
        from app.pipelines.agent_pipeline import list_gcs_files

        # Mock blob objects
        mock_blob1 = MagicMock()
        mock_blob1.name = "documents/file1.pdf"
        mock_blob2 = MagicMock()
        mock_blob2.name = "documents/file2.txt"

        mock_client_instance = MagicMock()
        mock_client_instance.list_blobs.return_value = [mock_blob1, mock_blob2]
        mock_client.return_value = mock_client_instance

        result = list_gcs_files("my-bucket", "documents/")

        assert "file1.pdf" in result
        assert "file2.txt" in result
        assert "gs://my-bucket" in result

    @patch("app.pipelines.agent_pipeline.storage.Client")
    def test_list_gcs_files_empty(self, mock_client):
        """Test handling of empty bucket/prefix."""
        from app.pipelines.agent_pipeline import list_gcs_files

        mock_client_instance = MagicMock()
        mock_client_instance.list_blobs.return_value = []
        mock_client.return_value = mock_client_instance

        result = list_gcs_files("my-bucket", "empty/")

        assert "No files found" in result
        assert "my-bucket" in result

    @patch("app.pipelines.agent_pipeline.storage.Client")
    def test_list_gcs_files_no_prefix(self, mock_client):
        """Test listing files without prefix."""
        from app.pipelines.agent_pipeline import list_gcs_files

        mock_blob = MagicMock()
        mock_blob.name = "root-file.txt"

        mock_client_instance = MagicMock()
        mock_client_instance.list_blobs.return_value = [mock_blob]
        mock_client.return_value = mock_client_instance

        result = list_gcs_files("my-bucket")

        assert "root-file.txt" in result

    @patch("app.pipelines.agent_pipeline.storage.Client")
    def test_list_gcs_files_exception(self, mock_client):
        """Test handling of GCS errors."""
        from app.pipelines.agent_pipeline import list_gcs_files

        mock_client_instance = MagicMock()
        mock_client_instance.list_blobs.side_effect = Exception("Access denied")
        mock_client.return_value = mock_client_instance

        result = list_gcs_files("my-bucket")

        assert "GCS listing failed" in result
        assert "Access denied" in result


class TestCalculatorTool:
    """Tests for the calculate tool."""

    def test_calculate_simple_addition(self):
        """Test simple addition."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("5 + 3")
        assert result == "8"

    def test_calculate_multiplication(self):
        """Test multiplication."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("25 * 4")
        assert result == "100"

    def test_calculate_complex_expression(self):
        """Test complex mathematical expression."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("(10 + 5) * 2 - 3")
        assert result == "27"

    def test_calculate_decimal(self):
        """Test decimal calculations."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("10.5 + 2.3")
        assert "12.8" in result

    def test_calculate_invalid_characters(self):
        """Test rejection of invalid characters."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("import os; os.system('ls')")

        assert "Error" in result
        assert "invalid characters" in result.lower()

    def test_calculate_alphabet_rejected(self):
        """Test that alphabetic characters are rejected."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("abc")

        assert "Error" in result

    def test_calculate_injection_attempt(self):
        """Test that code injection attempts are blocked."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("__import__('os').system('ls')")

        assert "Error" in result

    def test_calculate_division(self):
        """Test division."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("100 / 4")
        assert result == "25.0" or result == "25"

    def test_calculate_modulo(self):
        """Test modulo operation."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("10 % 3")
        assert result == "1"

    def test_calculate_exception_handling(self):
        """Test handling of calculation errors (e.g., division by zero)."""
        from app.pipelines.agent_pipeline import calculate

        result = calculate("1 / 0")

        # Should handle gracefully, not crash
        assert isinstance(result, str)
