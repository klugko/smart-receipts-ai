from app.infrastructure.ocr.base import OCREngine, OCRResult
from app.infrastructure.ocr.tesseract import TesseractOCR
from app.infrastructure.ocr.easyocr_engine import EasyOCREngine
from app.infrastructure.ocr.factory import OCREngineFactory

__all__ = [
    "OCREngine",
    "OCRResult",
    "TesseractOCR",
    "EasyOCREngine",
    "OCREngineFactory",
]
