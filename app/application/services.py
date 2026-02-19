import structlog

from app.application.pipeline import ExtractionPipeline
from app.domain.exceptions import ReceiptProcessingError, UnsupportedFileTypeError
from app.domain.models import ReceiptData

logger = structlog.get_logger(__name__)


class ReceiptProcessingService:
    """Application service for processing receipt files."""

    ALLOWED_CONTENT_TYPES = {
        "application/pdf",
        "application/x-pdf",
    }
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

    def __init__(self, pipeline: ExtractionPipeline):
        self._pipeline = pipeline

    async def process_receipt(
        self,
        file_content: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> ReceiptData:
        """
        Process an uploaded receipt file.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            content_type: MIME type of the file

        Returns:
            Extracted receipt data

        Raises:
            UnsupportedFileTypeError: If file type is not supported
            ReceiptProcessingError: If processing fails
        """
        self._validate_file(file_content, filename, content_type)

        logger.info(
            "processing_receipt",
            filename=filename,
            size_bytes=len(file_content),
        )

        try:
            result = await self._pipeline.process(file_content)

            logger.info(
                "receipt_processed",
                filename=filename,
                provider=result.service_provider.name,
                total=result.transaction.total_amount,
                currency=result.transaction.currency,
                processing_time_ms=result.metadata.processing_time_ms,
            )

            return result

        except ReceiptProcessingError:
            raise
        except Exception as e:
            logger.error(
                "receipt_processing_failed",
                filename=filename,
                error=str(e),
            )
            raise ReceiptProcessingError(
                message="Failed to process receipt",
                details={"filename": filename, "error": str(e)},
            ) from e

    def _validate_file(
        self,
        content: bytes,
        filename: str,
        content_type: str | None,
    ) -> None:
        """Validate uploaded file."""
        if len(content) > self.MAX_FILE_SIZE_BYTES:
            raise UnsupportedFileTypeError(
                message=f"File exceeds maximum size of {self.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
                details={"size": len(content), "max_size": self.MAX_FILE_SIZE_BYTES},
            )

        if not filename.lower().endswith(".pdf"):
            raise UnsupportedFileTypeError(
                message="Only PDF files are supported",
                details={"filename": filename},
            )

        if content[:4] != b"%PDF":
            raise UnsupportedFileTypeError(
                message="Invalid PDF file format",
                details={"filename": filename},
            )
