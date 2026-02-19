from app.infrastructure.llm.base import LLMExtractor
from app.infrastructure.llm.ollama import OllamaExtractor
from app.infrastructure.llm.openai_extractor import OpenAIExtractor


class LLMExtractorFactory:
    """Factory for creating LLM extractor instances."""

    @classmethod
    def create_ollama(
        cls,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        **kwargs,
    ) -> OllamaExtractor:
        """Create an Ollama extractor."""
        return OllamaExtractor(model=model, host=host, **kwargs)

    @classmethod
    def create_openai(
        cls,
        api_key: str,
        model: str = "gpt-4o-mini",
        **kwargs,
    ) -> OpenAIExtractor:
        """Create an OpenAI extractor."""
        return OpenAIExtractor(api_key=api_key, model=model, **kwargs)

    @classmethod
    def create(cls, provider: str, **kwargs) -> LLMExtractor:
        """Create an extractor by provider name."""
        provider = provider.lower()

        if provider == "ollama":
            return cls.create_ollama(**kwargs)
        elif provider == "openai":
            return cls.create_openai(**kwargs)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Available: ollama, openai")
