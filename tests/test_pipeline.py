from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from PIL import Image

from app.application.pipeline import (
    ExtractionPipeline,
    PipelineConfig,
    PipelineStrategy,
)
from app.domain.models import ServiceProvider
from app.infrastructure.llm.base import ExtractionResult
from app.infrastructure.ocr.base import OCRResult


@pytest.fixture
def mock_pdf_processor():
    processor = MagicMock()
    processor.process.return_value = ([Image.fromarray(np.zeros((100, 100), dtype=np.uint8))], None)
    return processor


@pytest.fixture
def mock_ocr_engine():
    engine = MagicMock()
    engine.name = "test_ocr"
    engine.extract_text_batch.return_value = [
        OCRResult(text="Test receipt text", confidence=0.9, language="en")
    ]
    engine.combine_results.return_value = OCRResult(
        text="Test receipt text", confidence=0.9, language="en"
    )
    return engine


@pytest.fixture
def mock_llm_extractor():
    extractor = MagicMock()
    extractor.name = "test_llm"
    extractor.supports_vision = False
    extractor.extract_from_text = AsyncMock(
        return_value=ExtractionResult(
            raw_response='{"service_provider": {"name": "Test Shop"}, "transaction": {"total_amount": 100}}',
            parsed_data={
                "service_provider": {
                    "name": "Test Shop",
                    "address": "123 Test St",
                    "vat_number": "DE123456789",
                    "country": "DE",
                },
                "transaction": {
                    "items": [{"name": "Item 1", "quantity": 1, "total_price": 100}],
                    "currency": "EUR",
                    "total_amount": 100.0,
                    "vat_details": [],
                    "payment_method": "Card",
                    "transaction_date": "2024-01-15",
                    "invoice_number": "INV-001",
                },
            },
            model="test_llm",
            tokens_used=100,
        )
    )
    return extractor


class TestPipelineConfig:
    def test_default_config(self):
        config = PipelineConfig()
        assert config.strategy == PipelineStrategy.OCR_LLM
        assert config.use_preprocessing is True
        assert config.include_raw_text is False

    def test_custom_config(self):
        config = PipelineConfig(
            strategy=PipelineStrategy.HYBRID,
            include_raw_text=True,
        )
        assert config.strategy == PipelineStrategy.HYBRID
        assert config.include_raw_text is True


class TestExtractionPipeline:
    @pytest.mark.asyncio
    async def test_process_ocr_llm_strategy(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
            config=PipelineConfig(strategy=PipelineStrategy.OCR_LLM),
        )

        result = await pipeline.process(b"%PDF-1.4 test")

        assert result.service_provider.name == "Test Shop"
        assert result.transaction.total_amount == 100.0
        assert result.metadata.ocr_engine == "test_ocr"
        assert result.metadata.llm_model == "test_llm"

    @pytest.mark.asyncio
    async def test_process_hybrid_with_native_text(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        mock_pdf_processor.process.return_value = (
            [Image.fromarray(np.zeros((100, 100), dtype=np.uint8))],
            "Native PDF text content that is long enough",
        )

        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
            config=PipelineConfig(strategy=PipelineStrategy.HYBRID),
        )

        await pipeline.process(b"%PDF-1.4 test")

        mock_llm_extractor.extract_from_text.assert_called_once()
        assert "Native PDF text" in mock_llm_extractor.extract_from_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_process_includes_raw_text(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
            config=PipelineConfig(include_raw_text=True),
        )

        result = await pipeline.process(b"%PDF-1.4 test")

        assert result.raw_text == "Test receipt text"

    @pytest.mark.asyncio
    async def test_process_multipage_pdf(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        mock_pdf_processor.process.return_value = (
            [
                Image.fromarray(np.zeros((100, 100), dtype=np.uint8)),
                Image.fromarray(np.zeros((100, 100), dtype=np.uint8)),
            ],
            None,
        )

        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
        )

        result = await pipeline.process(b"%PDF-1.4 test")

        assert result.metadata.page_count == 2

    @pytest.mark.asyncio
    async def test_process_with_provider_service(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        mock_provider_service = MagicMock()
        mock_provider_service.enrich_provider.return_value = ServiceProvider(
            name="Enriched Shop",
            vat_number="DE999999999",
            country="DE",
        )
        mock_provider_service.learn_provider.return_value = None

        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
            config=PipelineConfig(enable_provider_enrichment=True),
            provider_service=mock_provider_service,
        )

        result = await pipeline.process(b"%PDF-1.4 test")

        assert result.service_provider.name == "Enriched Shop"
        mock_provider_service.learn_provider.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_calculates_confidence(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
        )

        result = await pipeline.process(b"%PDF-1.4 test")

        assert result.metadata.ocr_confidence == 0.9
        assert result.metadata.extraction_confidence is not None
        assert result.metadata.extraction_confidence > 0


class TestPipelineVisionStrategy:
    @pytest.mark.asyncio
    async def test_vision_strategy_single_page(self, mock_pdf_processor, mock_ocr_engine):
        mock_llm = MagicMock()
        mock_llm.name = "vision_llm"
        mock_llm.supports_vision = True
        mock_llm.extract_from_image = AsyncMock(
            return_value=ExtractionResult(
                raw_response="{}",
                parsed_data={
                    "service_provider": {"name": "Vision Shop"},
                    "transaction": {"total_amount": 50},
                },
                model="vision_llm",
            )
        )

        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm,
            config=PipelineConfig(strategy=PipelineStrategy.VISION_LLM),
        )

        result = await pipeline.process(b"%PDF-1.4 test")

        assert result.service_provider.name == "Vision Shop"
        mock_llm.extract_from_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_vision_fallback_to_ocr(
        self, mock_pdf_processor, mock_ocr_engine, mock_llm_extractor
    ):
        mock_llm_extractor.supports_vision = False

        pipeline = ExtractionPipeline(
            pdf_processor=mock_pdf_processor,
            ocr_engine=mock_ocr_engine,
            llm_extractor=mock_llm_extractor,
            config=PipelineConfig(strategy=PipelineStrategy.VISION_LLM),
        )

        await pipeline.process(b"%PDF-1.4 test")

        mock_ocr_engine.extract_text_batch.assert_called_once()
        mock_llm_extractor.extract_from_text.assert_called_once()
