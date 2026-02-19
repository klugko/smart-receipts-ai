from abc import ABC, abstractmethod
from dataclasses import dataclass
from PIL import Image


@dataclass
class ExtractionResult:
    """Result from LLM extraction."""

    raw_response: str
    parsed_data: dict
    model: str
    tokens_used: int | None = None


class LLMExtractor(ABC):
    """Abstract base class for LLM-based extractors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    async def extract_from_text(self, ocr_text: str) -> ExtractionResult:
        """Extract structured data from OCR text."""
        pass

    async def extract_from_image(self, image: Image.Image) -> ExtractionResult:
        """Extract structured data directly from image (vision models only)."""
        raise NotImplementedError("This extractor does not support vision extraction")

    @property
    def supports_vision(self) -> bool:
        """Whether this extractor supports direct image input."""
        return False
