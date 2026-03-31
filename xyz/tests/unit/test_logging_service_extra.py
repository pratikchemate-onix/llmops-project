import logging
from unittest.mock import patch, MagicMock
from app.services.logging_service import log_evaluation, log_feedback

@patch("app.services.logging_service._get_bq_client")
def test_log_evaluation_success(mock_get_bq):
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = []
    mock_get_bq.return_value = (mock_client, "test-project")
    
    log_evaluation("req-123", "correctness", 4.5, "Good response")
    
    mock_client.insert_rows_json.assert_called_once()
    args = mock_client.insert_rows_json.call_args[0]
    assert args[0] == "test-project.llmops.evaluations"
    assert args[1][0]["request_id"] == "req-123"

@patch("app.services.logging_service._get_bq_client")
def test_log_evaluation_failure(mock_get_bq, caplog):
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = [{"index": 0, "errors": ["error"]}]
    mock_get_bq.return_value = (mock_client, "test-project")
    
    with caplog.at_level(logging.ERROR):
        log_evaluation("req-123", "correctness", 4.5, "Good response")
    
    assert "BQ evaluation insert errors" in caplog.text

@patch("app.services.logging_service._get_bq_client")
def test_log_feedback_success(mock_get_bq):
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = []
    mock_get_bq.return_value = (mock_client, "test-project")
    
    log_feedback("req-123", 1, "Helpful")
    
    mock_client.insert_rows_json.assert_called_once()
    args = mock_client.insert_rows_json.call_args[0]
    assert args[0] == "test-project.llmops.feedback"
    assert args[1][0]["score"] == 1

@patch("app.services.logging_service._get_bq_client")
def test_log_feedback_failure(mock_get_bq, caplog):
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = [{"index": 0, "errors": ["error"]}]
    mock_get_bq.return_value = (mock_client, "test-project")
    
    with caplog.at_level(logging.ERROR):
        log_feedback("req-123", 1, "Helpful")
    
    assert "BQ feedback insert errors" in caplog.text

@patch("app.services.logging_service._get_bq_client")
def test_log_feedback_exception(mock_get_bq, caplog):
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = Exception("BQ down")
    mock_get_bq.return_value = (mock_client, "test-project")
    
    with caplog.at_level(logging.ERROR):
        log_feedback("req-123", 1, "Helpful")
    
    assert "BQ feedback insert failed" in caplog.text
