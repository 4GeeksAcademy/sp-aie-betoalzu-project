from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class Country(str, Enum):
    SPAIN = "Spain"
    USA = "USA"


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class SupplierCategory(str, Enum):
    JOB_BOARDS = "job_boards"
    ATS_SOFTWARE = "ats_software"
    ASSESSMENT_TOOLS = "assessment_tools"
    TRAINING_PLATFORMS = "training_platforms"
    PAYROLL_AND_HR_SOFTWARE = "payroll_and_hr_software"
    VIDEO_INTERVIEW = "video_interview"
    BACKGROUND_CHECK = "background_check"
    OFFICE_AND_FACILITIES = "office_and_facilities"
    IT_AND_SOFTWARE_LICENSES = "it_and_software_licenses"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_country_currency(country: Country, currency: Currency) -> None:
    expected_currency = Currency.EUR if country == Country.SPAIN else Currency.USD
    if currency != expected_currency:
        raise ValueError(
            f"Invalid country/currency combination: {country.value} requires {expected_currency.value}."
        )


class SupplierBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    country: Country
    categories: list[SupplierCategory] = Field(min_length=1)
    monthly_rate: float = Field(gt=0)
    currency: Currency
    status: SupplierStatus
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None

    @field_validator("categories")
    @classmethod
    def ensure_unique_categories(cls, categories: list[SupplierCategory]) -> list[SupplierCategory]:
        if len(categories) != len(set(categories)):
            raise ValueError("categories cannot contain duplicates")
        return categories

    @model_validator(mode="after")
    def validate_currency_by_country(self) -> SupplierBase:
        _validate_country_currency(self.country, self.currency)
        return self


class SupplierCreate(SupplierBase):
    updated_at: datetime = Field(default_factory=_utc_now)


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1)
    country: Country | None = None
    categories: list[SupplierCategory] | None = Field(default=None, min_length=1)
    monthly_rate: float | None = Field(default=None, gt=0)
    currency: Currency | None = None
    status: SupplierStatus | None = None
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None
    updated_at: datetime | None = None

    @field_validator("categories")
    @classmethod
    def ensure_unique_categories(
        cls, categories: list[SupplierCategory] | None
    ) -> list[SupplierCategory] | None:
        if categories is None:
            return categories
        if len(categories) != len(set(categories)):
            raise ValueError("categories cannot contain duplicates")
        return categories

    @model_validator(mode="after")
    def enforce_business_rules(self) -> SupplierUpdate:
        if self.monthly_rate is not None:
            self.updated_at = _utc_now()

        if self.country is not None and self.currency is not None:
            _validate_country_currency(self.country, self.currency)

        return self


class Supplier(SupplierBase):
    updated_at: datetime = Field(default_factory=_utc_now)

    def renewal_due_in_days(self, days: int = 60, *, reference_date: date | None = None) -> bool:
        if self.contract_renewal_date is None:
            return False

        today = reference_date or date.today()
        delta = (self.contract_renewal_date - today).days
        return 0 <= delta <= days
