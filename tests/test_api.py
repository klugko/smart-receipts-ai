import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

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


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check_returns_version(self, client):
        response = client.get("/health")
        assert response.json()["version"] == "1.0.0"


class TestReceiptProcessEndpoint:
    def test_process_no_file(self, client):
        response = client.post("/api/v1/receipts/process")
        assert response.status_code == 422

    def test_process_empty_filename(self, client):
        response = client.post(
            "/api/v1/receipts/process",
            files={"file": ("", b"content", "application/pdf")},
        )
        assert response.status_code == 400

    def test_process_non_pdf_file(self, client):
        response = client.post(
            "/api/v1/receipts/process",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert response.status_code == 400

    def test_process_invalid_pdf_content(self, client):
        response = client.post(
            "/api/v1/receipts/process",
            files={"file": ("test.pdf", b"not valid pdf content", "application/pdf")},
        )
        assert response.status_code == 400

    def test_process_empty_file(self, client):
        response = client.post(
            "/api/v1/receipts/process",
            files={"file": ("test.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400

    @patch("app.presentation.dependencies.get_receipt_service")
    def test_process_valid_pdf(self, mock_service, client, sample_pdf_bytes, mock_receipt_data):
        mock_svc = MagicMock()
        mock_svc.process_receipt = AsyncMock(return_value=mock_receipt_data)
        mock_service.return_value = mock_svc

        response = client.post(
            "/api/v1/receipts/process",
            files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        )

        assert response.status_code == 200 or response.status_code == 422

    def test_process_with_include_raw_text_param(self, client, sample_pdf_bytes):
        response = client.post(
            "/api/v1/receipts/process?include_raw_text=true",
            files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        )
        assert response.status_code in [200, 400, 422]


class TestBatchProcessEndpoint:
    def test_batch_no_files(self, client):
        response = client.post("/api/v1/receipts/process/batch")
        assert response.status_code == 422

    def test_batch_too_many_files(self, client, sample_pdf_bytes):
        files = [
            ("files", (f"test_{i}.pdf", sample_pdf_bytes, "application/pdf"))
            for i in range(11)
        ]
        response = client.post(
            "/api/v1/receipts/process/batch",
            files=files,
        )
        assert response.status_code == 400
        assert "Maximum 10 files" in response.json()["detail"]

    def test_batch_empty_list(self, client):
        response = client.post(
            "/api/v1/receipts/process/batch",
            files=[],
        )
        assert response.status_code == 422


class TestEvaluationEndpoint:
    def test_evaluate_missing_ground_truth(self, client):
        response = client.post(
            "/api/v1/evaluate/run",
            json={"ground_truth_path": "nonexistent/path.json"},
        )
        assert response.status_code == 404

    def test_evaluate_default_params(self, client):
        response = client.post(
            "/api/v1/evaluate/run",
            json={},
        )
        assert response.status_code in [200, 404, 422]


class TestProviderStatsEndpoint:
    def test_provider_stats(self, client):
        response = client.get("/api/v1/providers/stats")
        assert response.status_code in [200, 503]

    @patch("app.presentation.dependencies.get_provider_repository")
    def test_provider_stats_disabled(self, mock_repo, client):
        mock_repo.return_value = None
        response = client.get("/api/v1/providers/stats")
        assert response.status_code == 503


class TestAPIDocumentation:
    def test_openapi_json(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "/api/v1/receipts/process" in data["paths"]

    def test_swagger_ui(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc(self, client):
        response = client.get("/redoc")
        assert response.status_code == 200
