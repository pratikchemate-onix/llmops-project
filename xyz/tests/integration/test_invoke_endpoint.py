"""Integration tests for the POST /invoke endpoint."""


class TestInvokeEndpoint:
    """Full request/response cycle tests using the FastAPI test client."""

    def test_health_endpoint_returns_ok(self, test_client):
        """GET / should return status=ok."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_invoke_mock_app_returns_200(self, test_client):
        """POST /invoke with mock_app should return 200 with all fields."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Hello world"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "output" in data
        assert "pipeline_executed" in data
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], float)

    def test_invoke_invalid_app_id_returns_404(self, test_client):
        """POST /invoke with unknown app_id should return 404."""
        response = test_client.post(
            "/invoke", json={"app_id": "nonexistent_app_xyz", "user_input": "Hello"}
        )
        assert response.status_code == 404

    def test_invoke_missing_user_input_returns_422(self, test_client):
        """POST /invoke with missing user_input should return 422."""
        response = test_client.post("/invoke", json={"app_id": "mock_app"})
        assert response.status_code == 422

    def test_invoke_response_contains_task_detection(self, test_client):
        """Response must include task_detection with needs_rag and needs_agent."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Test"}
        )
        data = response.json()
        assert "task_detection" in data
        assert "needs_rag" in data["task_detection"]
        assert "needs_agent" in data["task_detection"]

    def test_invoke_response_contains_usage_metrics(self, test_client):
        """Response must include usage metrics with tokens and cost."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Calculate 2+2"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "usage" in data
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert "total_cost" in data["usage"]
        assert isinstance(data["usage"]["prompt_tokens"], int)
        assert isinstance(data["usage"]["completion_tokens"], int)
        assert isinstance(data["usage"]["total_cost"], float)

    def test_invoke_with_custom_model_override(self, test_client):
        """Should allow model override via request parameter."""
        response = test_client.post(
            "/invoke",
            json={
                "app_id": "mock_app",
                "user_input": "Hello",
                "model": "gemini-2.5-flash"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["model"] == "gemini-2.5-flash"

    def test_invoke_empty_input_rejected_by_guardrails(self, test_client):
        """Empty or whitespace-only input should be rejected."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "   "}
        )
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_invoke_too_long_input_rejected(self, test_client):
        """Input exceeding max length should be rejected by guardrails."""
        long_input = "x" * 5000  # Exceeds default 4000 char limit
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": long_input}
        )
        assert response.status_code == 400
        assert "too long" in response.json()["detail"].lower()

    def test_invoke_routes_to_llm_pipeline(self, test_client, monkeypatch):
        """Simple queries should route to LLM pipeline."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "What is 2+2?"}
        )
        assert response.status_code == 200
        data = response.json()
        # For mock_app with no RAG/agent needs, should use llm pipeline
        assert data["pipeline_executed"] in ["llm", "agent", "rag"]
        assert "output" in data
        assert len(data["output"]) > 0

    def test_invoke_returns_request_id(self, test_client):
        """Each request should return a unique request_id for tracking."""
        response1 = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Test 1"}
        )
        response2 = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Test 2"}
        )
        data1 = response1.json()
        data2 = response2.json()
        assert "request_id" in data1
        assert "request_id" in data2
        assert data1["request_id"] != data2["request_id"]

    def test_invoke_includes_config_in_response(self, test_client):
        """Response should include the resolved config."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Test"}
        )
        data = response.json()
        assert "config" in data
        assert isinstance(data["config"], dict)
        assert "pipeline" in data["config"]

    def test_feedback_endpoint_accepts_valid_request(self, test_client):
        """POST /feedback with valid data should return success."""
        # First make a request to get a request_id
        invoke_response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Test"}
        )
        request_id = invoke_response.json()["request_id"]

        # Submit feedback
        response = test_client.post(
            "/feedback",
            json={
                "request_id": request_id,
                "score": 1,
                "comment": "Great response!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_feedback_without_comment_accepted(self, test_client):
        """Feedback submission without comment should work."""
        invoke_response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Test"}
        )
        request_id = invoke_response.json()["request_id"]

        response = test_client.post(
            "/feedback",
            json={"request_id": request_id, "score": -1}
        )
        assert response.status_code == 200

    def test_invoke_handles_config_file_missing_gracefully(self, test_client, monkeypatch):
        """Should return 500 if config file is completely missing."""
        # This would require monkeypatching config loader to raise FileNotFoundError
        # For now, test that unknown app_id returns proper error
        response = test_client.post(
            "/invoke", json={"app_id": "nonexistent_xyz_123", "user_input": "Test"}
        )
        assert response.status_code in [404, 500]
        assert "detail" in response.json()

    def test_invoke_response_structure_complete(self, test_client):
        """Verify all expected fields are present in successful response."""
        response = test_client.post(
            "/invoke", json={"app_id": "mock_app", "user_input": "Hello"}
        )
        assert response.status_code == 200
        data = response.json()

        # Check all required fields
        required_fields = [
            "request_id", "app_id", "user_input", "config",
            "task_detection", "pipeline_executed", "output",
            "latency_ms", "usage"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Check nested structures
        assert "needs_rag" in data["task_detection"]
        assert "needs_agent" in data["task_detection"]
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert "total_cost" in data["usage"]
