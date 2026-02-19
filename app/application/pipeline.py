from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from app.infrastructure.database.service import ProviderMatchingService

from app.domain.models import (
    LineItem,
    ProcessingMetadata,
    ReceiptData,
    ServiceProvider,
    TransactionDetails,
    VATDetail,
)
from app.infrastructure.llm.base import ExtractionResult, LLMExtractor
from app.infrastructure.ocr.base import OCREngine, OCRResult
from app.infrastructure.pdf.processor import PDFProcessor


class PipelineStrategy(StrEnum):
    OCR_LLM = "ocr_llm"
    VISION_LLM = "vision_llm"
    HYBRID = "hybrid"


@dataclass
class PipelineConfig:
    """Configuration for the extraction pipeline."""

    strategy: PipelineStrategy = PipelineStrategy.OCR_LLM
    use_preprocessing: bool = True
    fallback_to_ocr: bool = True
    include_raw_text: bool = False
    enable_provider_enrichment: bool = True


class ExtractionPipeline:
    """Orchestrates the receipt extraction process."""

    def __init__(
        self,
        pdf_processor: PDFProcessor,
        ocr_engine: OCREngine,
        llm_extractor: LLMExtractor,
        config: PipelineConfig | None = None,
        provider_service: ProviderMatchingService | None = None,
    ):
        self._pdf_processor = pdf_processor
        self._ocr_engine = ocr_engine
        self._llm_extractor = llm_extractor
        self._config = config or PipelineConfig()
        self._provider_service = provider_service

    async def process(self, pdf_bytes: bytes) -> ReceiptData:
        """Process a PDF receipt and extract structured data."""
        start_time = time.perf_counter()

        images, native_text = self._pdf_processor.process(pdf_bytes)
        page_count = len(images)

        ocr_result: OCRResult | None = None
        extraction_result: ExtractionResult

        strategy = self._config.strategy

        if strategy == PipelineStrategy.VISION_LLM and self._llm_extractor.supports_vision:
            extraction_result = await self._vision_extraction(images)
        elif strategy == PipelineStrategy.HYBRID and native_text:
            extraction_result = await self._llm_extractor.extract_from_text(native_text)
        else:
            ocr_result = self._perform_ocr(images)
            extraction_result = await self._llm_extractor.extract_from_text(ocr_result.text)

        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        receipt_data = self._build_receipt_data(
            extraction_result=extraction_result,
            ocr_result=ocr_result,
            native_text=native_text,
            processing_time_ms=processing_time_ms,
            page_count=page_count,
        )

        if self._config.enable_provider_enrichment and self._provider_service:
            receipt_data = self._enrich_with_provider_db(receipt_data)

        return receipt_data

    def _enrich_with_provider_db(self, receipt_data: ReceiptData) -> ReceiptData:
        """Enrich receipt with provider database information."""
        if not self._provider_service:
            return receipt_data

        enriched_provider = self._provider_service.enrich_provider(receipt_data.service_provider)

        self._provider_service.learn_provider(enriched_provider)

        return ReceiptData(
            service_provider=enriched_provider,
            transaction=receipt_data.transaction,
            raw_text=receipt_data.raw_text,
            metadata=receipt_data.metadata,
        )

    async def _vision_extraction(self, images: list[Image.Image]) -> ExtractionResult:
        """Extract data using vision LLM directly on images."""
        if len(images) == 1:
            return await self._llm_extractor.extract_from_image(images[0])

        results = []
        for img in images:
            result = await self._llm_extractor.extract_from_image(img)
            results.append(result)

        return self._merge_extraction_results(results)

    def _perform_ocr(self, images: list[Image.Image]) -> OCRResult:
        """Perform OCR on all images."""
        results = self._ocr_engine.extract_text_batch(images)
        return self._ocr_engine.combine_results(results)

    def _merge_extraction_results(self, results: list[ExtractionResult]) -> ExtractionResult:
        """Merge multiple extraction results."""
        if len(results) == 1:
            return results[0]

        merged_data = results[0].parsed_data.copy()
        for result in results[1:]:
            items = result.parsed_data.get("transaction", {}).get("items", [])
            if items:
                merged_data.setdefault("transaction", {}).setdefault("items", []).extend(items)

        return ExtractionResult(
            raw_response="\n".join(r.raw_response for r in results),
            parsed_data=merged_data,
            model=results[0].model,
            tokens_used=sum(r.tokens_used or 0 for r in results),
        )

    def _build_receipt_data(
        self,
        extraction_result: ExtractionResult,
        ocr_result: OCRResult | None,
        native_text: str | None,
        processing_time_ms: int,
        page_count: int,
    ) -> ReceiptData:
        """Build the final ReceiptData from extracted information."""
        data = extraction_result.parsed_data

        sp_data = data.get("service_provider", {})
        service_provider = ServiceProvider(
            name=sp_data.get("name") or "Unknown",
            address=sp_data.get("address"),
            vat_number=sp_data.get("vat_number"),
            country=sp_data.get("country"),
            phone=sp_data.get("phone"),
            email=sp_data.get("email"),
        )

        tx_data = data.get("transaction", {})

        items = []
        for item_data in tx_data.get("items", []):
            if not item_data:
                continue
            price = item_data.get("price") or item_data.get("total_price") or 0
            items.append(
                LineItem(
                    name=item_data.get("name") or item_data.get("item") or "Unknown Item",
                    quantity=float(item_data.get("quantity") or 1),
                    price=float(price),
                    vat_rate=item_data.get("vat_rate"),
                )
            )

        vat_details = []
        for vat_data in tx_data.get("vat_details", []):
            if not vat_data:
                continue
            vat_details.append(
                VATDetail(
                    rate=float(vat_data.get("rate") or 0),
                    net_amount=float(vat_data.get("net_amount") or 0),
                    vat_amount=float(vat_data.get("vat_amount") or 0),
                    gross_amount=float(vat_data.get("gross_amount") or 0),
                )
            )

        vat_str = None
        if vat_details:
            rates = sorted({v.rate for v in vat_details})
            vat_str = " + ".join(f"{r}%" for r in rates)
        elif tx_data.get("vat"):
            vat_str = str(tx_data.get("vat"))

        transaction_date = None
        date_str = tx_data.get("transaction_date")
        if date_str:
            try:
                if "T" in str(date_str):
                    transaction_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    transaction_date = datetime.strptime(str(date_str), "%Y-%m-%d")
            except (ValueError, AttributeError):
                pass

        transaction = TransactionDetails(
            items=items,
            currency=tx_data.get("currency") or "EUR",
            total_amount=float(tx_data.get("total_amount") or 0),
            vat=vat_str,
            vat_details=vat_details,
            payment_method=tx_data.get("payment_method"),
            transaction_date=transaction_date,
            invoice_number=tx_data.get("invoice_number"),
        )

        raw_text = None
        if self._config.include_raw_text:
            raw_text = ocr_result.text if ocr_result else native_text

        confidence = None
        if ocr_result:
            field_count = sum(
                [
                    1 if service_provider.name != "Unknown" else 0,
                    1 if service_provider.vat_number else 0,
                    1 if transaction.total_amount > 0 else 0,
                    1 if transaction.items else 0,
                ]
            )
            confidence = min(1.0, (ocr_result.confidence + field_count * 0.15))

        metadata = ProcessingMetadata(
            ocr_engine=self._ocr_engine.name,
            llm_model=extraction_result.model,
            processing_time_ms=processing_time_ms,
            ocr_confidence=ocr_result.confidence if ocr_result else None,
            extraction_confidence=confidence,
            page_count=page_count,
            language_detected=ocr_result.language if ocr_result else None,
        )

        return ReceiptData(
            service_provider=service_provider,
            transaction=transaction,
            raw_text=raw_text,
            metadata=metadata,
        )
