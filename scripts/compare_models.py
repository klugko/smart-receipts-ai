#!/usr/bin/env python3
"""
Model comparison script for receipt extraction.

Compares different OCR engines and LLM models on the evaluation dataset.

Usage:
    python scripts/compare_models.py --output evaluation/comparison_results.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.pdf.processor import PDFProcessor
from app.infrastructure.ocr.factory import OCREngineFactory
from app.infrastructure.llm.factory import LLMExtractorFactory
from app.application.pipeline import ExtractionPipeline, PipelineConfig
from evaluation.evaluator import ReceiptEvaluator


@dataclass
class ModelConfig:
    """Configuration for a model comparison run."""

    name: str
    ocr_engine: str
    ocr_languages: str
    llm_provider: str
    llm_model: str


@dataclass
class ComparisonResult:
    """Result of a single model configuration."""

    config_name: str
    total_receipts: int
    successful: int
    failed: int
    average_accuracy: float
    average_processing_time_ms: float
    field_scores: dict


CONFIGURATIONS = [
    ModelConfig(
        name="tesseract_llama32",
        ocr_engine="tesseract",
        ocr_languages="eng+deu+fra",
        llm_provider="ollama",
        llm_model="llama3.2",
    ),
    ModelConfig(
        name="tesseract_mistral",
        ocr_engine="tesseract",
        ocr_languages="eng+deu+fra",
        llm_provider="ollama",
        llm_model="mistral",
    ),
    ModelConfig(
        name="easyocr_llama32",
        ocr_engine="easyocr",
        ocr_languages="en,de,fr",
        llm_provider="ollama",
        llm_model="llama3.2",
    ),
]


async def evaluate_config(
    config: ModelConfig,
    ground_truth_path: Path,
    receipts_base: Path,
) -> ComparisonResult:
    """Evaluate a single model configuration."""
    print(f"\n{'='*60}")
    print(f"Evaluating: {config.name}")
    print(f"  OCR: {config.ocr_engine} ({config.ocr_languages})")
    print(f"  LLM: {config.llm_provider}/{config.llm_model}")
    print(f"{'='*60}")

    pdf_processor = PDFProcessor()

    if config.ocr_engine == "tesseract":
        ocr = OCREngineFactory.create("tesseract", languages=config.ocr_languages)
    else:
        languages = config.ocr_languages.split(",")
        ocr = OCREngineFactory.create("easyocr", languages=languages, gpu=False)

    llm = LLMExtractorFactory.create_ollama(model=config.llm_model)

    pipeline = ExtractionPipeline(
        pdf_processor=pdf_processor,
        ocr_engine=ocr,
        llm_extractor=llm,
        config=PipelineConfig(include_raw_text=False),
    )

    evaluator = ReceiptEvaluator(ground_truth_path)
    gt_data = evaluator._ground_truth

    scores = []
    field_totals: dict = {
        "provider_name": {"correct": 0, "total": 0},
        "provider_vat": {"correct": 0, "total": 0},
        "provider_country": {"correct": 0, "total": 0},
        "currency": {"correct": 0, "total": 0},
        "total_amount": {"correct": 0, "total": 0},
    }

    for receipt_info in gt_data.get("receipts", []):
        file_path = receipts_base / receipt_info.get("file_path", "")

        if not file_path.exists():
            print(f"  SKIP: {file_path.name} (not found)")
            continue

        print(f"  Processing: {file_path.name}...", end=" ")

        try:
            pdf_bytes = file_path.read_bytes()
            extracted = await pipeline.process(pdf_bytes)

            score = evaluator.evaluate_receipt(str(file_path), extracted)
            scores.append(score)

            gt = receipt_info.get("ground_truth", {})
            _update_field_scores(field_totals, gt, extracted)

            print(f"OK (score: {score.overall_score:.2f})")

        except Exception as e:
            print(f"ERROR: {e}")

    successful = [s for s in scores if s.overall_score > 0]
    avg_accuracy = sum(s.accuracy for s in successful) / len(successful) if successful else 0.0
    avg_time = sum(s.processing_time_ms for s in scores) / len(scores) if scores else 0.0

    field_accuracy = {}
    for field, counts in field_totals.items():
        if counts["total"] > 0:
            field_accuracy[field] = counts["correct"] / counts["total"]
        else:
            field_accuracy[field] = 0.0

    return ComparisonResult(
        config_name=config.name,
        total_receipts=len(scores),
        successful=len(successful),
        failed=len(scores) - len(successful),
        average_accuracy=avg_accuracy,
        average_processing_time_ms=avg_time,
        field_scores=field_accuracy,
    )


def _update_field_scores(totals: dict, gt: dict, extracted) -> None:
    """Update field-level accuracy counters."""
    gt_provider = gt.get("service_provider", {})
    gt_tx = gt.get("transaction", {})

    if gt_provider.get("name"):
        totals["provider_name"]["total"] += 1
        if gt_provider["name"].lower() in extracted.service_provider.name.lower():
            totals["provider_name"]["correct"] += 1

    if gt_provider.get("vat_number"):
        totals["provider_vat"]["total"] += 1
        gt_vat = gt_provider["vat_number"].replace(" ", "").upper()
        ext_vat = (extracted.service_provider.vat_number or "").replace(" ", "").upper()
        if gt_vat == ext_vat:
            totals["provider_vat"]["correct"] += 1

    if gt_provider.get("country"):
        totals["provider_country"]["total"] += 1
        if gt_provider["country"].upper() == (extracted.service_provider.country or "").upper():
            totals["provider_country"]["correct"] += 1

    if gt_tx.get("currency"):
        totals["currency"]["total"] += 1
        if gt_tx["currency"].upper() == extracted.transaction.currency.upper():
            totals["currency"]["correct"] += 1

    if gt_tx.get("total_amount") and gt_tx["total_amount"] > 0:
        totals["total_amount"]["total"] += 1
        if abs(gt_tx["total_amount"] - extracted.transaction.total_amount) < 1.0:
            totals["total_amount"]["correct"] += 1


async def run_comparison(
    ground_truth_path: Path,
    output_path: Path,
    configs: Optional[list[ModelConfig]] = None,
) -> None:
    """Run comparison across all configurations."""
    if configs is None:
        configs = CONFIGURATIONS

    receipts_base = Path(".")

    results = []
    for config in configs:
        try:
            result = await evaluate_config(config, ground_truth_path, receipts_base)
            results.append(asdict(result))
        except Exception as e:
            print(f"ERROR evaluating {config.name}: {e}")
            results.append({
                "config_name": config.name,
                "error": str(e),
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now().isoformat(),
        "configurations_tested": len(configs),
        "results": results,
        "summary": _generate_summary(results),
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print("COMPARISON COMPLETE")
    print(f"{'='*60}")
    print(f"Results saved to: {output_path}")
    print("\nSummary:")

    for result in results:
        if "error" in result:
            print(f"  {result['config_name']}: ERROR - {result['error']}")
        else:
            print(f"  {result['config_name']}:")
            print(f"    Accuracy: {result['average_accuracy']:.1%}")
            print(f"    Avg Time: {result['average_processing_time_ms']:.0f}ms")


def _generate_summary(results: list[dict]) -> dict:
    """Generate comparison summary."""
    valid_results = [r for r in results if "error" not in r]

    if not valid_results:
        return {"best_accuracy": None, "fastest": None}

    best_accuracy = max(valid_results, key=lambda r: r["average_accuracy"])
    fastest = min(valid_results, key=lambda r: r["average_processing_time_ms"])

    return {
        "best_accuracy": {
            "config": best_accuracy["config_name"],
            "accuracy": best_accuracy["average_accuracy"],
        },
        "fastest": {
            "config": fastest["config_name"],
            "time_ms": fastest["average_processing_time_ms"],
        },
        "recommendation": best_accuracy["config_name"],
    }


def main():
    parser = argparse.ArgumentParser(description="Compare receipt extraction models")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("evaluation/ground_truth.json"),
        help="Path to ground truth JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/comparison_results.json"),
        help="Output path for comparison results",
    )

    args = parser.parse_args()

    if not args.ground_truth.exists():
        print(f"ERROR: Ground truth file not found: {args.ground_truth}")
        sys.exit(1)

    asyncio.run(run_comparison(args.ground_truth, args.output))


if __name__ == "__main__":
    main()
