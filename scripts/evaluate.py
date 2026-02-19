#!/usr/bin/env python3
"""
Evaluation script for receipt extraction models.

Usage:
    python scripts/evaluate.py --receipts-dir receipts/ --output evaluation/results/
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.pdf.processor import PDFProcessor
from app.infrastructure.ocr.factory import OCREngineFactory
from app.infrastructure.llm.factory import LLMExtractorFactory
from app.application.pipeline import ExtractionPipeline, PipelineConfig
from evaluation.evaluator import ReceiptEvaluator


async def evaluate_receipts(
    ground_truth_path: Path,
    output_dir: Path,
    ocr_engine: str = "tesseract",
    llm_provider: str = "ollama",
    llm_model: str = "llama3.2",
) -> None:
    """Run evaluation on labeled receipts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluator = ReceiptEvaluator(ground_truth_path)
    gt_data = evaluator._ground_truth

    pdf_processor = PDFProcessor()

    if ocr_engine == "tesseract":
        ocr = OCREngineFactory.create("tesseract", languages="eng+deu+fra")
    else:
        ocr = OCREngineFactory.create("easyocr", languages=["en", "de", "fr"])

    if llm_provider == "openai":
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: OPENAI_API_KEY not set")
            sys.exit(1)
        llm = LLMExtractorFactory.create_openai(api_key=api_key, model=llm_model)
    else:
        llm = LLMExtractorFactory.create_ollama(model=llm_model)

    pipeline = ExtractionPipeline(
        pdf_processor=pdf_processor,
        ocr_engine=ocr,
        llm_extractor=llm,
        config=PipelineConfig(include_raw_text=True),
    )

    scores = []
    results = []

    for receipt_info in gt_data.get("receipts", []):
        file_path = receipt_info.get("file_path", "")
        full_path = Path(file_path)

        if not full_path.exists():
            print(f"SKIP: {file_path} not found")
            continue

        print(f"Processing: {file_path}")

        try:
            pdf_bytes = full_path.read_bytes()
            extracted = await pipeline.process(pdf_bytes)

            score = evaluator.evaluate_receipt(file_path, extracted)
            scores.append(score)

            results.append({
                "file_path": file_path,
                "extracted": extracted.model_dump(mode="json"),
                "ground_truth": receipt_info.get("ground_truth", {}),
                "score": {
                    "overall": score.overall_score,
                    "accuracy": score.accuracy,
                    "processing_time_ms": score.processing_time_ms,
                },
            })

            print(f"  Score: {score.overall_score:.2f} | Time: {score.processing_time_ms}ms")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "file_path": file_path,
                "error": str(e),
            })

    report = evaluator.generate_report(scores)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"evaluation_report_{timestamp}.json"

    report_data = {
        "timestamp": timestamp,
        "config": {
            "ocr_engine": ocr_engine,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        },
        "summary": {
            "total_receipts": report.total_receipts,
            "successful": report.successful_extractions,
            "failed": report.failed_extractions,
            "average_accuracy": report.average_accuracy,
            "average_processing_time_ms": report.average_processing_time_ms,
        },
        "results": results,
    }

    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)

    print(f"\nEvaluation complete. Report saved to: {report_path}")
    print(f"  Total receipts: {report.total_receipts}")
    print(f"  Successful: {report.successful_extractions}")
    print(f"  Average accuracy: {report.average_accuracy:.2%}")
    print(f"  Average time: {report.average_processing_time_ms:.0f}ms")


def main():
    parser = argparse.ArgumentParser(description="Evaluate receipt extraction models")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("evaluation/ground_truth.json"),
        help="Path to ground truth JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--ocr",
        choices=["tesseract", "easyocr"],
        default="tesseract",
        help="OCR engine to use",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM provider",
    )
    parser.add_argument(
        "--llm-model",
        default="llama3.2",
        help="LLM model name",
    )

    args = parser.parse_args()

    asyncio.run(evaluate_receipts(
        ground_truth_path=args.ground_truth,
        output_dir=args.output,
        ocr_engine=args.ocr,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
    ))


if __name__ == "__main__":
    main()
