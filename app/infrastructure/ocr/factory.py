from app.infrastructure.ocr.base import OCREngine
from app.infrastructure.ocr.tesseract import TesseractOCR


class OCREngineFactory:
    """Factory for creating OCR engine instances."""

    @classmethod
    def create(cls, engine_name: str, **kwargs) -> OCREngine:
        """Create an OCR engine by name."""
        engine_name = engine_name.lower()

        if engine_name == "tesseract":
            return TesseractOCR(**kwargs)
        elif engine_name == "easyocr":
            from app.infrastructure.ocr.easyocr_engine import EasyOCREngine
            return EasyOCREngine(**kwargs)
        else:
            available = cls.available_engines()
            raise ValueError(f"Unknown OCR engine: {engine_name}. Available: {', '.join(available)}")

    @classmethod
    def available_engines(cls) -> list[str]:
        """List available OCR engines."""
        engines = ["tesseract"]

        try:
            from app.infrastructure.ocr.easyocr_engine import is_easyocr_available
            if is_easyocr_available():
                engines.append("easyocr")
        except ImportError:
            pass

        return engines

    @classmethod
    def is_available(cls, engine_name: str) -> bool:
        """Check if an OCR engine is available."""
        return engine_name.lower() in cls.available_engines()
