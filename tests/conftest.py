import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.domain.models import (
    ReceiptData,
    ServiceProvider,
    TransactionDetails,
    ProcessingMetadata,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf_bytes():
    """Generate minimal valid PDF bytes for testing."""
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""


@pytest.fixture
def mock_receipt_data():
    """Create mock receipt data for testing."""
    return ReceiptData(
        service_provider=ServiceProvider(
            name="Test Shop",
            address="123 Test St",
            vat_number="DE123456789",
            country="DE",
        ),
        transaction=TransactionDetails(
            items=[],
            currency="EUR",
            total_amount=100.0,
        ),
        metadata=ProcessingMetadata(
            ocr_engine="tesseract",
            llm_model="llama3.2",
            processing_time_ms=1000,
        ),
    )


@pytest.fixture
def mock_ocr_engine():
    """Create a mock OCR engine."""
    from app.infrastructure.ocr.base import OCRResult

    engine = MagicMock()
    engine.name = "mock_ocr"
    engine.extract_text.return_value = OCRResult(
        text="Mock OCR text",
        confidence=0.95,
        language="en",
    )
    engine.extract_text_batch.return_value = [
        OCRResult(text="Mock OCR text", confidence=0.95, language="en")
    ]
    engine.combine_results.return_value = OCRResult(
        text="Mock OCR text",
        confidence=0.95,
        language="en",
    )
    return engine


@pytest.fixture
def mock_llm_extractor():
    """Create a mock LLM extractor."""
    from app.infrastructure.llm.base import ExtractionResult

    extractor = MagicMock()
    extractor.name = "mock_llm"
    extractor.supports_vision = False
    extractor.extract_from_text = AsyncMock(return_value=ExtractionResult(
        raw_response='{}',
        parsed_data={
            "service_provider": {"name": "Test Shop"},
            "transaction": {"total_amount": 100, "currency": "EUR"},
        },
        model="mock_llm",
        tokens_used=100,
    ))
    return extractor


@pytest.fixture
def mock_pdf_processor():
    """Create a mock PDF processor."""
    from PIL import Image
    import numpy as np

    processor = MagicMock()
    processor.process.return_value = (
        [Image.fromarray(np.zeros((100, 100), dtype=np.uint8))],
        None,
    )
    processor.get_page_count.return_value = 1
    return processor
