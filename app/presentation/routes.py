from typing import Annotated
from enum import Enum
from pathlib import Path
import json

from fastapi import APIRouter, File, UploadFile, Query, Depends, HTTPException
from pydantic import BaseModel

from app.domain.models import ReceiptData, ReceiptResponse
from app.application.services import ReceiptProcessingService
from app.presentation.dependencies import get_receipt_service, get_provider_repository


router = APIRouter(tags=["Receipts"])


@router.post(
    "/receipts/process",
    response_model=ReceiptResponse,
    response_model_by_alias=True,
    summary="Process a PDF receipt",
    description="Upload a PDF receipt and extract structured information including service provider details and transaction data.",
    responses={
        200: {
            "description": "Successfully extracted receipt data",
            "content": {
                "application/json": {
                    "example": {
                        "ServiceProvider": {
                            "Name": "MADISON Hotel GmbH",
                            "Address": "Schaarsteinweg 4, 20459 Hamburg",
                            "VATNumber": "DE118696407"
                        },
                        "TransactionDetails": {
                            "Items": [
                                {"Item": "Accommodation", "Quantity": 5, "Price": 550.0}
                            ],
                            "Currency": "EUR",
                            "TotalAmount": 568.0,
                            "VAT": "7% + 19%"
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid file type or format"},
        422: {"description": "Processing error"}
    }
)
async def process_receipt(
    file: Annotated[UploadFile, File(description="PDF receipt file to process")],
    service: ReceiptProcessingService = Depends(get_receipt_service),
) -> ReceiptResponse:
    """Process an uploaded PDF receipt and extract structured data."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()

    result = await service.process_receipt(
        file_content=content,
        filename=file.filename,
        content_type=file.content_type,
    )

    return result.to_response()


@router.post(
    "/receipts/process/detailed",
    response_model=ReceiptData,
    summary="Process a PDF receipt with full details",
    description="Upload a PDF receipt and get detailed extraction results including metadata.",
)
async def process_receipt_detailed(
    file: Annotated[UploadFile, File(description="PDF receipt file to process")],
    include_raw_text: Annotated[bool, Query(description="Include raw OCR text in response")] = False,
    service: ReceiptProcessingService = Depends(get_receipt_service),
) -> ReceiptData:
    """Process receipt with full metadata."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()

    result = await service.process_receipt(
        file_content=content,
        filename=file.filename,
        content_type=file.content_type,
    )

    if not include_raw_text:
        result.raw_text = None

    return result


@router.post(
    "/receipts/process/batch",
    response_model=list[ReceiptResponse],
    response_model_by_alias=True,
    summary="Process multiple PDF receipts",
    description="Upload multiple PDF receipts and extract structured information from each.",
)
async def process_receipts_batch(
    files: Annotated[list[UploadFile], File(description="PDF receipt files to process")],
    service: ReceiptProcessingService = Depends(get_receipt_service),
) -> list[ReceiptResponse]:
    """Process multiple uploaded PDF receipts."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch")

    results = []
    errors = []

    for file in files:
        if not file.filename:
            continue

        try:
            content = await file.read()
            result = await service.process_receipt(
                file_content=content,
                filename=file.filename,
                content_type=file.content_type,
            )
            results.append(result.to_response())
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    if errors and not results:
        raise HTTPException(status_code=422, detail={"message": "All files failed", "errors": errors})

    return results


class EvaluationRequest(BaseModel):
    """Request for running evaluation."""

    ground_truth_path: str = "evaluation/ground_truth.json"
    output_dir: str = "evaluation/results"


class EvaluationResult(BaseModel):
    """Result of evaluation run."""

    total_receipts: int
    successful: int
    failed: int
    average_accuracy: float
    average_processing_time_ms: float
    results: list[dict]


@router.post(
    "/evaluate/run",
    response_model=EvaluationResult,
    summary="Run evaluation on labeled dataset",
    description="Run extraction evaluation against the ground truth labeled dataset.",
)
async def run_evaluation(
    request: EvaluationRequest,
    service: ReceiptProcessingService = Depends(get_receipt_service),
) -> EvaluationResult:
    """Run evaluation on the labeled dataset."""
    gt_path = Path(request.ground_truth_path)
    if not gt_path.exists():
        raise HTTPException(status_code=404, detail=f"Ground truth file not found: {gt_path}")

    with open(gt_path) as f:
        ground_truth = json.load(f)

    results = []
    successful = 0
    total_accuracy = 0.0
    total_time = 0

    for receipt_info in ground_truth.get("receipts", []):
        file_path = Path(receipt_info.get("file_path", ""))

        if not file_path.exists():
            results.append({
                "file_path": str(file_path),
                "status": "skipped",
                "reason": "File not found"
            })
            continue

        try:
            pdf_bytes = file_path.read_bytes()
            extracted = await service.process_receipt(
                file_content=pdf_bytes,
                filename=file_path.name,
            )

            gt = receipt_info.get("ground_truth", {})
            accuracy = _calculate_accuracy(gt, extracted)

            results.append({
                "file_path": str(file_path),
                "status": "success",
                "accuracy": accuracy,
                "processing_time_ms": extracted.metadata.processing_time_ms,
                "extracted": {
                    "provider_name": extracted.service_provider.name,
                    "total_amount": extracted.transaction.total_amount,
                    "currency": extracted.transaction.currency,
                }
            })

            successful += 1
            total_accuracy += accuracy
            total_time += extracted.metadata.processing_time_ms

        except Exception as e:
            results.append({
                "file_path": str(file_path),
                "status": "failed",
                "error": str(e)
            })

    return EvaluationResult(
        total_receipts=len(ground_truth.get("receipts", [])),
        successful=successful,
        failed=len(ground_truth.get("receipts", [])) - successful,
        average_accuracy=total_accuracy / successful if successful > 0 else 0.0,
        average_processing_time_ms=total_time / successful if successful > 0 else 0.0,
        results=results,
    )


def _calculate_accuracy(ground_truth: dict, extracted: ReceiptData) -> float:
    """Calculate accuracy score between ground truth and extracted data."""
    score = 0.0
    total_fields = 0

    gt_provider = ground_truth.get("service_provider", {})
    if gt_provider.get("name"):
        total_fields += 1
        if gt_provider["name"].lower() in extracted.service_provider.name.lower():
            score += 1.0
        elif extracted.service_provider.name.lower() in gt_provider["name"].lower():
            score += 0.8

    if gt_provider.get("vat_number"):
        total_fields += 1
        gt_vat = gt_provider["vat_number"].replace(" ", "").upper()
        ext_vat = (extracted.service_provider.vat_number or "").replace(" ", "").upper()
        if gt_vat == ext_vat:
            score += 1.0

    if gt_provider.get("country"):
        total_fields += 1
        if gt_provider["country"].upper() == (extracted.service_provider.country or "").upper():
            score += 1.0

    gt_tx = ground_truth.get("transaction", {})
    if gt_tx.get("currency"):
        total_fields += 1
        if gt_tx["currency"].upper() == extracted.transaction.currency.upper():
            score += 1.0

    if gt_tx.get("total_amount") and gt_tx["total_amount"] > 0:
        total_fields += 1
        if abs(gt_tx["total_amount"] - extracted.transaction.total_amount) < 0.01:
            score += 1.0
        elif abs(gt_tx["total_amount"] - extracted.transaction.total_amount) < 1.0:
            score += 0.5

    return score / total_fields if total_fields > 0 else 0.0


class ProviderStats(BaseModel):
    """Provider database statistics."""

    total_providers: int
    by_country: dict[str, int]


@router.get(
    "/providers/stats",
    response_model=ProviderStats,
    summary="Get provider database statistics",
)
async def get_provider_stats(
    repository=Depends(get_provider_repository),
) -> ProviderStats:
    """Get statistics about the provider database."""
    if repository is None:
        raise HTTPException(status_code=503, detail="Provider database not enabled")

    providers = repository.get_all()
    by_country: dict[str, int] = {}

    for p in providers:
        country = p.country or "unknown"
        by_country[country] = by_country.get(country, 0) + 1

    return ProviderStats(
        total_providers=len(providers),
        by_country=by_country,
    )
