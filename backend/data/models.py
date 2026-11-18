"""Operational schema (public). The agent never sees these tables directly; it reads
PII-free views in the `reporting` schema (see migration 0001 and DECISIONS.md D-011)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Money = Numeric(12, 2)


class Base(DeclarativeBase):
    pass


class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(2))
    property_type: Mapped[str] = mapped_column(String(20))  # garden | midrise | highrise
    year_built: Mapped[int]
    acquired_on: Mapped[date]


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("property_id", "unit_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    unit_number: Mapped[str] = mapped_column(String(10))
    unit_type: Mapped[str] = mapped_column(String(10))  # studio | 1br | 2br | 3br
    bedrooms: Mapped[int]
    bathrooms: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    sqft: Mapped[int]
    market_rent: Mapped[Decimal] = mapped_column(Money)  # as of the dataset's as-of date


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(60))
    last_name: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(120))  # PII: excluded from reporting views
    phone: Mapped[str] = mapped_column(String(30))  # PII: excluded from reporting views
    credit_score: Mapped[int]


class Lease(Base):
    __tablename__ = "leases"
    __table_args__ = (
        CheckConstraint("end_date > start_date"),
        CheckConstraint("status IN ('active','expired','terminated','future')"),
        Index("ix_leases_unit_dates", "unit_id", "start_date", "end_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    start_date: Mapped[date]
    end_date: Mapped[date]  # scheduled end (exclusive: first day the unit is free)
    move_out_date: Mapped[date | None]  # actual end if terminated early / not yet known
    monthly_rent: Mapped[Decimal] = mapped_column(Money)
    security_deposit: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(12))
    renewal_of_lease_id: Mapped[int | None] = mapped_column(ForeignKey("leases.id"))


class RentLedger(Base):
    """One row per lease-month: what was billed and what (if anything) was paid."""

    __tablename__ = "rent_ledger"
    __table_args__ = (UniqueConstraint("lease_id", "period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lease_id: Mapped[int] = mapped_column(ForeignKey("leases.id"))
    period: Mapped[date] = mapped_column(index=True)  # first day of the month billed
    due_date: Mapped[date]
    amount_due: Mapped[Decimal] = mapped_column(Money)
    amount_paid: Mapped[Decimal] = mapped_column(Money)
    paid_on: Mapped[date | None]  # date the (last) payment landed; null if unpaid


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    trade: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(30))
    hourly_rate: Mapped[Decimal] = mapped_column(Money)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint("priority IN ('emergency','high','normal','low')"),
        CheckConstraint("status IN ('open','completed','cancelled')"),
        Index("ix_work_orders_property_opened", "property_id", "opened_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))  # hvac | plumbing | electrical | ...
    priority: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10))
    opened_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    cost: Mapped[Decimal | None] = mapped_column(Money)
    description: Mapped[str] = mapped_column(String(300))


class OperatingExpense(Base):
    """Monthly non-maintenance opex per property (taxes, insurance, utilities, payroll...)."""

    __tablename__ = "operating_expenses"
    __table_args__ = (UniqueConstraint("property_id", "period", "category"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    period: Mapped[date]
    category: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Money)


class DatasetMeta(Base):
    """Records the seed and as-of date the data was generated with (for reproducibility)."""

    __tablename__ = "dataset_meta"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
