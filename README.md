# Smart Receipts AI

API-based OCR system for extracting structured information from scanned PDF receipts.

## Features

- PDF receipt processing with multiple OCR engines (Tesseract, EasyOCR)
- LLM-based structured data extraction using open-source models (Ollama/Llama 3.2)
- Multi-language support (English, German, French)
- Service Provider Database for data enrichment and validation
- RESTful API with FastAPI
- Docker containerization with Ollama integration
- Comprehensive evaluation framework for model comparison

## Architecture

```
app/
├── domain/           # Core business models and exceptions
├── application/      # Use cases and pipeline orchestration
├── infrastructure/   # OCR, LLM, PDF processing, Database
└── presentation/     # FastAPI routes and middleware
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Tesseract OCR (for local development)

### Installation

```bash
cd smart-receipts-ai

python -m venv venv
source venv/bin/activate

# Base installation (Tesseract OCR - lightweight, ~50MB)
pip install -r requirements.txt

# System dependencies
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra poppler-utils
```

### Optional: EasyOCR (adds ~500MB CPU / ~3GB GPU)

```bash
# CPU-only version (no NVIDIA packages)
pip install -r requirements-easyocr.txt

# Or with GPU support
pip install easyocr
```

### Download Dataset (Optional)

```bash
export KAGGLE_USERNAME=your_username
export KAGGLE_KEY=your_key
python scripts/download_dataset.py
```

### Configuration

```bash
cp .env.example .env
```

Key settings in `.env`:
- `OLLAMA_HOST`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model to use (default: llama3.2)
- `OCR_ENGINE`: tesseract or easyocr
- `ENABLE_PROVIDER_DATABASE`: Enable provider matching (default: true)

### Running with Docker (Recommended)

```bash
docker-compose up --build

docker-compose logs -f app
```

This starts:
- FastAPI application on port 8000
- Ollama server with automatic model pull

### Running Locally

```bash
ollama pull llama3.2

uvicorn app.main:app --reload --port 8000
```

## API Usage

### Process a Receipt

```bash
curl -X POST "http://localhost:8000/api/v1/receipts/process" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@receipt.pdf"
```

### Response Format

```json
{
  "service_provider": {
    "name": "MADISON Hotel GmbH",
    "address": "Schaarsteinweg 4, 20459 Hamburg",
    "vat_number": "DE118696407",
    "country": "DE"
  },
  "transaction": {
    "items": [
      {"name": "Accommodation", "quantity": 5, "total_price": 550.00}
    ],
    "currency": "EUR",
    "total_amount": 568.00,
    "vat_details": [
      {"rate": 7.0, "net_amount": 514.02, "vat_amount": 35.98, "gross_amount": 550.00}
    ],
    "payment_method": "Mastercard",
    "transaction_date": "2018-12-21",
    "invoice_number": "484950"
  },
  "metadata": {
    "ocr_engine": "tesseract",
    "llm_model": "llama3.2",
    "processing_time_ms": 2500,
    "page_count": 1
  }
}
```

### Batch Processing

```bash
curl -X POST "http://localhost:8000/api/v1/receipts/process/batch" \
  -F "files=@receipt1.pdf" \
  -F "files=@receipt2.pdf"
```

### Run Evaluation

```bash
curl -X POST "http://localhost:8000/api/v1/evaluate/run" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Evaluation

### Run Evaluation Script

```bash
python scripts/evaluate.py --ocr tesseract --llm-model llama3.2
```

### Compare Models

```bash
python scripts/compare_models.py --output evaluation/comparison_results.json
```

## Testing

```bash
pytest

pytest --cov=app --cov-report=html
```

## Project Structure

```
smart-receipts-ai/
├── app/
│   ├── domain/              # Business models, exceptions
│   ├── application/         # Pipeline, services
│   ├── infrastructure/      # OCR, LLM, PDF, Database
│   └── presentation/        # API layer
├── evaluation/              # Ground truth, evaluator
├── scripts/                 # Download, evaluate, compare
├── tests/                   # Test suite
├── docs/                    # Presentation slides
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| ENVIRONMENT | development/production | development |
| OLLAMA_HOST | Ollama server URL | http://localhost:11434 |
| OLLAMA_MODEL | Ollama model name | llama3.2 |
| OCR_ENGINE | tesseract or easyocr | tesseract |
| TESSERACT_LANGUAGES | Language codes | eng+deu+fra |
| ENABLE_PROVIDER_DATABASE | Enable provider DB | true |
| DATABASE_URL | SQLite database path | sqlite:///./data/providers.db |
| LOG_LEVEL | DEBUG/INFO/WARNING/ERROR | INFO |
| MAX_FILE_SIZE_MB | Max upload size | 10 |

## Model Selection

### OCR Engines
- **Tesseract**: Fast, reliable, excellent multi-language support
- **EasyOCR**: Better for complex layouts, optional GPU acceleration

### LLM Models (Open-Source via Ollama)
- **Llama 3.2**: Recommended - best balance of accuracy and speed
- **Mistral**: Faster inference, slightly lower accuracy
- **Qwen**: Good for multilingual receipts

All extraction uses local open-source models for data privacy compliance.

## Service Provider Database

The optional provider database improves extraction quality by:
1. Validating VAT numbers against known formats
2. Matching provider names with fuzzy matching
3. Enriching extracted data with stored information
4. Learning new providers from successful extractions

## Dataset

The `receipts/` directory contains the [Kaggle Receipts Dataset](https://www.kaggle.com/datasets/jenswalter/receipts/data) used for development and evaluation.

### Structure

```
receipts/
├── 2017/
│   └── de/public transport/    # German transport tickets
├── 2018/
│   ├── ca/hotel/               # Canadian hotel receipts
│   ├── cn/cafe/                # Chinese cafe receipts
│   └── de/
│       ├── cafe/               # German cafe receipts (Starbucks)
│       ├── hotel/              # German hotel receipts (Madison, Ibis)
│       └── public transport/   # German railway tickets (Deutsche Bahn)
├── 2019-2024/                  # Additional receipts by year/country
└── index.txt                   # Dataset index
```

### Ground Truth Labels

10 receipts have been manually labeled for evaluation in `evaluation/ground_truth.json`:

| Category | Count | Countries |
|----------|-------|-----------|
| Hotels | 5 | DE, CA |
| Cafes | 3 | DE, CN |
| Public Transport | 2 | DE |

## Presentation

See `docs/PRESENTATION.html` (or `docs/PRESENTATION.md`) for slides covering:
- Solution overview and architecture
- Technical approach and pipeline design
- Model evaluation results
- Provider database proposal
- Current limitations and future work

## License

Proprietary - See LICENSE file for details.
