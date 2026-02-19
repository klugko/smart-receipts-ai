from dataclasses import dataclass

from rapidfuzz import fuzz, process

from app.domain.models import ServiceProvider
from app.infrastructure.database.models import Provider
from app.infrastructure.database.repository import ProviderRepository


@dataclass
class MatchResult:
    """Result of provider matching."""

    provider: Provider
    confidence: float
    match_type: str


class ProviderMatchingService:
    """Service for matching and enriching provider data."""

    VAT_PATTERNS = {
        "DE": r"^DE\d{9}$",
        "FR": r"^FR[A-Z0-9]{2}\d{9}$",
        "GB": r"^GB\d{9}$|^GB\d{12}$",
        "AT": r"^ATU\d{8}$",
        "PL": r"^PL\d{10}$",
        "NL": r"^NL\d{9}B\d{2}$",
        "BE": r"^BE0\d{9}$",
        "IT": r"^IT\d{11}$",
        "ES": r"^ES[A-Z0-9]\d{7}[A-Z0-9]$",
    }

    def __init__(self, repository: ProviderRepository):
        self._repository = repository

    def match_provider(
        self,
        extracted: ServiceProvider,
        min_confidence: float = 0.7,
    ) -> MatchResult | None:
        """Match extracted provider against database."""
        if extracted.vat_number:
            db_provider = self._repository.get_by_vat(extracted.vat_number)
            if db_provider:
                return MatchResult(
                    provider=db_provider,
                    confidence=1.0,
                    match_type="vat_exact",
                )

        if extracted.name:
            all_providers = self._repository.get_all()
            if not all_providers:
                return None

            names = [p.name for p in all_providers]
            match = process.extractOne(
                extracted.name,
                names,
                scorer=fuzz.token_sort_ratio,
            )

            if match and match[1] >= min_confidence * 100:
                matched_name = match[0]
                for p in all_providers:
                    if p.name == matched_name:
                        return MatchResult(
                            provider=p,
                            confidence=match[1] / 100,
                            match_type="name_fuzzy",
                        )

        return None

    def enrich_provider(
        self,
        extracted: ServiceProvider,
        match_result: MatchResult | None = None,
    ) -> ServiceProvider:
        """Enrich extracted provider with database information."""
        if match_result is None:
            match_result = self.match_provider(extracted)

        if match_result is None:
            return extracted

        db_provider = match_result.provider

        enriched = ServiceProvider(
            name=extracted.name or db_provider.name,
            address=extracted.address or db_provider.address,
            vat_number=extracted.vat_number or db_provider.vat_number,
            country=extracted.country or db_provider.country,
            phone=extracted.phone or db_provider.phone,
            email=extracted.email or db_provider.email,
        )

        return enriched

    def validate_vat_format(self, vat_number: str, country: str | None = None) -> bool:
        """Validate VAT number format."""
        import re

        vat = vat_number.replace(" ", "").upper()

        if country:
            pattern = self.VAT_PATTERNS.get(country.upper())
            if pattern:
                return bool(re.match(pattern, vat))

        for pattern in self.VAT_PATTERNS.values():
            if re.match(pattern, vat):
                return True

        return False

    def learn_provider(self, extracted: ServiceProvider) -> Provider | None:
        """Add or update provider in database from extraction."""
        if not extracted.vat_number or not extracted.name:
            return None

        return self._repository.upsert(
            vat_number=extracted.vat_number,
            name=extracted.name,
            address=extracted.address,
            country=extracted.country,
        )
