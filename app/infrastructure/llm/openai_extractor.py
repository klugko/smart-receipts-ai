import base64
import io
import json
import re

from openai import AsyncOpenAI
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.exceptions import LLMParsingError
from app.infrastructure.llm.base import ExtractionResult, LLMExtractor
from app.infrastructure.llm.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT,
    VISION_EXTRACTION_PROMPT,
)


class OpenAIExtractor(LLMExtractor):
    """OpenAI-based LLM extractor with vision support."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        self._model = model
        self._temperature = temperature
        self._client = AsyncOpenAI(api_key=api_key)

    @property
    def name(self) -> str:
        return f"openai/{self._model}"

    @property
    def supports_vision(self) -> bool:
        return "gpt-4" in self._model or "gpt-4o" in self._model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def extract_from_text(self, ocr_text: str) -> ExtractionResult:
        """Extract structured data from OCR text using OpenAI."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": EXTRACTION_USER_PROMPT.format(ocr_text=ocr_text)},
                ],
                temperature=self._temperature,
                response_format={"type": "json_object"},
            )

            raw_response = response.choices[0].message.content or ""
            parsed_data = self._parse_response(raw_response)

            return ExtractionResult(
                raw_response=raw_response,
                parsed_data=parsed_data,
                model=self._model,
                tokens_used=response.usage.total_tokens if response.usage else None,
            )

        except json.JSONDecodeError as e:
            raise LLMParsingError(
                message="Failed to parse OpenAI response as JSON",
                details={"error": str(e)},
            ) from e
        except Exception as e:
            raise LLMParsingError(
                message="OpenAI extraction failed",
                details={"error": str(e)},
            ) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def extract_from_image(self, image: Image.Image) -> ExtractionResult:
        """Extract structured data directly from image using vision model."""
        if not self.supports_vision:
            raise LLMParsingError(
                message=f"Model {self._model} does not support vision",
                details={},
            )

        try:
            base64_image = self._image_to_base64(image)

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_EXTRACTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                temperature=self._temperature,
                max_tokens=4096,
            )

            raw_response = response.choices[0].message.content or ""
            parsed_data = self._parse_response(raw_response)

            return ExtractionResult(
                raw_response=raw_response,
                parsed_data=parsed_data,
                model=self._model,
                tokens_used=response.usage.total_tokens if response.usage else None,
            )

        except Exception as e:
            raise LLMParsingError(
                message="OpenAI vision extraction failed",
                details={"error": str(e)},
            ) from e

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=95)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

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
