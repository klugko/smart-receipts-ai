from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Base, Provider


class ProviderRepository:
    """Repository for provider database operations."""

    def __init__(self, database_url: str):
        if database_url.startswith("sqlite:///"):
            db_path = database_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self._engine)

    def get_by_vat(self, vat_number: str) -> Provider | None:
        """Find provider by VAT number."""
        normalized_vat = vat_number.replace(" ", "").upper()
        with Session(self._engine) as session:
            stmt = select(Provider).where(Provider.vat_number == normalized_vat)
            return session.scalar(stmt)

    def get_by_name(self, name: str) -> Sequence[Provider]:
        """Find providers by name (partial match)."""
        with Session(self._engine) as session:
            stmt = select(Provider).where(Provider.name.ilike(f"%{name}%"))
            return session.scalars(stmt).all()

    def get_by_country(self, country: str) -> Sequence[Provider]:
        """Find providers by country code."""
        with Session(self._engine) as session:
            stmt = select(Provider).where(Provider.country == country.upper())
            return session.scalars(stmt).all()

    def get_all(self) -> Sequence[Provider]:
        """Get all providers."""
        with Session(self._engine) as session:
            stmt = select(Provider)
            return session.scalars(stmt).all()

    def create(self, provider: Provider) -> Provider:
        """Create a new provider."""
        provider.vat_number = provider.vat_number.replace(" ", "").upper()
        with Session(self._engine) as session:
            session.add(provider)
            session.commit()
            session.refresh(provider)
            return provider

    def update(self, provider: Provider) -> Provider:
        """Update an existing provider."""
        with Session(self._engine) as session:
            session.merge(provider)
            session.commit()
            return provider

    def upsert(
        self,
        vat_number: str,
        name: str,
        address: str | None = None,
        country: str | None = None,
        category: str | None = None,
    ) -> Provider:
        """Insert or update a provider."""
        existing = self.get_by_vat(vat_number)

        if existing:
            existing.extraction_count += 1
            if address and not existing.address:
                existing.address = address
            return self.update(existing)

        new_provider = Provider(
            vat_number=vat_number,
            name=name,
            address=address,
            country=country,
            category=category,
        )
        return self.create(new_provider)

    def seed_from_extractions(self, providers_data: list[dict]) -> int:
        """Seed database from extracted provider data."""
        count = 0
        for data in providers_data:
            vat = data.get("vat_number")
            name = data.get("name")
            if vat and name:
                self.upsert(
                    vat_number=vat,
                    name=name,
                    address=data.get("address"),
                    country=data.get("country"),
                    category=data.get("category"),
                )
                count += 1
        return count
