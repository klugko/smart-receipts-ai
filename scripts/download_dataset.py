#!/usr/bin/env python3
"""
Download the Kaggle Receipts Dataset.

Usage:
    python scripts/download_dataset.py

Prerequisites:
    - Set KAGGLE_USERNAME and KAGGLE_KEY in .env or environment
    - Or place kaggle.json in ~/.kaggle/
"""

import os
import sys
import zipfile
from pathlib import Path


def download_dataset(output_dir: Path) -> None:
    """Download and extract the Kaggle receipts dataset."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        print("ERROR: kaggle package not installed. Run: pip install kaggle")
        sys.exit(1)

    api = KaggleApi()

    try:
        api.authenticate()
    except Exception as e:
        print(f"ERROR: Kaggle authentication failed: {e}")
        print("\nTo fix this, either:")
        print("1. Set KAGGLE_USERNAME and KAGGLE_KEY environment variables")
        print("2. Place kaggle.json in ~/.kaggle/")
        print("\nGet your credentials from: https://www.kaggle.com/settings")
        sys.exit(1)

    dataset_name = "jenswalter/receipts"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading dataset '{dataset_name}'...")

    try:
        api.dataset_download_files(
            dataset_name,
            path=str(output_dir),
            unzip=True,
        )
        print(f"Dataset downloaded and extracted to: {output_dir}")

    except Exception as e:
        print(f"ERROR: Failed to download dataset: {e}")
        sys.exit(1)

    pdf_count = len(list(output_dir.rglob("*.pdf")))
    print(f"Total PDF files: {pdf_count}")


def main():
    project_root = Path(__file__).parent.parent
    receipts_dir = project_root / "receipts"

    if receipts_dir.exists() and any(receipts_dir.rglob("*.pdf")):
        pdf_count = len(list(receipts_dir.rglob("*.pdf")))
        print(f"Dataset already exists with {pdf_count} PDF files.")
        response = input("Re-download? [y/N]: ").strip().lower()
        if response != "y":
            print("Skipping download.")
            return

    download_dataset(receipts_dir)


if __name__ == "__main__":
    main()
