from unittest.mock import MagicMock, patch

from app.pipelines.rag_pipeline import RAGPipeline


def test_rag_pipeline_execute():
    """Test that RAGPipeline.execute calls the LLM with the correct prompt format."""
    # Arrange
    config = {
        "model": "mock-rag-model",
        "prompt_template": "Context: {context}\nQuestion: {user_input}",
        "vector_store_type": "mock",
    }
    pipeline = RAGPipeline(config)
    user_input = "What is the capital of France?"

    # Mock the VectorStoreFactory and the vector store
    with patch("app.pipelines.rag_pipeline.VectorStoreFactory") as MockFactory:
        mock_store = MagicMock()
        mock_store.search.return_value = ["Doc 1", "Doc 2"]
        MockFactory.get_store.return_value = mock_store

        # Mock the llm_provider.generate function
        with patch("app.pipelines.rag_pipeline.llm_provider.generate") as mock_generate:
            mock_generate.return_value = "Paris is the capital of France."

            # Act
            result = pipeline.execute(user_input)

            # Assert
            assert result == "Paris is the capital of France."

            # Verify that the prompt was formatted correctly with retrieved docs
            expected_prompt = "Context: Doc 1\n\nDoc 2\n" "Question: What is the capital of France?"
            mock_generate.assert_called_once_with(expected_prompt, "mock-rag-model")

            # Verify vector store interaction
            MockFactory.get_store.assert_called_with("mock")
            mock_store.search.assert_called_with(user_input, limit=3)
