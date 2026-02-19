import importlib.util
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.domain.exceptions import OCRExtractionError
from app.infrastructure.llm.base import ExtractionResult
from app.infrastructure.llm.factory import LLMExtractorFactory
from app.infrastructure.ocr.base import OCREngine, OCRResult
from app.infrastructure.ocr.factory import OCREngineFactory
from app.infrastructure.pdf.processor import PDFProcessor


class TestOCRResult:
    def test_create_ocr_result(self):
        result = OCRResult(text="Test text", confidence=0.95)
        assert result.text == "Test text"
        assert result.confidence == 0.95
        assert result.language is None

    def test_create_ocr_result_with_language(self):
        result = OCRResult(text="Test", confidence=0.9, language="de")
        assert result.language == "de"


class TestOCREngineFactory:
    def test_available_engines(self):
        engines = OCREngineFactory.available_engines()
        assert "tesseract" in engines
        # easyocr may or may not be available depending on installation

    def test_create_tesseract(self):
        engine = OCREngineFactory.create("tesseract", languages="eng")
        assert engine.name == "tesseract"

    def test_create_unknown_engine_raises(self):
        with pytest.raises(ValueError) as exc_info:
            OCREngineFactory.create("unknown_engine")
        assert "Unknown OCR engine" in str(exc_info.value)

    def test_create_case_insensitive(self):
        engine = OCREngineFactory.create("TESSERACT", languages="eng")
        assert engine.name == "tesseract"


class TestOCREngineBase:
    def test_combine_results_empty(self):
        class TestEngine(OCREngine):
            @property
            def name(self):
                return "test"

            def extract_text(self, image):
                return OCRResult(text="", confidence=0.0)

        engine = TestEngine()
        result = engine.combine_results([])
        assert result.text == ""
        assert result.confidence == 0.0

    def test_combine_results_single(self):
        class TestEngine(OCREngine):
            @property
            def name(self):
                return "test"

            def extract_text(self, image):
                return OCRResult(text="Single", confidence=0.9)

        engine = TestEngine()
        results = [OCRResult(text="Single", confidence=0.9, language="en")]
        combined = engine.combine_results(results)
        assert combined.text == "Single"
        assert combined.confidence == 0.9
        assert combined.language == "en"

    def test_combine_results_multiple(self):
        class TestEngine(OCREngine):
            @property
            def name(self):
                return "test"

            def extract_text(self, image):
                return OCRResult(text="", confidence=0.0)

        engine = TestEngine()
        results = [
            OCRResult(text="First page", confidence=0.9, language="en"),
            OCRResult(text="Second page", confidence=0.8, language="en"),
        ]
        combined = engine.combine_results(results)
        assert "First page" in combined.text
        assert "Second page" in combined.text
        assert abs(combined.confidence - 0.85) < 0.0001


class TestLLMExtractorFactory:
    def test_create_ollama(self):
        extractor = LLMExtractorFactory.create_ollama(model="llama3.2")
        assert "ollama" in extractor.name

    def test_create_ollama_with_host(self):
        extractor = LLMExtractorFactory.create_ollama(model="llama3.2", host="http://custom:11434")
        assert extractor.name == "ollama/llama3.2"

    def test_create_unknown_provider_raises(self):
        with pytest.raises(ValueError) as exc_info:
            LLMExtractorFactory.create("unknown_provider")
        assert "Unknown LLM provider" in str(exc_info.value)


class TestExtractionResult:
    def test_create_extraction_result(self):
        result = ExtractionResult(
            raw_response='{"test": "data"}',
            parsed_data={"test": "data"},
            model="llama3.2",
        )
        assert result.raw_response == '{"test": "data"}'
        assert result.parsed_data == {"test": "data"}
        assert result.model == "llama3.2"
        assert result.tokens_used is None

    def test_create_with_tokens(self):
        result = ExtractionResult(
            raw_response="{}",
            parsed_data={},
            model="test",
            tokens_used=150,
        )
        assert result.tokens_used == 150


class TestPDFProcessor:
    def test_init_default_settings(self):
        processor = PDFProcessor()
        assert processor._dpi == 300
        assert processor._grayscale is True

    def test_init_custom_settings(self):
        processor = PDFProcessor(dpi=150, grayscale=False)
        assert processor._dpi == 150
        assert processor._grayscale is False

    def test_extract_native_text_empty(self):
        processor = PDFProcessor()
        result = processor.extract_native_text(b"invalid pdf")
        assert result is None

    @patch("app.infrastructure.pdf.processor.pdfplumber")
    def test_extract_native_text_with_text(self, mock_pdfplumber):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 100
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdfplumber.open.return_value = mock_pdf

        processor = PDFProcessor()
        result = processor.extract_native_text(b"%PDF-1.4 content")
        assert result == "A" * 100

    def test_preprocess_image_rgb(self):
        processor = PDFProcessor()
        img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
        result = processor.preprocess_image(img)
        assert isinstance(result, Image.Image)

    def test_preprocess_image_grayscale(self):
        processor = PDFProcessor()
        img = Image.fromarray(np.random.randint(0, 255, (100, 100), dtype=np.uint8))
        result = processor.preprocess_image(img)
        assert isinstance(result, Image.Image)


class TestTesseractOCR:
    @patch("app.infrastructure.ocr.tesseract.pytesseract")
    def test_extract_text_success(self, mock_pytesseract):
        from app.infrastructure.ocr.tesseract import TesseractOCR

        mock_pytesseract.image_to_data.return_value = {
            "conf": [95, 90, -1, 85],
            "text": ["Hello", "World", "", "Test"],
        }
        mock_pytesseract.image_to_string.return_value = "Hello World Test"
        mock_pytesseract.image_to_osd.return_value = {"script": "Latin"}
        mock_pytesseract.Output.DICT = "dict"

        ocr = TesseractOCR(languages="eng")
        img = Image.fromarray(np.zeros((100, 100), dtype=np.uint8))
        result = ocr.extract_text(img)

        assert result.text == "Hello World Test"
        assert result.confidence > 0

    @patch("app.infrastructure.ocr.tesseract.pytesseract")
    def test_extract_text_error(self, mock_pytesseract):
        from app.infrastructure.ocr.tesseract import TesseractOCR

        mock_pytesseract.image_to_data.side_effect = Exception("Tesseract error")

        ocr = TesseractOCR()
        img = Image.fromarray(np.zeros((100, 100), dtype=np.uint8))

        with pytest.raises(OCRExtractionError):
            ocr.extract_text(img)


EASYOCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None


@pytest.mark.skipif(not EASYOCR_AVAILABLE, reason="EasyOCR not installed")
class TestEasyOCR:
    @patch("app.infrastructure.ocr.easyocr_engine.easyocr")
    def test_extract_text_success(self, mock_easyocr):
        from app.infrastructure.ocr.easyocr_engine import EasyOCREngine

        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            ([[0, 0], [10, 0], [10, 10], [0, 10]], "Hello", 0.95),
            ([[20, 0], [30, 0], [30, 10], [20, 10]], "World", 0.90),
        ]
        mock_easyocr.Reader.return_value = mock_reader

        ocr = EasyOCREngine(languages=["en"])
        EasyOCREngine._reader_cache.clear()

        img = Image.fromarray(np.zeros((100, 100), dtype=np.uint8))
        result = ocr.extract_text(img)

        assert "Hello" in result.text
        assert "World" in result.text
        assert result.confidence > 0

    @patch("app.infrastructure.ocr.easyocr_engine.easyocr")
    def test_extract_text_error(self, mock_easyocr):
        from app.infrastructure.ocr.easyocr_engine import EasyOCREngine

        mock_reader = MagicMock()
        mock_reader.readtext.side_effect = Exception("EasyOCR error")
        mock_easyocr.Reader.return_value = mock_reader

        ocr = EasyOCREngine(languages=["en"])
        EasyOCREngine._reader_cache.clear()

        img = Image.fromarray(np.zeros((100, 100), dtype=np.uint8))

        with pytest.raises(OCRExtractionError):
            ocr.extract_text(img)
