from app.pipelines.base import BasePipeline
from app.services import llm_provider
from app.services.vector_store import VectorStoreFactory


class RAGPipeline(BasePipeline):
    def execute(self, user_input: str) -> str:
        """
        Executes the RAG pipeline flow with context retrieval.
        """
        # 1. Retrieve Context
        context = ""
        try:
            # Get the configured vector store (defaulting to mock for now)
            store_type = self.config.get("vector_store_type", "mock")
            vector_store = VectorStoreFactory.get_store(store_type)

            # Retrieve documents
            limit = self.config.get("top_k", 3)
            retrieved_docs = vector_store.search(user_input, limit=limit)

            if retrieved_docs:
                context = "\n\n".join(retrieved_docs)
            else:
                context = "No relevant documents found."

        except Exception as e:
            # Fallback to empty context if retrieval fails
            print(f"RAG Retrieval failed: {e}")
            context = "Error retrieving documents."

        # 2. Format Prompt
        # The prompt template expects {context} and {user_input}
        prompt_template = self.config.get(
            "prompt_template", "Context:\n{context}\n\nQuestion: {user_input}"
        )
        prompt = prompt_template.format(user_input=user_input, context=context)

        # 3. Generate
        return llm_provider.generate(prompt, self.model)
