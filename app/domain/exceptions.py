class ReceiptProcessingError(Exception):
    """Base exception for receipt processing errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PDFProcessingError(ReceiptProcessingError):
    """Error during PDF reading or conversion."""

    pass


class OCRExtractionError(ReceiptProcessingError):
    """Error during OCR text extraction."""

    pass


class LLMParsingError(ReceiptProcessingError):
    """Error during LLM-based information extraction."""

    pass


class UnsupportedFileTypeError(ReceiptProcessingError):
    """Uploaded file type is not supported."""

    pass
