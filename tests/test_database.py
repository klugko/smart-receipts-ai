import pytest
import tempfile
from pathlib import Path

from app.infrastructure.database.models import Provider, Base
from app.infrastructure.database.repository import ProviderRepository
from app.infrastructure.database.service import ProviderMatchingService
from app.domain.models import ServiceProvider


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f"sqlite:///{f.name}"
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def repository(temp_db):
    """Create a repository with temp database."""
    return ProviderRepository(temp_db)


@pytest.fixture
def matching_service(repository):
    """Create a matching service."""
    return ProviderMatchingService(repository)


class TestProviderModel:
    def test_create_provider(self):
        provider = Provider(
            vat_number="DE123456789",
            name="Test Company",
            address="123 Test St",
            country="DE",
        )
        assert provider.vat_number == "DE123456789"
        assert provider.name == "Test Company"

    def test_provider_repr(self):
        provider = Provider(vat_number="DE123", name="Test")
        assert "DE123" in repr(provider)
        assert "Test" in repr(provider)


class TestProviderRepository:
    def test_create_provider(self, repository):
        provider = Provider(
            vat_number="DE123456789",
            name="Test Company",
        )
        created = repository.create(provider)
        assert created.id is not None
        assert created.vat_number == "DE123456789"

    def test_get_by_vat(self, repository):
        repository.create(Provider(vat_number="DE111111111", name="Company A"))
        repository.create(Provider(vat_number="DE222222222", name="Company B"))

        found = repository.get_by_vat("DE111111111")
        assert found is not None
        assert found.name == "Company A"

        not_found = repository.get_by_vat("DE999999999")
        assert not_found is None

    def test_get_by_vat_normalizes(self, repository):
        repository.create(Provider(vat_number="DE123456789", name="Test"))

        found = repository.get_by_vat("de 123 456 789")
        assert found is not None

    def test_get_by_name(self, repository):
        repository.create(Provider(vat_number="DE111", name="Starbucks Coffee"))
        repository.create(Provider(vat_number="DE222", name="Coffee Shop"))

        results = repository.get_by_name("Coffee")
        assert len(results) == 2

        results = repository.get_by_name("Starbucks")
        assert len(results) == 1

    def test_get_by_country(self, repository):
        repository.create(Provider(vat_number="DE111", name="German Co", country="DE"))
        repository.create(Provider(vat_number="FR111", name="French Co", country="FR"))
        repository.create(Provider(vat_number="DE222", name="German Co 2", country="DE"))

        results = repository.get_by_country("DE")
        assert len(results) == 2

        results = repository.get_by_country("FR")
        assert len(results) == 1

    def test_get_all(self, repository):
        repository.create(Provider(vat_number="DE111", name="Co 1"))
        repository.create(Provider(vat_number="DE222", name="Co 2"))

        results = repository.get_all()
        assert len(results) == 2

    def test_upsert_new(self, repository):
        provider = repository.upsert(
            vat_number="DE123456789",
            name="New Company",
            address="123 St",
            country="DE",
        )
        assert provider.extraction_count == 1

    def test_upsert_existing(self, repository):
        repository.upsert(vat_number="DE123456789", name="Company")
        provider = repository.upsert(vat_number="DE123456789", name="Company")
        assert provider.extraction_count == 2

    def test_upsert_fills_missing_address(self, repository):
        repository.upsert(vat_number="DE123", name="Company")
        provider = repository.upsert(
            vat_number="DE123",
            name="Company",
            address="New Address"
        )
        assert provider.address == "New Address"

    def test_seed_from_extractions(self, repository):
        data = [
            {"vat_number": "DE111", "name": "Company 1"},
            {"vat_number": "DE222", "name": "Company 2"},
            {"name": "No VAT Company"},
            {},
        ]
        count = repository.seed_from_extractions(data)
        assert count == 2


class TestProviderMatchingService:
    def test_match_by_vat_exact(self, matching_service, repository):
        repository.create(Provider(
            vat_number="DE123456789",
            name="MADISON Hotel",
            country="DE",
        ))

        extracted = ServiceProvider(
            name="Madison Hotel",
            vat_number="DE123456789",
        )

        match = matching_service.match_provider(extracted)
        assert match is not None
        assert match.confidence == 1.0
        assert match.match_type == "vat_exact"

    def test_match_by_name_fuzzy(self, matching_service, repository):
        repository.create(Provider(
            vat_number="DE123",
            name="MADISON Hotel GmbH",
        ))

        extracted = ServiceProvider(
            name="Madison Hotel",
        )

        match = matching_service.match_provider(extracted, min_confidence=0.5)
        assert match is not None
        assert match.match_type == "name_fuzzy"
        assert match.confidence >= 0.5

    def test_no_match_found(self, matching_service):
        extracted = ServiceProvider(name="Unknown Company")
        match = matching_service.match_provider(extracted)
        assert match is None

    def test_enrich_provider(self, matching_service, repository):
        repository.create(Provider(
            vat_number="DE123456789",
            name="Full Company Name",
            address="123 Full Address",
            country="DE",
            phone="+49123456",
        ))

        extracted = ServiceProvider(
            name="Company",
            vat_number="DE123456789",
        )

        enriched = matching_service.enrich_provider(extracted)
        assert enriched.address == "123 Full Address"
        assert enriched.country == "DE"
        assert enriched.phone == "+49123456"

    def test_enrich_keeps_extracted_values(self, matching_service, repository):
        repository.create(Provider(
            vat_number="DE123456789",
            name="Database Name",
            address="Database Address",
        ))

        extracted = ServiceProvider(
            name="Extracted Name",
            address="Extracted Address",
            vat_number="DE123456789",
        )

        enriched = matching_service.enrich_provider(extracted)
        assert enriched.name == "Extracted Name"
        assert enriched.address == "Extracted Address"

    def test_validate_vat_format_de(self, matching_service):
        assert matching_service.validate_vat_format("DE123456789", "DE") is True
        assert matching_service.validate_vat_format("DE12345678", "DE") is False
        assert matching_service.validate_vat_format("DE1234567890", "DE") is False

    def test_validate_vat_format_fr(self, matching_service):
        assert matching_service.validate_vat_format("FR12345678901", "FR") is True

    def test_validate_vat_format_auto_detect(self, matching_service):
        assert matching_service.validate_vat_format("DE123456789") is True
        assert matching_service.validate_vat_format("INVALID") is False

    def test_learn_provider(self, matching_service, repository):
        extracted = ServiceProvider(
            name="New Company",
            vat_number="DE999999999",
            address="999 New St",
            country="DE",
        )

        provider = matching_service.learn_provider(extracted)
        assert provider is not None
        assert provider.name == "New Company"

        found = repository.get_by_vat("DE999999999")
        assert found is not None

    def test_learn_provider_no_vat(self, matching_service):
        extracted = ServiceProvider(name="No VAT Company")
        result = matching_service.learn_provider(extracted)
        assert result is None
