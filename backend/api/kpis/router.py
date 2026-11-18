from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Engine

from api.db import fetch_all, get_engine
from api.kpis import queries as q

router = APIRouter(prefix="/kpis", tags=["kpis"])
EngineDep = Annotated[Engine, Depends(get_engine)]


# ------------------------------------------------------------------ filters
def _month_floor(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def dataset_as_of(engine: EngineDep) -> date:
    meta = {r["key"]: r["value"] for r in fetch_all(engine, q.META, {})}
    return date.fromisoformat(meta["as_of"])


class Filters(BaseModel):
    pids: list[int] | None
    as_of: date
    start: date  # first day of first month
    end: date  # first day of last month (inclusive)


def get_filters(
    engine: EngineDep,
    property_id: Annotated[list[int] | None, Query(description="Repeatable; omit = all")] = None,
    as_of: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Filters:
    """Defaults: as_of = dataset as-of date; range = the 12 months ending at as_of."""
    as_of = as_of or dataset_as_of(engine)
    end = _month_floor(end or as_of)
    start = _month_floor(start or _add_months(end, -11))
    return Filters(pids=property_id or None, as_of=as_of, start=start, end=end)


FiltersDep = Annotated[Filters, Depends(get_filters)]


# ------------------------------------------------------------------ models
class PropertyOut(BaseModel):
    id: int
    name: str
    city: str
    state: str
    property_type: str
    year_built: int
    units: int


class MetaOut(BaseModel):
    as_of: date
    seed: int
    first_month: date


class OccupancyRow(BaseModel):
    property_id: int
    property: str
    units: int
    occupied: int
    occupancy: float


class TrendPoint(BaseModel):
    month: date
    occupancy: float | None


class OccupancyOut(BaseModel):
    as_of: date
    by_property: list[OccupancyRow]
    trend: list[TrendPoint]


class RentRollRow(BaseModel):
    property: str
    unit_id: int
    unit_number: str
    unit_type: str
    sqft: int
    market_rent: float
    lease_id: int | None
    tenant: str | None
    start_date: date | None
    end_date: date | None
    monthly_rent: float | None
    balance: float


class RentRollOut(BaseModel):
    as_of: date
    total: int
    rows: list[RentRollRow]


class AgingRow(BaseModel):
    bucket: Literal["0-30", "31-60", "61-90", "90+"]
    current_resident: bool
    amount: float
    tenants: int


class ExpirationRow(BaseModel):
    month: date
    property_id: int
    property: str
    leases: int
    monthly_rent: float


class NoiRow(BaseModel):
    property_id: int
    property: str
    month: date
    revenue: float
    operating_expenses: float
    maintenance: float
    noi: float


class SlaRow(BaseModel):
    grp: str
    tickets: int
    judged: int
    met: int
    sla_rate: float | None
    median_hours: float | None


# ------------------------------------------------------------------ endpoints
@router.get("/meta", response_model=MetaOut)
def meta(engine: EngineDep) -> MetaOut:
    m = {r["key"]: r["value"] for r in fetch_all(engine, q.META, {})}
    as_of = date.fromisoformat(m["as_of"])
    return MetaOut(as_of=as_of, seed=int(m["seed"]), first_month=_add_months(as_of, -23))


@router.get("/properties", response_model=list[PropertyOut])
def properties(engine: EngineDep) -> list[dict]:
    return fetch_all(engine, q.PROPERTIES, {})


@router.get("/occupancy", response_model=OccupancyOut)
def occupancy(engine: EngineDep, f: FiltersDep) -> OccupancyOut:
    p = f.model_dump()
    return OccupancyOut(
        as_of=f.as_of,
        by_property=fetch_all(engine, q.OCCUPANCY_BY_PROPERTY, p),  # type: ignore[arg-type]
        trend=fetch_all(engine, q.OCCUPANCY_TREND, p),  # type: ignore[arg-type]
    )


@router.get("/rent-roll", response_model=RentRollOut)
def rent_roll(
    engine: EngineDep,
    f: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RentRollOut:
    rows = fetch_all(engine, q.RENT_ROLL, {**f.model_dump(), "limit": limit, "offset": offset})
    total = rows[0]["total_rows"] if rows else 0
    return RentRollOut(as_of=f.as_of, total=total, rows=rows)  # type: ignore[arg-type]


@router.get("/delinquency", response_model=list[AgingRow])
def delinquency(engine: EngineDep, f: FiltersDep) -> list[dict]:
    return fetch_all(engine, q.DELINQUENCY_AGING, f.model_dump())


@router.get("/lease-expirations", response_model=list[ExpirationRow])
def lease_expirations(
    engine: EngineDep, f: FiltersDep, months: Annotated[int, Query(ge=1, le=24)] = 12
) -> list[dict]:
    return fetch_all(engine, q.LEASE_EXPIRATIONS, {**f.model_dump(), "months": months})


@router.get("/noi", response_model=list[NoiRow])
def noi(engine: EngineDep, f: FiltersDep) -> list[dict]:
    return fetch_all(engine, q.NOI_MONTHLY, f.model_dump())


SLA_GROUPS = {"priority": "priority", "property": "property", "category": "category"}


@router.get("/work-order-sla", response_model=list[SlaRow])
def work_order_sla(
    engine: EngineDep,
    f: FiltersDep,
    group_by: Literal["priority", "property", "category"] = "priority",
) -> list[dict]:
    # group_by is validated by the Literal above and mapped through an allowlist: never
    # interpolate raw user input into SQL.
    sql = q.WORK_ORDER_SLA.format(group_col=SLA_GROUPS[group_by])
    return fetch_all(engine, sql, f.model_dump())
