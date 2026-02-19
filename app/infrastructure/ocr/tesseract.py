import pytesseract
from PIL import Image

from app.domain.exceptions import OCRExtractionError
from app.infrastructure.ocr.base import OCREngine, OCRResult


class TesseractOCR(OCREngine):
    """Tesseract OCR engine implementation."""

    def __init__(
        self,
        languages: str = "eng+deu+fra",
        psm: int = 3,
        oem: int = 3,
    ):
        self._languages = languages
        self._psm = psm
        self._oem = oem
        self._config = f"--psm {psm} --oem {oem}"

    @property
    def name(self) -> str:
        return "tesseract"

    def extract_text(self, image: Image.Image) -> OCRResult:
        """Extract text using Tesseract OCR."""
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self._languages,
                config=self._config,
                output_type=pytesseract.Output.DICT,
            )

            text_parts = []
            confidences = []

            for i, conf in enumerate(data["conf"]):
                if conf != -1:
                    text = data["text"][i].strip()
                    if text:
                        text_parts.append(text)
                        confidences.append(conf)

            full_text = pytesseract.image_to_string(
                image,
                lang=self._languages,
                config=self._config,
            )

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            detected_lang = self._detect_language(image)

            return OCRResult(
                text=full_text.strip(),
                confidence=avg_confidence / 100.0,
                language=detected_lang,
            )

        except Exception as e:
            raise OCRExtractionError(
                message="Tesseract OCR extraction failed",
                details={"error": str(e)},
            )

    def _detect_language(self, image: Image.Image) -> str | None:
        """Attempt to detect the language of the document."""
        try:
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
            script = osd.get("script", "")
            if script == "Latin":
                return "en"
            return script.lower() if script else None
        except Exception:
            return None
