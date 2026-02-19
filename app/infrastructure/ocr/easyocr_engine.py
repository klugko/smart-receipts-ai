import numpy as np
from PIL import Image

from app.domain.exceptions import OCRExtractionError
from app.infrastructure.ocr.base import OCREngine, OCRResult

try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


class EasyOCREngine(OCREngine):
    """EasyOCR engine implementation with GPU support."""

    _reader_cache: dict = {}

    def __init__(
        self,
        languages: list[str] | None = None,
        gpu: bool = False,
    ):
        if not EASYOCR_AVAILABLE:
            raise OCRExtractionError(
                message="EasyOCR is not installed. Install with: pip install -r requirements-easyocr.txt",
                details={"install_command": "pip install -r requirements-easyocr.txt"},
            )

        self._languages = languages or ["en", "de", "fr"]
        self._gpu = gpu
        self._reader = None

    @property
    def name(self) -> str:
        return "easyocr"

    def _get_reader(self):
        """Get or create EasyOCR reader with caching."""
        cache_key = (tuple(self._languages), self._gpu)

        if cache_key not in EasyOCREngine._reader_cache:
            EasyOCREngine._reader_cache[cache_key] = easyocr.Reader(
                self._languages,
                gpu=self._gpu,
            )

        return EasyOCREngine._reader_cache[cache_key]

    def extract_text(self, image: Image.Image) -> OCRResult:
        """Extract text using EasyOCR."""
        try:
            reader = self._get_reader()
            img_array = np.array(image)

            results = reader.readtext(img_array)

            text_parts = []
            confidences = []

            for _bbox, text, confidence in results:
                if text.strip():
                    text_parts.append(text)
                    confidences.append(confidence)

            full_text = " ".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                language=self._languages[0] if self._languages else None,
            )

        except Exception as e:
            raise OCRExtractionError(
                message="EasyOCR extraction failed",
                details={"error": str(e)},
            ) from e


def is_easyocr_available() -> bool:
    """Check if EasyOCR is installed."""
    return EASYOCR_AVAILABLE
