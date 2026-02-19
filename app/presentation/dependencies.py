from functools import lru_cache
from typing import Optional

from app.config import settings
from app.infrastructure.pdf.processor import PDFProcessor
from app.infrastructure.ocr.factory import OCREngineFactory
from app.infrastructure.llm.factory import LLMExtractorFactory
from app.infrastructure.database.repository import ProviderRepository
from app.infrastructure.database.service import ProviderMatchingService
from app.application.pipeline import ExtractionPipeline, PipelineConfig
from app.application.services import ReceiptProcessingService


@lru_cache()
def get_pdf_processor() -> PDFProcessor:
    """Get or create PDF processor instance."""
    return PDFProcessor(dpi=300, grayscale=True)


@lru_cache()
def get_ocr_engine():
    """Get or create OCR engine instance."""
    engine_name = settings.ocr_engine

    if engine_name == "tesseract":
        return OCREngineFactory.create(
            engine_name,
            languages=settings.tesseract_languages,
        )
    elif engine_name == "easyocr":
        languages = settings.tesseract_languages.split("+")
        lang_map = {"eng": "en", "deu": "de", "fra": "fr"}
        mapped_langs = [lang_map.get(l, l) for l in languages]
        return OCREngineFactory.create(
            engine_name,
            languages=mapped_langs,
            gpu=False,
        )

    return OCREngineFactory.create(engine_name)


def get_llm_extractor():
    """Get or create LLM extractor instance."""
    if settings.use_openai:
        return LLMExtractorFactory.create_openai(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    return LLMExtractorFactory.create_ollama(
        model=settings.ollama_model,
        host=settings.ollama_host,
    )


@lru_cache()
def get_provider_repository() -> Optional[ProviderRepository]:
    """Get provider repository if enabled."""
    if not settings.enable_provider_database:
        return None
    return ProviderRepository(settings.database_url)


@lru_cache()
def get_provider_service() -> Optional[ProviderMatchingService]:
    """Get provider matching service if enabled."""
    repo = get_provider_repository()
    if repo is None:
        return None
    return ProviderMatchingService(repo)


def get_pipeline() -> ExtractionPipeline:
    """Get or create extraction pipeline."""
    config = PipelineConfig(
        use_preprocessing=True,
        include_raw_text=False,
        enable_provider_enrichment=settings.enable_provider_database,
    )

    return ExtractionPipeline(
        pdf_processor=get_pdf_processor(),
        ocr_engine=get_ocr_engine(),
        llm_extractor=get_llm_extractor(),
        config=config,
        provider_service=get_provider_service(),
    )


def get_receipt_service() -> ReceiptProcessingService:
    """Get receipt processing service."""
    return ReceiptProcessingService(pipeline=get_pipeline())
