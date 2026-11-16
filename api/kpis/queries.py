"""KPI SQL. One query per metric, kept as explicit SQL so the definitions are reviewable.

Conventions (DECISIONS.md D-010..D-013):
  * a unit is occupied on day D if a lease has start_date <= D < COALESCE(move_out_date, end_date)
  * end_date is exclusive (first day the unit is free), so a lease "expires" in the month of
    end_date - 1
  * a payment counts as of D only if paid_on <= D (point-in-time correct)
  * delinquency aging buckets are by charge month, as in standard PM aging reports
  * NOI is cash basis: collected rent - operating expenses - completed work-order cost
Every query takes :pids (int[] or NULL = whole portfolio).
"""

PROPERTY_FILTER = "(CAST(:pids AS int[]) IS NULL OR {col} = ANY(CAST(:pids AS int[])))"


def _f(col: str) -> str:
    return PROPERTY_FILTER.format(col=col)


ACTIVE_ON = "{l}.start_date <= {d} AND {d} < COALESCE({l}.move_out_date, {l}.end_date)"

META = "SELECT key, value FROM dataset_meta"

PROPERTIES = """
SELECT p.id, p.name, p.city, p.state, p.property_type, p.year_built,
       count(u.id) AS units
FROM properties p JOIN units u ON u.property_id = p.id
GROUP BY p.id ORDER BY p.name
"""

OCCUPANCY_BY_PROPERTY = f"""
SELECT p.id AS property_id, p.name AS property, count(u.id) AS units,
       count(l.id) AS occupied,
       round(count(l.id)::numeric / count(u.id), 4)::float AS occupancy
FROM properties p
JOIN units u ON u.property_id = p.id
LEFT JOIN leases l ON l.unit_id = u.id AND {ACTIVE_ON.format(l="l", d=":as_of")}
WHERE {_f("p.id")}
GROUP BY p.id, p.name
ORDER BY p.name
"""

OCCUPANCY_TREND = f"""
WITH months AS (
  SELECT generate_series(CAST(:start AS date), CAST(:end AS date), interval '1 month')::date AS d
),
scope AS (SELECT id FROM units WHERE {_f("property_id")})
SELECT m.d AS month,
       round((SELECT count(*) FROM leases l JOIN scope s ON s.id = l.unit_id
              WHERE {ACTIVE_ON.format(l="l", d="m.d")})::numeric
             / NULLIF((SELECT count(*) FROM scope), 0), 4)::float AS occupancy
FROM months m ORDER BY m.d
"""

RENT_ROLL = f"""
SELECT p.name AS property, u.id AS unit_id, u.unit_number, u.unit_type, u.sqft,
       u.market_rent::float AS market_rent,
       l.id AS lease_id, t.first_name || ' ' || t.last_name AS tenant,
       l.start_date, l.end_date, l.monthly_rent::float AS monthly_rent,
       COALESCE(b.balance, 0)::float AS balance,
       count(*) OVER () AS total_rows
FROM units u
JOIN properties p ON p.id = u.property_id
LEFT JOIN leases l ON l.unit_id = u.id AND {ACTIVE_ON.format(l="l", d=":as_of")}
LEFT JOIN tenants t ON t.id = l.tenant_id
LEFT JOIN LATERAL (
  SELECT sum(r.amount_due - CASE WHEN r.paid_on <= :as_of THEN r.amount_paid ELSE 0 END)
         AS balance
  FROM rent_ledger r JOIN leases lx ON lx.id = r.lease_id
  WHERE lx.tenant_id = l.tenant_id AND lx.unit_id = u.id AND r.due_date <= :as_of
) b ON true
WHERE {_f("p.id")}
ORDER BY p.name, u.unit_number::int
LIMIT :limit OFFSET :offset
"""

DELINQUENCY_AGING = f"""
WITH items AS (
  SELECT l.tenant_id, u.property_id,
         r.amount_due - CASE WHEN r.paid_on <= :as_of THEN r.amount_paid ELSE 0 END AS outstanding,
         (extract(year FROM CAST(:as_of AS date)) * 12 + extract(month FROM CAST(:as_of AS date)))
         - (extract(year FROM r.due_date) * 12 + extract(month FROM r.due_date)) AS months_past,
         EXISTS (SELECT 1 FROM leases l3
                 WHERE l3.tenant_id = l.tenant_id AND {ACTIVE_ON.format(l="l3", d=":as_of")})
           AS current_resident
  FROM rent_ledger r
  JOIN leases l ON l.id = r.lease_id
  JOIN units u ON u.id = l.unit_id
  WHERE r.due_date <= :as_of AND {_f("u.property_id")}
)
SELECT CASE WHEN months_past = 0 THEN '0-30' WHEN months_past = 1 THEN '31-60'
            WHEN months_past = 2 THEN '61-90' ELSE '90+' END AS bucket,
       current_resident,
       round(sum(outstanding), 2)::float AS amount,
       count(DISTINCT tenant_id) AS tenants
FROM items WHERE outstanding > 0
GROUP BY 1, 2 ORDER BY 1, 2
"""

LEASE_EXPIRATIONS = f"""
SELECT date_trunc('month', l.end_date - 1)::date AS month,
       p.id AS property_id, p.name AS property,
       count(*) AS leases, sum(l.monthly_rent)::float AS monthly_rent
FROM leases l
JOIN units u ON u.id = l.unit_id
JOIN properties p ON p.id = u.property_id
WHERE {ACTIVE_ON.format(l="l", d=":as_of")}
  AND l.end_date - 1 < CAST(:as_of AS date) + make_interval(months => :months)
  AND {_f("p.id")}
GROUP BY 1, 2, 3 ORDER BY 1, 3
"""

# Revenue by payment date, opex by period, maintenance by completion date.
NOI_MONTHLY = f"""
WITH months AS (
  SELECT generate_series(CAST(:start AS date), CAST(:end AS date), interval '1 month')::date AS m
),
props AS (SELECT id, name FROM properties WHERE {_f("id")}),
rev AS (
  SELECT u.property_id, date_trunc('month', r.paid_on)::date AS m, sum(r.amount_paid) AS v
  FROM rent_ledger r JOIN leases l ON l.id = r.lease_id JOIN units u ON u.id = l.unit_id
  WHERE r.paid_on IS NOT NULL AND r.paid_on <= :as_of GROUP BY 1, 2
),
opex AS (SELECT property_id, period AS m, sum(amount) AS v FROM operating_expenses GROUP BY 1, 2),
maint AS (
  SELECT property_id, date_trunc('month', completed_at)::date AS m, sum(cost) AS v
  FROM work_orders WHERE status = 'completed' AND completed_at::date <= :as_of GROUP BY 1, 2
)
SELECT p.id AS property_id, p.name AS property, months.m AS month,
       COALESCE(rev.v, 0)::float AS revenue,
       COALESCE(opex.v, 0)::float AS operating_expenses,
       COALESCE(maint.v, 0)::float AS maintenance,
       (COALESCE(rev.v, 0) - COALESCE(opex.v, 0) - COALESCE(maint.v, 0))::float AS noi
FROM props p CROSS JOIN months
LEFT JOIN rev ON rev.property_id = p.id AND rev.m = months.m
LEFT JOIN opex ON opex.property_id = p.id AND opex.m = months.m
LEFT JOIN maint ON maint.property_id = p.id AND maint.m = months.m
ORDER BY p.name, months.m
"""

SLA_TARGETS = "(VALUES ('emergency', 24), ('high', 72), ('normal', 168), ('low', 336))"

# A ticket meets SLA if completed within its target; open tickets already past target count as
# breaches; open tickets still inside their window and cancelled tickets are excluded.
WORK_ORDER_SLA = f"""
WITH wo AS (
  SELECT w.*, s.target_hours, p.name AS property,
         extract(epoch FROM (w.completed_at - w.opened_at)) / 3600 AS hours,
         extract(epoch FROM (CAST(:as_of AS date) + 1 - w.opened_at)) / 3600 AS age_hours
  FROM work_orders w
  JOIN {SLA_TARGETS} AS s(priority, target_hours) ON s.priority = w.priority
  JOIN properties p ON p.id = w.property_id
  WHERE w.opened_at >= :start AND w.opened_at < CAST(:end AS date) + interval '1 month'
    AND w.opened_at::date <= :as_of AND w.status <> 'cancelled' AND {_f("w.property_id")}
),
judged AS (
  SELECT *, CASE WHEN status = 'completed' THEN hours <= target_hours
                 WHEN age_hours > target_hours THEN false END AS met
  FROM wo
)
SELECT {{group_col}} AS grp, count(*) AS tickets,
       count(*) FILTER (WHERE met IS NOT NULL) AS judged,
       count(*) FILTER (WHERE met) AS met,
       round(avg(CASE WHEN met THEN 1.0 ELSE 0.0 END) FILTER (WHERE met IS NOT NULL), 4)::float
         AS sla_rate,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY hours)::numeric, 1)::float
         AS median_hours
FROM judged GROUP BY 1 ORDER BY 1
"""
