from abc import ABC, abstractmethod
from dataclasses import dataclass
from PIL import Image


@dataclass
class OCRResult:
    """Result from OCR extraction."""

    text: str
    confidence: float
    language: str | None = None


class OCREngine(ABC):
    """Abstract base class for OCR engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier."""
        pass

    @abstractmethod
    def extract_text(self, image: Image.Image) -> OCRResult:
        """Extract text from a single image."""
        pass

    def extract_text_batch(self, images: list[Image.Image]) -> list[OCRResult]:
        """Extract text from multiple images."""
        return [self.extract_text(img) for img in images]

    def combine_results(self, results: list[OCRResult]) -> OCRResult:
        """Combine multiple OCR results into one."""
        if not results:
            return OCRResult(text="", confidence=0.0)

        combined_text = "\n\n".join(r.text for r in results if r.text)
        avg_confidence = sum(r.confidence for r in results) / len(results)
        language = results[0].language

        return OCRResult(
            text=combined_text,
            confidence=avg_confidence,
            language=language,
        )
