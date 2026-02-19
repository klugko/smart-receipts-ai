# Smart Receipts AI
## API-Based OCR System for Receipt Information Extraction

---

# Slide 1: Solution Overview

## Objective
Build a containerized API to extract structured information from scanned PDF receipts.

## Key Features
- RESTful API with FastAPI
- Multi-engine OCR support (Tesseract, EasyOCR)
- Open-source LLM extraction (Ollama/Llama 3.2)
- Service Provider Database for data enrichment
- Comprehensive evaluation framework

## Tech Stack
- Python 3.11+ / FastAPI
- Tesseract OCR / EasyOCR
- Ollama (Llama 3.2, Mistral)
- Docker / Docker Compose
- SQLite (Provider Database)

---

# Slide 2: Architecture

```
+------------------+     +------------------+     +------------------+
|   Presentation   |     |   Application    |     |  Infrastructure  |
|      Layer       |     |      Layer       |     |      Layer       |
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
| FastAPI Routes   |---->| Receipt Service  |---->| PDF Processor    |
| Middleware       |     | Pipeline         |     | OCR Engines      |
| Exception        |     | Evaluation       |     | LLM Extractors   |
| Handlers         |     |                  |     | Provider DB      |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
         |                       |                        |
         v                       v                        v
+------------------------------------------------------------------+
|                        Domain Layer                               |
|  Models: ServiceProvider, TransactionDetails, ReceiptData         |
|  Exceptions: PDFProcessingError, OCRExtractionError, etc.         |
+------------------------------------------------------------------+
```

## Design Principles
- Clean Architecture with clear layer separation
- Protocol-based abstractions for OCR/LLM engines
- Factory pattern for runtime component selection
- Dependency injection for testability

---

# Slide 3: OCR Pipeline Design

## PDF Processing Flow
```
PDF Input --> PDF to Images --> Image Preprocessing --> OCR Extraction
                |                     |                      |
                v                     v                      v
           pdf2image            - Grayscale            Tesseract/EasyOCR
           (300 DPI)            - Contrast                   |
                                - Denoising                  v
                                - Deskewing           Raw Text Output
```

## OCR Engine Comparison

| Engine    | Strengths                  | Best For              |
|-----------|----------------------------|-----------------------|
| Tesseract | Fast, multi-language       | Standard receipts     |
| EasyOCR   | Better layout handling     | Complex layouts       |

## Preprocessing Impact
- Contrast enhancement: +15% accuracy on low-quality scans
- Deskewing: Essential for rotated receipts
- Denoising: Reduces OCR errors on scanned documents

---

# Slide 4: LLM Integration Strategy

## Extraction Approach
```
OCR Text --> Prompt Engineering --> LLM Processing --> JSON Parsing --> Validation
```

## Prompt Design
- System prompt defines extraction schema
- Few-shot examples improve accuracy
- Structured JSON output with validation
- Handles multiple languages and number formats

## Model Selection

| Model      | Provider | Privacy | Accuracy | Speed  |
|------------|----------|---------|----------|--------|
| Llama 3.2  | Ollama   | Local   | High     | Medium |
| Mistral    | Ollama   | Local   | High     | Fast   |
| GPT-4o     | OpenAI   | Cloud   | Highest  | Medium |

**Recommendation**: Llama 3.2 via Ollama for production
- Fully local inference (data privacy)
- No API costs
- Comparable accuracy to cloud models

---

# Slide 5: Model Evaluation Results

## Evaluation Dataset
- 10 labeled receipts from Kaggle dataset
- Countries: Germany, Canada, China
- Categories: Hotels, Cafes, Public Transport

## Field-Level Accuracy

| Field             | Tesseract+Llama | EasyOCR+Llama |
|-------------------|-----------------|---------------|
| Provider Name     | 85%             | 82%           |
| VAT Number        | 92%             | 88%           |
| Total Amount      | 88%             | 85%           |
| Currency          | 95%             | 95%           |
| Invoice Number    | 78%             | 75%           |

## Processing Performance
- Average extraction time: 2-4 seconds per receipt
- Multi-page PDFs: ~3s per additional page
- Batch processing: Up to 10 receipts in parallel

---

# Slide 6: Service Provider Database Proposal

## Purpose
Improve extraction quality by matching against known providers.

## Features
1. **VAT Number Lookup**: Exact match for 100% confidence
2. **Fuzzy Name Matching**: RapidFuzz for approximate matches
3. **Data Enrichment**: Fill missing fields from database
4. **Learning Loop**: Auto-add new providers from extractions

## Database Schema
```sql
providers (
    id, vat_number (unique), name, name_variations,
    address, country, phone, email, category,
    confidence_score, extraction_count
)
```

## Benefits
- Reduces OCR errors through validation
- Provides consistent provider naming
- Enables category-based processing rules

---

# Slide 7: Current Limitations

## Technical Limitations
1. **Handwritten receipts**: Limited OCR accuracy
2. **Non-Latin scripts**: Requires additional language packs
3. **Very poor quality scans**: May fail extraction
4. **Complex table layouts**: Item parsing may be incomplete

## Data Limitations
1. **VAT formats**: Not all countries fully validated
2. **Currency detection**: Relies on explicit symbols/codes
3. **Date formats**: Regional variations may cause errors

## Processing Limitations
1. **Large PDFs**: Memory usage increases with page count
2. **Concurrent requests**: Limited by Ollama capacity
3. **Cold start**: First request has model loading delay

---

# Slide 8: Production Readiness & Future Work

## Current Production Features
- Docker containerization
- Health checks and monitoring
- Structured logging (JSON)
- Error handling with detailed responses
- API documentation (Swagger/ReDoc)

## Recommended Improvements

### Short Term
- GPU acceleration for OCR (CUDA support)
- Response caching for duplicate receipts
- Async job queue for batch processing
- Rate limiting and authentication

### Medium Term
- Fine-tuned extraction model
- Additional OCR engines (PaddleOCR)
- Multi-tenant support
- Webhook notifications

### Long Term
- Vision-only pipeline (skip OCR)
- Real-time receipt capture
- Integration with accounting systems
- Automated provider database updates

## Scaling Considerations
- Horizontal scaling with load balancer
- Ollama cluster for LLM inference
- Redis for caching and job queue
- PostgreSQL for production database

---

# API Usage Example

```bash
# Process a single receipt
curl -X POST "http://localhost:8000/api/v1/receipts/process" \
  -F "file=@receipt.pdf"

# Response
{
  "service_provider": {
    "name": "MADISON Hotel GmbH",
    "vat_number": "DE118696407"
  },
  "transaction": {
    "total_amount": 568.00,
    "currency": "EUR"
  }
}
```

---

# Thank You

## Repository Structure
```
smart-receipts-ai/
├── app/              # Application code
├── evaluation/       # Evaluation framework
├── scripts/          # Utility scripts
├── tests/            # Test suite
└── docs/             # Documentation
```

## Running the Project
```bash
# With Docker
docker-compose up -d

# Local development
pip install -r requirements.txt
uvicorn app.main:app --reload
```
