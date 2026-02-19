import pytest
from datetime import datetime

from app.domain.models import (
    ServiceProvider,
    LineItem,
    VATDetail,
    TransactionDetails,
    ReceiptData,
    ReceiptResponse,
    ProcessingMetadata,
)
from app.domain.exceptions import (
    ReceiptProcessingError,
    PDFProcessingError,
    OCRExtractionError,
    LLMParsingError,
    UnsupportedFileTypeError,
)


class TestServiceProvider:
    def test_create_with_required_fields(self):
        provider = ServiceProvider(name="Test Shop")
        assert provider.name == "Test Shop"
        assert provider.address is None
        assert provider.vat_number is None
        assert provider.country is None

    def test_vat_number_normalization(self):
        provider = ServiceProvider(name="Test", vat_number="de 123 456 789")
        assert provider.vat_number == "DE123456789"

    def test_vat_number_none_stays_none(self):
        provider = ServiceProvider(name="Test", vat_number=None)
        assert provider.vat_number is None

    def test_create_with_all_fields(self):
        provider = ServiceProvider(
            name="Test Shop",
            address="123 Main St, City",
            vat_number="DE123456789",
            country="DE",
            phone="+49123456",
            email="test@shop.com",
        )
        assert provider.name == "Test Shop"
        assert provider.address == "123 Main St, City"
        assert provider.country == "DE"

    def test_alias_serialization(self):
        provider = ServiceProvider(name="Shop", vat_number="DE123")
        data = provider.model_dump(by_alias=True)
        assert data["Name"] == "Shop"
        assert data["VATNumber"] == "DE123"


class TestLineItem:
    def test_create_with_required_fields(self):
        item = LineItem(name="Coffee", price=5.99)
        assert item.name == "Coffee"
        assert item.quantity == 1.0
        assert item.price == 5.99

    def test_create_with_all_fields(self):
        item = LineItem(
            name="Coffee",
            quantity=2,
            price=5.98,
            vat_rate=19.0,
        )
        assert item.quantity == 2
        assert item.vat_rate == 19.0

    def test_negative_price_rejected(self):
        with pytest.raises(ValueError):
            LineItem(name="Item", price=-10)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValueError):
            LineItem(name="Item", quantity=-1, price=10)

    def test_alias_serialization(self):
        item = LineItem(name="Coffee", quantity=2, price=5.99)
        data = item.model_dump(by_alias=True)
        assert data["Item"] == "Coffee"
        assert data["Quantity"] == 2
        assert data["Price"] == 5.99


class TestVATDetail:
    def test_create_vat_detail(self):
        vat = VATDetail(
            rate=19.0,
            net_amount=100.0,
            vat_amount=19.0,
            gross_amount=119.0,
        )
        assert vat.rate == 19.0
        assert vat.net_amount == 100.0
        assert vat.gross_amount == 119.0

    def test_zero_rate_allowed(self):
        vat = VATDetail(rate=0.0, net_amount=100.0, vat_amount=0.0, gross_amount=100.0)
        assert vat.rate == 0.0


class TestTransactionDetails:
    def test_create_minimal_transaction(self):
        tx = TransactionDetails(total_amount=10.0)
        assert tx.total_amount == 10.0
        assert tx.currency == "EUR"
        assert tx.items == []
        assert tx.vat is None

    def test_create_full_transaction(self):
        tx = TransactionDetails(
            items=[LineItem(name="Item", price=10)],
            currency="USD",
            total_amount=10.0,
            vat="19%",
            payment_method="Card",
            transaction_date=datetime(2024, 1, 15),
            invoice_number="INV-001",
        )
        assert len(tx.items) == 1
        assert tx.currency == "USD"
        assert tx.vat == "19%"
        assert tx.invoice_number == "INV-001"

    def test_currency_normalization(self):
        tx = TransactionDetails(currency="eur", total_amount=10.0)
        assert tx.currency == "EUR"

    def test_alias_serialization(self):
        tx = TransactionDetails(
            items=[LineItem(name="Product", price=9.99)],
            currency="USD",
            total_amount=9.99,
            vat="5%",
        )
        data = tx.model_dump(by_alias=True)
        assert data["Currency"] == "USD"
        assert data["TotalAmount"] == 9.99
        assert data["VAT"] == "5%"
        assert len(data["Items"]) == 1


class TestReceiptResponse:
    def test_create_receipt_response(self):
        response = ReceiptResponse(
            service_provider=ServiceProvider(name="Shop XYZ", vat_number="VAT123456"),
            transaction_details=TransactionDetails(
                items=[LineItem(name="Product 1", quantity=2, price=9.99)],
                currency="USD",
                total_amount=39.97,
                vat="5%",
            ),
        )
        assert response.service_provider.name == "Shop XYZ"
        assert response.transaction_details.total_amount == 39.97

    def test_alias_serialization_matches_spec(self):
        response = ReceiptResponse(
            service_provider=ServiceProvider(
                name="Shop XYZ",
                address="123 Main Street, City, State, ZIP",
                vat_number="VAT123456",
            ),
            transaction_details=TransactionDetails(
                items=[
                    LineItem(name="Product 1", quantity=2, price=9.99),
                    LineItem(name="Product 2", quantity=1, price=19.99),
                ],
                currency="USD",
                total_amount=39.97,
                vat="5%",
            ),
        )
        data = response.model_dump(by_alias=True)

        assert "ServiceProvider" in data
        assert data["ServiceProvider"]["Name"] == "Shop XYZ"
        assert data["ServiceProvider"]["VATNumber"] == "VAT123456"

        assert "TransactionDetails" in data
        assert data["TransactionDetails"]["Currency"] == "USD"
        assert data["TransactionDetails"]["TotalAmount"] == 39.97
        assert data["TransactionDetails"]["VAT"] == "5%"
        assert len(data["TransactionDetails"]["Items"]) == 2


class TestReceiptData:
    def test_create_receipt_data(self):
        receipt = ReceiptData(
            service_provider=ServiceProvider(name="Shop"),
            transaction=TransactionDetails(total_amount=100.0),
            metadata=ProcessingMetadata(
                ocr_engine="tesseract",
                llm_model="llama3.2",
                processing_time_ms=1000,
            ),
        )
        assert receipt.service_provider.name == "Shop"
        assert receipt.transaction.total_amount == 100.0
        assert receipt.metadata.ocr_engine == "tesseract"

    def test_to_response_conversion(self):
        receipt = ReceiptData(
            service_provider=ServiceProvider(name="Shop", vat_number="DE123"),
            transaction=TransactionDetails(
                items=[LineItem(name="Item", price=50)],
                total_amount=50.0,
                vat="19%",
            ),
            metadata=ProcessingMetadata(
                ocr_engine="tesseract",
                llm_model="llama3.2",
                processing_time_ms=1000,
            ),
        )
        response = receipt.to_response()
        assert isinstance(response, ReceiptResponse)
        assert response.service_provider.name == "Shop"
        assert response.transaction_details.total_amount == 50.0


class TestProcessingMetadata:
    def test_create_minimal_metadata(self):
        meta = ProcessingMetadata(
            ocr_engine="tesseract",
            llm_model="llama3.2",
            processing_time_ms=1000,
        )
        assert meta.ocr_engine == "tesseract"
        assert meta.page_count == 1

    def test_negative_processing_time_rejected(self):
        with pytest.raises(ValueError):
            ProcessingMetadata(
                ocr_engine="tesseract",
                llm_model="llama3.2",
                processing_time_ms=-100,
            )


class TestExceptions:
    def test_receipt_processing_error(self):
        error = ReceiptProcessingError("Test error", {"key": "value"})
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_pdf_processing_error_inheritance(self):
        error = PDFProcessingError("PDF error")
        assert isinstance(error, ReceiptProcessingError)

    def test_ocr_extraction_error_inheritance(self):
        error = OCRExtractionError("OCR error")
        assert isinstance(error, ReceiptProcessingError)

    def test_llm_parsing_error_inheritance(self):
        error = LLMParsingError("LLM error")
        assert isinstance(error, ReceiptProcessingError)

    def test_unsupported_file_type_error_inheritance(self):
        error = UnsupportedFileTypeError("File type error")
        assert isinstance(error, ReceiptProcessingError)
