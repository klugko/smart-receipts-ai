EXTRACTION_SYSTEM_PROMPT = """You are an expert receipt data extraction system. Your task is to extract structured information from receipt text obtained via OCR.

Extract the following information and return it as valid JSON:

1. Service Provider:
   - name: The business name
   - address: Complete address if available
   - vat_number: VAT/Tax registration number (look for patterns like DE123456789, VAT12345, USt-IdNr, etc.)
   - country: ISO 2-letter country code based on address or VAT number
   - phone: Contact phone if present
   - email: Contact email if present

2. Transaction Details:
   - items: List of purchased items with:
     - name: Item description
     - quantity: Number of items (default 1)
     - unit_price: Price per unit if available
     - total_price: Total price for this line
     - vat_rate: VAT rate if shown for this item
   - currency: 3-letter ISO currency code (EUR, USD, GBP, etc.)
   - subtotal: Amount before VAT if shown
   - total_amount: Final total amount
   - vat_details: List of VAT breakdowns with rate, net_amount, vat_amount, gross_amount
   - payment_method: How was it paid (cash, card, etc.)
   - transaction_date: Date of transaction in ISO format (YYYY-MM-DD)
   - invoice_number: Receipt/Invoice number

Important rules:
- Extract only information that is clearly present in the text
- Use null for fields that cannot be determined
- Amounts should be numbers, not strings
- Dates should be in ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD)
- VAT rates should be percentages (e.g., 19 for 19%)
- Be careful with German/European number formats: 1.234,56 means 1234.56
- Return ONLY valid JSON, no explanations or markdown"""

EXTRACTION_USER_PROMPT = """Extract structured data from this receipt text:

---
{ocr_text}
---

Return the extracted information as JSON following this exact structure:
{{
    "service_provider": {{
        "name": "...",
        "address": "...",
        "vat_number": "...",
        "country": "...",
        "phone": "...",
        "email": "..."
    }},
    "transaction": {{
        "items": [
            {{"name": "...", "quantity": 1, "unit_price": null, "total_price": 0.00, "vat_rate": null}}
        ],
        "currency": "EUR",
        "subtotal": null,
        "total_amount": 0.00,
        "vat_details": [
            {{"rate": 19, "net_amount": 0.00, "vat_amount": 0.00, "gross_amount": 0.00}}
        ],
        "payment_method": null,
        "transaction_date": null,
        "invoice_number": null
    }}
}}"""

VISION_EXTRACTION_PROMPT = """Analyze this receipt image and extract all structured information.

Extract:
1. Service Provider: name, full address, VAT number, country code, phone, email
2. Transaction: all items (name, quantity, price), currency, totals, VAT breakdown, payment method, date, invoice number

Return ONLY valid JSON with this structure:
{
    "service_provider": {"name": "...", "address": "...", "vat_number": "...", "country": "...", "phone": null, "email": null},
    "transaction": {
        "items": [{"name": "...", "quantity": 1, "unit_price": null, "total_price": 0.00, "vat_rate": null}],
        "currency": "EUR",
        "subtotal": null,
        "total_amount": 0.00,
        "vat_details": [{"rate": 19, "net_amount": 0.00, "vat_amount": 0.00, "gross_amount": 0.00}],
        "payment_method": null,
        "transaction_date": null,
        "invoice_number": null
    }
}

Rules:
- Extract only what you can clearly see
- Use null for missing fields
- Numbers must be numeric (not strings)
- Dates in ISO format (YYYY-MM-DD)
- Handle European number formats (1.234,56 = 1234.56)"""
