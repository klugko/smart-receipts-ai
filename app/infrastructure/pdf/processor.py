import io
from pathlib import Path
from typing import BinaryIO

import numpy as np
from PIL import Image
import cv2
import pdfplumber
from pdf2image import convert_from_bytes

from app.domain.exceptions import PDFProcessingError


class PDFProcessor:
    """Handles PDF to image conversion and preprocessing."""

    def __init__(self, dpi: int = 300, grayscale: bool = True):
        self._dpi = dpi
        self._grayscale = grayscale

    def extract_native_text(self, pdf_bytes: bytes) -> str | None:
        """
        Attempt to extract text from native PDF (non-scanned).
        Returns None if no extractable text found.
        """
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                combined = "\n\n".join(text_parts).strip()
                if len(combined) > 50:
                    return combined
                return None
        except Exception:
            return None

    def convert_to_images(self, pdf_bytes: bytes) -> list[Image.Image]:
        """Convert PDF pages to PIL Images."""
        try:
            images = convert_from_bytes(pdf_bytes, dpi=self._dpi)
            return images
        except Exception as e:
            raise PDFProcessingError(
                message="Failed to convert PDF to images",
                details={"error": str(e)},
            )

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Apply preprocessing to improve OCR accuracy."""
        img_array = np.array(image)

        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        coords = np.column_stack(np.where(enhanced < 200))
        if len(coords) > 100:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = 90 + angle
            if abs(angle) > 0.5 and abs(angle) < 10:
                (h, w) = enhanced.shape[:2]
                center = (w // 2, h // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                enhanced = cv2.warpAffine(
                    enhanced, rotation_matrix, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )

        return Image.fromarray(enhanced)

    def process(self, pdf_source: bytes | BinaryIO | Path) -> tuple[list[Image.Image], str | None]:
        """
        Process PDF and return preprocessed images and optional native text.

        Returns:
            Tuple of (preprocessed images, native text if available)
        """
        if isinstance(pdf_source, Path):
            pdf_bytes = pdf_source.read_bytes()
        elif isinstance(pdf_source, bytes):
            pdf_bytes = pdf_source
        else:
            pdf_bytes = pdf_source.read()

        native_text = self.extract_native_text(pdf_bytes)

        images = self.convert_to_images(pdf_bytes)
        preprocessed = [self.preprocess_image(img) for img in images]

        return preprocessed, native_text

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get the number of pages in a PDF."""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                return len(pdf.pages)
        except Exception:
            return 1
