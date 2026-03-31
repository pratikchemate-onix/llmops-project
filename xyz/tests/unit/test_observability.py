import os
import pytest
from unittest.mock import patch, MagicMock
from utils.observability import configure_otel_resource, setup_opentelemetry

def test_configure_otel_resource():
    with patch.dict(os.environ, {}, clear=True):
        configure_otel_resource("test-agent", "test-project")
        assert "OTEL_RESOURCE_ATTRIBUTES" in os.environ
        attr = os.environ["OTEL_RESOURCE_ATTRIBUTES"]
        assert "service.name=test-agent" in attr
        assert "gcp.project_id=test-project" in attr

@patch("google.auth.default")
@patch("utils.observability.logs.set_logger_provider")
@patch("utils.observability.trace.set_tracer_provider")
@patch("utils.observability.LoggingInstrumentor")
@patch("utils.observability.GoogleGenAiSdkInstrumentor")
@patch("utils.observability.OTLPSpanExporter")
@patch("utils.observability.CloudLoggingExporter")
@patch("utils.observability.LoggingServiceV2Client")
@patch("grpc.composite_channel_credentials")
def test_setup_opentelemetry_success(
    mock_grpc, mock_bq_client, mock_cloud_log, mock_otlp, mock_genai, mock_logging, mock_set_trace, mock_set_logs, mock_auth
):
    # Mock auth
    mock_creds = MagicMock()
    mock_creds.with_quota_project.return_value = mock_creds
    mock_auth.return_value = (mock_creds, "project")
    
    # Mock the return values of the Instrumentors
    mock_logging_inst = MagicMock()
    mock_logging.return_value = mock_logging_inst
    
    mock_genai_inst = MagicMock()
    mock_genai.return_value = mock_genai_inst
    
    with patch.dict(os.environ, {"OTEL_RESOURCE_ATTRIBUTES": "existing=val"}):
        setup_opentelemetry("test-project", "test-agent", "INFO")
        
    mock_auth.assert_called_once()
    mock_logging_inst.instrument.assert_called_once()
    mock_genai_inst.instrument.assert_called_once()

def test_setup_opentelemetry_invalid_loglevel(capsys):
    # Just test that it defaults to INFO and doesn't crash before auth
    with patch("google.auth.default", side_effect=Exception("stop here")):
        with pytest.raises(Exception):
            setup_opentelemetry("p", "a", "INVALID")
    
    captured = capsys.readouterr()
    assert "Defaulting to 'INFO'" in captured.out
