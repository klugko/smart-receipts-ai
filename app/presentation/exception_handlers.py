import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    LLMParsingError,
    OCRExtractionError,
    PDFProcessingError,
    ReceiptProcessingError,
    UnsupportedFileTypeError,
)

logger = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers for the application."""

    @app.exception_handler(UnsupportedFileTypeError)
    async def unsupported_file_handler(
        request: Request,
        exc: UnsupportedFileTypeError,
    ) -> JSONResponse:
        logger.warning("unsupported_file_type", message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=400,
            content={
                "error": "unsupported_file_type",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(PDFProcessingError)
    async def pdf_processing_handler(
        request: Request,
        exc: PDFProcessingError,
    ) -> JSONResponse:
        logger.error("pdf_processing_error", message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=422,
            content={
                "error": "pdf_processing_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(OCRExtractionError)
    async def ocr_extraction_handler(
        request: Request,
        exc: OCRExtractionError,
    ) -> JSONResponse:
        logger.error("ocr_extraction_error", message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=422,
            content={
                "error": "ocr_extraction_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(LLMParsingError)
    async def llm_parsing_handler(
        request: Request,
        exc: LLMParsingError,
    ) -> JSONResponse:
        logger.error("llm_parsing_error", message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=422,
            content={
                "error": "llm_parsing_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ReceiptProcessingError)
    async def receipt_processing_handler(
        request: Request,
        exc: ReceiptProcessingError,
    ) -> JSONResponse:
        logger.error("receipt_processing_error", message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=500,
            content={
                "error": "processing_error",
                "message": exc.message,
                "details": exc.details,
            },
        )
