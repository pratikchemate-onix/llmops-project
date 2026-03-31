import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError
from utils.config import ServerEnv, initialize_environment

def test_server_env_validation_success():
    data = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_CLOUD_LOCATION": "us-east1",
        "BIGQUERY_PROJECT": "bq-project",
        "ALLOW_ORIGINS": '["http://site.com"]'
    }
    env = ServerEnv(**data)
    assert env.google_cloud_project == "test-project"
    assert env.google_cloud_location == "us-east1"
    assert env.bigquery_project_resolved == "bq-project"
    assert env.allow_origins_list == ["http://site.com"]

def test_server_env_fallback():
    data = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
    }
    env = ServerEnv(**data)
    assert env.bigquery_project_resolved == "test-project"
    assert env.firestore_project_resolved == "test-project"
    assert env.rag_location_resolved == "us-central1"

def test_server_env_invalid_origins():
    with pytest.raises(ValidationError):
        ServerEnv(GOOGLE_CLOUD_PROJECT="p", ALLOW_ORIGINS="not-json")
    
    with pytest.raises(ValidationError):
        ServerEnv(GOOGLE_CLOUD_PROJECT="p", ALLOW_ORIGINS='{"not": "a list"}')
        
    with pytest.raises(ValidationError):
        ServerEnv(GOOGLE_CLOUD_PROJECT="p", ALLOW_ORIGINS="[]")

@patch("utils.config.load_dotenv")
def test_initialize_environment_success(mock_load):
    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-p"}):
        env = initialize_environment(ServerEnv, print_config=False)
        assert env.google_cloud_project == "test-p"

@patch("utils.config.load_dotenv")
def test_initialize_environment_failure(mock_load):
    with patch.dict(os.environ, {}, clear=True):
        # sys.exit(1) should raise SystemExit to prevent UnboundLocalError in the test
        with patch("sys.exit", side_effect=SystemExit(1)) as mock_exit:
            with pytest.raises(SystemExit):
                initialize_environment(ServerEnv, print_config=False)
            mock_exit.assert_called_once_with(1)

def test_server_env_print_config(capsys):
    env = ServerEnv(GOOGLE_CLOUD_PROJECT="test-p")
    env.print_config()
    captured = capsys.readouterr()
    assert "GOOGLE_CLOUD_PROJECT:  test-p" in captured.out
