import json
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from datetime import datetime

from app.domain.models import ReceiptData


@dataclass
class FieldScore:
    """Score for a single field extraction."""

    field_name: str
    expected: Any
    extracted: Any
    is_match: bool
    similarity: float


@dataclass
class ReceiptScore:
    """Score for a single receipt extraction."""

    file_path: str
    field_scores: list[FieldScore] = field(default_factory=list)
    overall_score: float = 0.0
    processing_time_ms: int = 0

    @property
    def accuracy(self) -> float:
        if not self.field_scores:
            return 0.0
        return sum(1 for f in self.field_scores if f.is_match) / len(self.field_scores)


@dataclass
class EvaluationReport:
    """Complete evaluation report."""

    receipt_scores: list[ReceiptScore] = field(default_factory=list)
    total_receipts: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    average_accuracy: float = 0.0
    average_processing_time_ms: float = 0.0
    field_level_accuracy: dict = field(default_factory=dict)


class ReceiptEvaluator:
    """Evaluates receipt extraction against ground truth."""

    def __init__(self, ground_truth_path: Path | str):
        self._ground_truth_path = Path(ground_truth_path)
        self._ground_truth = self._load_ground_truth()

    def _load_ground_truth(self) -> dict:
        """Load ground truth data from JSON file."""
        with open(self._ground_truth_path) as f:
            return json.load(f)

    def evaluate_receipt(
        self,
        file_path: str,
        extracted: ReceiptData,
    ) -> ReceiptScore:
        """Evaluate a single receipt extraction against ground truth."""
        ground_truth = self._find_ground_truth(file_path)
        if not ground_truth:
            return ReceiptScore(file_path=file_path, overall_score=0.0)

        field_scores = []

        gt_provider = ground_truth.get("service_provider", {})
        field_scores.extend(self._compare_provider(gt_provider, extracted.service_provider))

        gt_transaction = ground_truth.get("transaction", {})
        field_scores.extend(self._compare_transaction(gt_transaction, extracted.transaction))

        overall = sum(f.similarity for f in field_scores) / len(field_scores) if field_scores else 0.0

        return ReceiptScore(
            file_path=file_path,
            field_scores=field_scores,
            overall_score=overall,
            processing_time_ms=extracted.metadata.processing_time_ms,
        )

    def _find_ground_truth(self, file_path: str) -> dict | None:
        """Find ground truth for a given file path."""
        for receipt in self._ground_truth.get("receipts", []):
            gt_path = receipt.get("file_path", "")
            if file_path.endswith(gt_path) or gt_path.endswith(Path(file_path).name):
                return receipt.get("ground_truth", {})
        return None

    def _compare_provider(self, expected: dict, extracted) -> list[FieldScore]:
        """Compare service provider fields."""
        scores = []

        for field_name in ["name", "address", "vat_number", "country", "phone", "email"]:
            exp_value = expected.get(field_name)
            if exp_value is None:
                continue

            ext_value = getattr(extracted, field_name, None)
            similarity = self._compute_similarity(exp_value, ext_value)

            scores.append(FieldScore(
                field_name=f"provider.{field_name}",
                expected=exp_value,
                extracted=ext_value,
                is_match=similarity > 0.8,
                similarity=similarity,
            ))

        return scores

    def _compare_transaction(self, expected: dict, extracted) -> list[FieldScore]:
        """Compare transaction fields."""
        scores = []

        for field_name in ["currency", "total_amount", "subtotal", "invoice_number", "payment_method"]:
            exp_value = expected.get(field_name)
            if exp_value is None:
                continue

            ext_value = getattr(extracted, field_name, None)
            similarity = self._compute_similarity(exp_value, ext_value)

            scores.append(FieldScore(
                field_name=f"transaction.{field_name}",
                expected=exp_value,
                extracted=ext_value,
                is_match=similarity > 0.8,
                similarity=similarity,
            ))

        exp_items = expected.get("items", [])
        ext_items = extracted.items
        if exp_items:
            item_score = self._compare_items(exp_items, ext_items)
            scores.append(FieldScore(
                field_name="transaction.items",
                expected=len(exp_items),
                extracted=len(ext_items),
                is_match=item_score > 0.7,
                similarity=item_score,
            ))

        return scores

    def _compare_items(self, expected: list, extracted: list) -> float:
        """Compare item lists."""
        if not expected:
            return 1.0 if not extracted else 0.5

        if not extracted:
            return 0.0

        count_score = min(len(extracted), len(expected)) / max(len(extracted), len(expected))

        name_matches = 0
        for exp_item in expected:
            exp_name = exp_item.get("name", "").lower()
            for ext_item in extracted:
                if exp_name in ext_item.name.lower() or ext_item.name.lower() in exp_name:
                    name_matches += 1
                    break

        name_score = name_matches / len(expected) if expected else 0

        return (count_score + name_score) / 2

    def _compute_similarity(self, expected: Any, extracted: Any) -> float:
        """Compute similarity between expected and extracted values."""
        if expected is None or extracted is None:
            return 0.0 if expected != extracted else 1.0

        if isinstance(expected, (int, float)) and isinstance(extracted, (int, float)):
            if expected == 0:
                return 1.0 if extracted == 0 else 0.0
            diff = abs(expected - extracted) / abs(expected)
            return max(0.0, 1.0 - diff)

        exp_str = str(expected).lower().strip()
        ext_str = str(extracted).lower().strip()

        if exp_str == ext_str:
            return 1.0

        if exp_str in ext_str or ext_str in exp_str:
            return 0.9

        return self._levenshtein_similarity(exp_str, ext_str)

    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Compute Levenshtein similarity between two strings."""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        len1, len2 = len(s1), len(s2)
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                dp[i][j] = min(
                    dp[i-1][j] + 1,
                    dp[i][j-1] + 1,
                    dp[i-1][j-1] + cost,
                )

        distance = dp[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)

    def generate_report(self, scores: list[ReceiptScore]) -> EvaluationReport:
        """Generate evaluation report from scores."""
        if not scores:
            return EvaluationReport()

        successful = [s for s in scores if s.overall_score > 0]
        avg_accuracy = sum(s.accuracy for s in successful) / len(successful) if successful else 0.0
        avg_time = sum(s.processing_time_ms for s in scores) / len(scores)

        field_counts: dict = {}
        for score in scores:
            for fs in score.field_scores:
                if fs.field_name not in field_counts:
                    field_counts[fs.field_name] = {"correct": 0, "total": 0}
                field_counts[fs.field_name]["total"] += 1
                if fs.is_match:
                    field_counts[fs.field_name]["correct"] += 1

        field_accuracy = {}
        for field_name, counts in field_counts.items():
            if counts["total"] > 0:
                field_accuracy[field_name] = counts["correct"] / counts["total"]

        return EvaluationReport(
            receipt_scores=scores,
            total_receipts=len(scores),
            successful_extractions=len(successful),
            failed_extractions=len(scores) - len(successful),
            average_accuracy=avg_accuracy,
            average_processing_time_ms=avg_time,
            field_level_accuracy=field_accuracy,
        )

    def export_report_json(self, report: EvaluationReport, output_path: Path) -> None:
        """Export report as JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_receipts": report.total_receipts,
                "successful": report.successful_extractions,
                "failed": report.failed_extractions,
                "average_accuracy": report.average_accuracy,
                "average_processing_time_ms": report.average_processing_time_ms,
            },
            "field_level_accuracy": report.field_level_accuracy,
            "detailed_scores": [
                {
                    "file_path": s.file_path,
                    "overall_score": s.overall_score,
                    "accuracy": s.accuracy,
                    "processing_time_ms": s.processing_time_ms,
                    "fields": [
                        {
                            "name": fs.field_name,
                            "expected": str(fs.expected),
                            "extracted": str(fs.extracted),
                            "similarity": fs.similarity,
                            "is_match": fs.is_match,
                        }
                        for fs in s.field_scores
                    ]
                }
                for s in report.receipt_scores
            ]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def export_report_csv(self, report: EvaluationReport, output_path: Path) -> None:
        """Export report as CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "file_path", "overall_score", "accuracy", "processing_time_ms",
                "provider_name_match", "vat_match", "total_amount_match"
            ])

            for score in report.receipt_scores:
                field_matches = {fs.field_name: fs.is_match for fs in score.field_scores}
                writer.writerow([
                    score.file_path,
                    f"{score.overall_score:.3f}",
                    f"{score.accuracy:.3f}",
                    score.processing_time_ms,
                    field_matches.get("provider.name", "N/A"),
                    field_matches.get("provider.vat_number", "N/A"),
                    field_matches.get("transaction.total_amount", "N/A"),
                ])
