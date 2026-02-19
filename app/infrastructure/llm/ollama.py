import json
import re

import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.exceptions import LLMParsingError
from app.infrastructure.llm.base import LLMExtractor, ExtractionResult
from app.infrastructure.llm.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT


class OllamaExtractor(LLMExtractor):
    """Ollama-based LLM extractor for local inference."""

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        temperature: float = 0.1,
    ):
        self._model = model
        self._host = host
        self._temperature = temperature
        self._client = ollama.Client(host=host)

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def extract_from_text(self, ocr_text: str) -> ExtractionResult:
        """Extract structured data from OCR text using Ollama."""
        try:
            response = self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": EXTRACTION_USER_PROMPT.format(ocr_text=ocr_text)},
                ],
                options={
                    "temperature": self._temperature,
                },
                format="json",
            )

            raw_response = response["message"]["content"]
            parsed_data = self._parse_response(raw_response)

            return ExtractionResult(
                raw_response=raw_response,
                parsed_data=parsed_data,
                model=self._model,
                tokens_used=response.get("eval_count"),
            )

        except json.JSONDecodeError as e:
            raise LLMParsingError(
                message="Failed to parse LLM response as JSON",
                details={"error": str(e), "response": raw_response[:500]},
            )
        except Exception as e:
            raise LLMParsingError(
                message="Ollama extraction failed",
                details={"error": str(e)},
            )

    def _parse_response(self, response: str) -> dict:
        """Parse and validate LLM response."""
        response = response.strip()

        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if json_match:
            response = json_match.group(1).strip()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])
            else:
                raise

        self._validate_structure(data)
        return data

    def _validate_structure(self, data: dict) -> None:
        """Validate extracted data has required structure."""
        if "service_provider" not in data:
            raise LLMParsingError(
                message="Missing service_provider in response",
                details={"data": data},
            )

        if "transaction" not in data:
            raise LLMParsingError(
                message="Missing transaction in response",
                details={"data": data},
            )

        sp = data["service_provider"]
        if not isinstance(sp, dict) or "name" not in sp:
            raise LLMParsingError(
                message="Invalid service_provider structure",
                details={"service_provider": sp},
            )

        tx = data["transaction"]
        if not isinstance(tx, dict) or "total_amount" not in tx:
            raise LLMParsingError(
                message="Invalid transaction structure",
                details={"transaction": tx},
            )
