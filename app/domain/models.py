from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceProvider(BaseModel):
    """Service provider information extracted from receipt."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., alias="Name", description="Name of the service provider")
    address: str | None = Field(None, alias="Address", description="Complete address")
    vat_number: str | None = Field(None, alias="VATNumber", description="VAT registration number")
    country: str | None = Field(None, description="Country code (ISO 3166-1 alpha-2)")
    phone: str | None = Field(None, description="Contact phone number")
    email: str | None = Field(None, description="Contact email address")

    @field_validator("vat_number", mode="before")
    @classmethod
    def normalize_vat(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.replace(" ", "").upper()


class LineItem(BaseModel):
    """Individual item from the receipt."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., alias="Item", description="Item description")
    quantity: float = Field(1.0, alias="Quantity", ge=0, description="Quantity purchased")
    price: float = Field(..., alias="Price", ge=0, description="Price for this item")
    vat_rate: float | None = Field(None, description="VAT rate percentage")


class VATDetail(BaseModel):
    """VAT breakdown for a specific rate."""

    rate: float = Field(..., ge=0, le=100, description="VAT rate percentage")
    net_amount: float = Field(..., ge=0, description="Net amount before VAT")
    vat_amount: float = Field(..., ge=0, description="VAT amount")
    gross_amount: float = Field(..., ge=0, description="Gross amount including VAT")


class TransactionDetails(BaseModel):
    """Complete transaction information."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[LineItem] = Field(
        default_factory=list, alias="Items", description="List of purchased items"
    )
    currency: str = Field(
        "EUR", alias="Currency", min_length=3, max_length=3, description="ISO 4217 currency code"
    )
    total_amount: float = Field(..., alias="TotalAmount", ge=0, description="Total charged amount")
    vat: str | None = Field(None, alias="VAT", description="VAT information")
    vat_details: list[VATDetail] = Field(default_factory=list, description="VAT breakdown by rate")
    payment_method: str | None = Field(None, description="Payment method used")
    transaction_date: datetime | None = Field(None, description="Date of transaction")
    invoice_number: str | None = Field(None, description="Invoice or receipt number")

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.upper().strip()


class ProcessingMetadata(BaseModel):
    """Metadata about the extraction process."""

    ocr_engine: str = Field(..., description="OCR engine used")
    llm_model: str = Field(..., description="LLM model used for extraction")
    processing_time_ms: int = Field(..., ge=0, description="Total processing time in milliseconds")
    ocr_confidence: float | None = Field(None, ge=0, le=1, description="OCR confidence score")
    extraction_confidence: float | None = Field(
        None, ge=0, le=1, description="Overall extraction confidence"
    )
    page_count: int = Field(1, ge=1, description="Number of pages processed")
    language_detected: str | None = Field(None, description="Detected language code")


class ReceiptResponse(BaseModel):
    """Response format matching the challenge specification."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "ServiceProvider": {
                    "Name": "Shop XYZ",
                    "Address": "123 Main Street, City, State, ZIP",
                    "VATNumber": "VAT123456",
                },
                "TransactionDetails": {
                    "Items": [
                        {"Item": "Product 1", "Quantity": 2, "Price": 9.99},
                        {"Item": "Product 2", "Quantity": 1, "Price": 19.99},
                    ],
                    "Currency": "USD",
                    "TotalAmount": 39.97,
                    "VAT": "5%",
                },
            }
        },
    )

    service_provider: ServiceProvider = Field(..., alias="ServiceProvider")
    transaction_details: TransactionDetails = Field(..., alias="TransactionDetails")


class ReceiptData(BaseModel):
    """Complete extracted receipt data with metadata."""

    service_provider: ServiceProvider
    transaction: TransactionDetails
    raw_text: str | None = Field(None, description="Raw OCR text output")
    metadata: ProcessingMetadata

    def to_response(self) -> ReceiptResponse:
        """Convert to the challenge-specified response format."""
        return ReceiptResponse(
            service_provider=self.service_provider,
            transaction_details=self.transaction,
        )
