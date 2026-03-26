"""
Tests for RAG pipeline with Vertex AI RAG Engine integration.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestRAGPipelineInitialization:
    """Tests for RAG pipeline initialization."""

    def test_rag_pipeline_init(self):
        """Test RAG pipeline initialization with config."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "prompt_template": "Context:\n{context}\n\nQ: {user_input}\nA:",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test-corpus",
            "top_k": 5,
        }

        pipeline = RAGPipeline(config)

        assert pipeline.top_k == 5
        assert pipeline.corpus_id == config["rag_corpus_id"]
        assert "{context}" in pipeline.prompt_template
        assert "{user_input}" in pipeline.prompt_template

    def test_rag_pipeline_default_top_k(self):
        """Test default top_k value."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)

        assert pipeline.top_k == 3  # Default value

    def test_rag_pipeline_default_prompt_template(self):
        """Test default prompt template."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)

        assert "{context}" in pipeline.prompt_template
        assert "{user_input}" in pipeline.prompt_template


class TestRAGVertexAIIntegration:
    """Tests for Vertex AI RAG Engine integration."""

    @patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "RAG_LOCATION": "us-central1",
            "FIRESTORE_PROJECT": "test-project",
        },
    )
    @patch("app.pipelines.rag_pipeline.vertexai")
    def test_rag_init_success(self, mock_vertexai):
        """Test successful Vertex AI initialization."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)
        result = pipeline._init_rag()

        assert result is True
        mock_vertexai.init.assert_called_once_with(
            project="test-project", location="us-central1"
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_rag_init_no_project(self):
        """Test RAG initialization without project configured."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)
        result = pipeline._init_rag()

        assert result is False

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    def test_rag_init_no_corpus(self):
        """Test RAG initialization without corpus ID."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "",  # Empty corpus ID
        }

        pipeline = RAGPipeline(config)
        result = pipeline._init_rag()

        assert result is False

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    def test_rag_init_exception(self, mock_vertexai):
        """Test handling of Vertex AI initialization errors."""
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_vertexai.init.side_effect = Exception("API not enabled")

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)
        result = pipeline._init_rag()

        assert result is False

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    def test_rag_init_idempotent(self, mock_vertexai):
        """Test that _init_rag can be called multiple times safely."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)

        # First call
        result1 = pipeline._init_rag()
        # Second call
        result2 = pipeline._init_rag()

        assert result1 is True
        assert result2 is True
        # Should only initialize once
        assert mock_vertexai.init.call_count == 1


class TestRAGContextRetrieval:
    """Tests for RAG context retrieval."""

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    @patch("app.pipelines.rag_pipeline.rag")
    def test_retrieve_context_success(self, mock_rag, mock_vertexai):
        """Test successful context retrieval."""
        from app.pipelines.rag_pipeline import RAGPipeline

        # Mock RAG response
        mock_context1 = MagicMock()
        mock_context1.source_uri = "gs://bucket/doc1.pdf"
        mock_context1.text = "This is relevant content from document 1."

        mock_context2 = MagicMock()
        mock_context2.source_uri = "gs://bucket/doc2.pdf"
        mock_context2.text = "This is relevant content from document 2."

        mock_response = MagicMock()
        mock_response.contexts.contexts = [mock_context1, mock_context2]

        mock_rag.retrieval_query.return_value = mock_response

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
            "top_k": 2,
        }

        pipeline = RAGPipeline(config)
        context, num_chunks = pipeline._retrieve_context("What is the policy?")

        assert num_chunks == 2
        assert "doc1.pdf" in context
        assert "doc2.pdf" in context
        assert "relevant content from document 1" in context
        assert "relevant content from document 2" in context

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    @patch("app.pipelines.rag_pipeline.rag")
    def test_retrieve_context_no_results(self, mock_rag, mock_vertexai):
        """Test retrieval when no relevant documents are found."""
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_response = MagicMock()
        mock_response.contexts.contexts = []

        mock_rag.retrieval_query.return_value = mock_response

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)
        context, num_chunks = pipeline._retrieve_context("Unknown question")

        assert num_chunks == 0
        assert context == ""

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    @patch("app.pipelines.rag_pipeline.rag")
    def test_retrieve_context_exception(self, mock_rag, mock_vertexai):
        """Test handling of retrieval errors."""
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_rag.retrieval_query.side_effect = Exception("Corpus not found")

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)
        context, num_chunks = pipeline._retrieve_context("What is the policy?")

        assert num_chunks == 0
        assert context == ""

    @patch.dict(os.environ, {}, clear=True)
    def test_retrieve_context_not_initialized(self):
        """Test retrieval when RAG is not initialized."""
        from app.pipelines.rag_pipeline import RAGPipeline

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "",  # No corpus
        }

        pipeline = RAGPipeline(config)
        context, num_chunks = pipeline._retrieve_context("What is the policy?")

        assert num_chunks == 0
        assert context == ""


class TestRAGPipelineExecution:
    """Tests for full RAG pipeline execution."""

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    @patch("app.pipelines.rag_pipeline.rag")
    @patch("app.pipelines.rag_pipeline.llm_provider.generate")
    def test_execute_with_context(self, mock_generate, mock_rag, mock_vertexai):
        """Test RAG pipeline execution with retrieved context."""
        from app.pipelines.rag_pipeline import RAGPipeline

        # Mock context retrieval
        mock_context = MagicMock()
        mock_context.source_uri = "gs://bucket/policy.pdf"
        mock_context.text = "Maternity leave is 12 weeks."

        mock_response = MagicMock()
        mock_response.contexts.contexts = [mock_context]
        mock_rag.retrieval_query.return_value = mock_response

        # Mock LLM response
        mock_generate.return_value = "Based on the policy, maternity leave is 12 weeks."

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
            "prompt_template": "Context:\n{context}\n\nQ: {user_input}\nA:",
        }

        pipeline = RAGPipeline(config)
        result = pipeline.execute("What is the maternity leave policy?")

        assert "12 weeks" in result
        mock_generate.assert_called_once()

        # Verify prompt included context
        call_args = mock_generate.call_args
        prompt = call_args[0][0]
        assert "Maternity leave is 12 weeks" in prompt

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"})
    @patch("app.pipelines.rag_pipeline.vertexai")
    @patch("app.pipelines.rag_pipeline.rag")
    @patch("app.pipelines.rag_pipeline.llm_provider.generate")
    def test_execute_no_context_found(self, mock_generate, mock_rag, mock_vertexai):
        """Test RAG pipeline when no relevant context is found."""
        from app.pipelines.rag_pipeline import RAGPipeline

        # Mock empty retrieval
        mock_response = MagicMock()
        mock_response.contexts.contexts = []
        mock_rag.retrieval_query.return_value = mock_response

        mock_generate.return_value = "I don't have information about that."

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "projects/test/locations/us-central1/ragCorpora/test",
        }

        pipeline = RAGPipeline(config)
        result = pipeline.execute("What is the unknown policy?")

        # Should still generate a response, but with NO_CONTEXT_NOTE
        assert isinstance(result, str)
        # The response should indicate no context was found
        assert "could not find relevant information" in result.lower() or "don't have information" in result.lower()

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.pipelines.rag_pipeline.llm_provider.generate")
    def test_execute_rag_not_configured(self, mock_generate):
        """Test execution when RAG is not configured."""
        from app.pipelines.rag_pipeline import RAGPipeline

        mock_generate.return_value = "I cannot answer without context."

        config = {
            "active_model": "gemini-pro",
            "rag_corpus_id": "",
        }

        pipeline = RAGPipeline(config)
        result = pipeline.execute("What is the policy?")

        # Should still execute but with no context
        assert isinstance(result, str)
