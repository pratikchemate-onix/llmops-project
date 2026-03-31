import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def setup_vertex_mock():
    # Create complete mock tree for vertexai
    mock_vertex = MagicMock()
    mock_preview = MagicMock()
    mock_rag = MagicMock()

    mock_preview.rag = mock_rag
    mock_vertex.preview = mock_preview

    with patch.dict(
        sys.modules,
        {
            "vertexai": mock_vertex,
            "vertexai.preview": mock_preview,
            "vertexai.preview.rag": mock_rag,
        }
    ):
        yield {"vertexai": mock_vertex, "rag": mock_rag}


class TestRAGPipelineInitialization:
    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_rag_pipeline_init(self):
        from app.pipelines.rag_pipeline import RAGPipeline
        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "test-corpus",
            "top_k": 5,
        }
        pipeline = RAGPipeline(config)
        assert pipeline.model == "gemini-pro"
        assert pipeline.corpus_id == "test-corpus"
        assert pipeline.top_k == 5
        assert not pipeline._rag_initialized

    def test_rag_pipeline_default_top_k(self):
        from app.pipelines.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline({"active_model": "gemini-pro"})
        assert pipeline.top_k == 3

    def test_rag_pipeline_default_prompt_template(self):
        from app.pipelines.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline({"active_model": "gemini-pro"})
        assert "{context}" in pipeline.prompt_template
        assert "{user_input}" in pipeline.prompt_template


class TestRAGVertexAIIntegration:
    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project", "RAG_LOCATION": "us-central1"})
    def test_rag_init_success(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "test",
        }
        pipeline = RAGPipeline(config)
        result = pipeline._init_rag()
        assert result is True
        setup_vertex_mock["vertexai"].init.assert_called_once_with(project="test-project", location="us-central1")

    @patch.dict(os.environ, {}, clear=True)
    def test_rag_init_no_project(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        result = pipeline._init_rag()
        assert result is False
        setup_vertex_mock["vertexai"].init.assert_not_called()

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_rag_init_no_corpus(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": ""})
        result = pipeline._init_rag()
        assert result is False
        setup_vertex_mock["vertexai"].init.assert_not_called()

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_rag_init_exception(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        setup_vertex_mock["vertexai"].init.side_effect = Exception("API not enabled")
        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        result = pipeline._init_rag()
        assert result is False

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_rag_init_idempotent(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        assert pipeline._init_rag() is True
        assert pipeline._init_rag() is True
        assert setup_vertex_mock["vertexai"].init.call_count == 1


class TestRAGContextRetrieval:
    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_retrieve_context_success(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_context1 = MagicMock()
        mock_context1.source_uri = "gs://doc1.pdf"
        mock_context1.text = "content 1"

        mock_response = MagicMock()
        mock_response.contexts.contexts = [mock_context1]
        setup_vertex_mock["rag"].retrieval_query.return_value = mock_response

        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test", "top_k": 1})
        context, num_chunks = pipeline._retrieve_context("query")

        assert num_chunks == 1
        assert "content 1" in context

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_retrieve_context_no_results(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        mock_response = MagicMock()
        mock_response.contexts.contexts = []
        setup_vertex_mock["rag"].retrieval_query.return_value = mock_response

        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        context, num_chunks = pipeline._retrieve_context("query")
        assert num_chunks == 0
        assert context == ""

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_retrieve_context_exception(self, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        setup_vertex_mock["rag"].retrieval_query.side_effect = Exception("Error")

        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        context, num_chunks = pipeline._retrieve_context("query")
        assert num_chunks == 0
        assert context == ""


class TestRAGPipelineExecution:
    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.llm_provider.generate")
    def test_execute_with_context(self, mock_generate, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_context = MagicMock()
        mock_context.source_uri = "gs://doc.pdf"
        mock_context.text = "12 weeks."
        mock_response = MagicMock()
        mock_response.contexts.contexts = [mock_context]
        setup_vertex_mock["rag"].retrieval_query.return_value = mock_response
        mock_generate.return_value = "12 weeks."

        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        result, num_chunks = pipeline.execute("query")

        assert "12 weeks" in result
        mock_generate.assert_called_once()

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.llm_provider.generate")
    def test_execute_no_context_found(self, mock_generate, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_response = MagicMock()
        mock_response.contexts.contexts = []
        setup_vertex_mock["rag"].retrieval_query.return_value = mock_response
        mock_generate.return_value = "No info."

        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": "test"})
        result, num_chunks = pipeline.execute("query")
        assert isinstance(result, str)

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.pipelines.rag_pipeline.llm_provider.generate")
    def test_execute_rag_not_configured(self, mock_generate, setup_vertex_mock):
        from app.pipelines.rag_pipeline import RAGPipeline
        mock_generate.return_value = "No info."

        pipeline = RAGPipeline({"active_model": "gemini-pro", "rag_corpus_id": ""})
        result, num_chunks = pipeline.execute("query")
        assert isinstance(result, str)
