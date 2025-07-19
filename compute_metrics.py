import os
from collections import defaultdict
from datetime import datetime
from statistics import median, stdev
from typing import Optional
import argparse
import pymysql

MYSQL_HOST = os.environ.get("MYSQLHOST", "localhost")
MYSQL_USER = os.environ.get("MYSQLUSER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQLPW", "")
MYSQL_DB = os.environ.get("MYSQLDB", "test")

mysql_conn = pymysql.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB,
    charset="utf8mb4",
    autocommit=True,
)
cur = mysql_conn.cursor()

# Default settings (seconds)
DEFAULT_TIME_WINDOW = 50 * 60  # 50 minutes
DEFAULT_POST_OFFSET = 2 * 3600  # 2 hours
DEFAULT_GLUCOSE_WINDOW = 15 * 60  # 15 minutes
DEFAULT_NO_CORRECTION_BEFORE = 2 * 3600  # 2 hours
DEFAULT_NO_CORRECTION_AFTER = 3 * 3600  # 3 hours

# Acceptable pre-meal glucose range (mg/dL).
# Corresponds to 5 – 1.5 mmol/L = 63 mg/dL and 5 + 1.5 mmol/L = 117 mg/dL.
PRE_MEAL_MIN = 63
PRE_MEAL_MAX = 117

# Conversion factor from mg/dL to mmol/L.
MGDL_TO_MMOLL = 1 / 18


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}") from exc


parser = argparse.ArgumentParser(description="Compute insulin/meal metrics")
parser.add_argument("--start", type=parse_date, help="Start date YYYY-MM-DD")
parser.add_argument("--end", type=parse_date, help="End date YYYY-MM-DD")
parser.add_argument(
    "--time-window",
    type=int,
    default=50,
    help="Meal-insulin association window in minutes (default: 50)",
)
parser.add_argument(
    "--post-offset",
    type=int,
    default=120,
    help="Minutes after meal for post-meal glucose (default: 120)",
)
parser.add_argument(
    "--pre-window",
    type=int,
    default=15,
    help="Minutes to average glucose before meal (default: 15)",
)
parser.add_argument(
    "--post-window",
    type=int,
    default=15,
    help="Minutes to average glucose after meal offset (default: 15)",
)
parser.add_argument(
    "--nocorr-before",
    type=int,
    default=120,
    help="Minutes before meal that must be correction-bolus free (default: 120)",
)
parser.add_argument(
    "--nocorr-after",
    type=int,
    default=180,
    help="Minutes after meal that must be correction-bolus free (default: 180)",
)
args = parser.parse_args()

TIME_WINDOW = args.time_window * 60
POST_OFFSET = args.post_offset * 60
PRE_WINDOW = args.pre_window * 60
POST_WINDOW = args.post_window * 60
NO_CORRECTION_BEFORE = args.nocorr_before * 60
NO_CORRECTION_AFTER = args.nocorr_after * 60


# Map an hour in dim_time to a time bucket.
# Expected time ranges: 04-12 = morning, 12-18 = afternoon, else evening.
def time_bucket(hour: int) -> str:
    if 4 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "evening"


def avg_glucose(
    ts: int,
    *,
    before: bool = True,
    offset: int = 0,
    window: int = DEFAULT_GLUCOSE_WINDOW,
) -> Optional[float]:
    """Return the average glucose in a window around *ts*.

    If *before* is True the window ends at ``ts - offset``. Otherwise it starts
    at ``ts + offset``. The window size is defined by *window* seconds.
    """

    if before:
        start = ts - offset - window
        end = ts - offset
    else:
        start = ts + offset
        end = ts + offset + window

    cur.execute(
        "SELECT AVG(sgv) FROM fact_glucose WHERE ts BETWEEN %s AND %s",
        (start, end),
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return None


def correction_bolus_before(ts: int) -> bool:
    """Return True if a bolus injection occurred in the NO_CORRECTION_BEFORE
    window prior to *ts* (excluding the TIME_WINDOW immediately preceding the
    meal)."""
    start = ts - NO_CORRECTION_BEFORE
    end = ts - TIME_WINDOW
    if end <= start:
        return False

    cur.execute(
        """
        SELECT 1
        FROM fact_insulin fi
        JOIN dim_insulin_type dit ON fi.insulin_type_id = dit.insulin_type_id
        WHERE dit.insulin_class = 'bolus'
          AND fi.ts BETWEEN %s AND %s
        LIMIT 1
        """,
        (start, end),
    )
    return cur.fetchone() is not None


def correction_bolus_after(ts: int) -> bool:
    """Return True if a bolus injection occurred within NO_CORRECTION_AFTER
    seconds after *ts* (excluding the TIME_WINDOW immediately following the meal)."""

    start = ts + TIME_WINDOW
    end = ts + NO_CORRECTION_AFTER
    if end <= start:
        return False

    cur.execute(
        """
        SELECT 1
        FROM fact_insulin fi
        JOIN dim_insulin_type dit ON fi.insulin_type_id = dit.insulin_type_id
        WHERE dit.insulin_class = 'bolus'
          AND fi.ts BETWEEN %s AND %s
        LIMIT 1
        """,
        (start, end),
    )
    return cur.fetchone() is not None


# Query meals paired with insulin doses based on temporal proximity
# Each meal can have multiple associated insulin doses. Sum the units so that
# each meal contributes a single data point with the total bolus amount.
query = """
    SELECT m.treatment_id,
           m.ts,
           m.carbs,
           SUM(fi.units) AS units,
           dt.hour
    FROM fact_meal m
    JOIN fact_insulin fi ON fi.ts BETWEEN m.ts - %s AND m.ts + %s
    JOIN dim_insulin_type dit ON fi.insulin_type_id = dit.insulin_type_id
    JOIN dim_time dt ON m.time_id = dt.time_id
"""
params = [TIME_WINDOW, TIME_WINDOW]
conditions = ["dit.insulin_class = 'bolus'"]
if args.start:
    conditions.append("dt.date >= %s")
    params.append(args.start.isoformat())
if args.end:
    conditions.append("dt.date <= %s")
    params.append(args.end.isoformat())
if conditions:
    query += " WHERE " + " AND ".join(conditions)

# Aggregate insulin units for each meal
query += " GROUP BY m.treatment_id, m.ts, m.carbs, dt.hour"

cur.execute(query, params)

stats = defaultdict(lambda: defaultdict(list))

for tid, ts, carbs, units, hour in cur.fetchall():
    if units is None or units == 0:
        continue
    if correction_bolus_before(ts):
        continue
    pre = avg_glucose(ts, before=True, window=PRE_WINDOW)
    if pre is None or not (PRE_MEAL_MIN <= pre <= PRE_MEAL_MAX):
        continue
    if correction_bolus_after(ts):
        continue
    post = avg_glucose(ts, before=False, offset=POST_OFFSET, window=POST_WINDOW)
    bucket = time_bucket(hour)

    if carbs:
        stats[bucket]["carb_ratio"].append(carbs / units)
        if pre is not None and post is not None:
            stats[bucket]["carb_absorption"].append((post - pre) * MGDL_TO_MMOLL / carbs)
    if pre is not None and post is not None:
        stats[bucket]["insulin_sensitivity"].append((pre - post) * MGDL_TO_MMOLL / units)


for bucket in ["morning", "afternoon", "evening"]:
    print(f"\n=== {bucket.capitalize()} ===")
    data = stats.get(bucket, {})
    if not data:
        print("No records")
        continue
    for metric, values in data.items():
        avg_val = sum(values) / len(values)
        med_val = median(values)
        sd_val = stdev(values) if len(values) > 1 else 0.0
        unit = " mmol/L per U" if metric == "insulin_sensitivity" else ""
        print(
            f"{metric}: {avg_val:.2f}{unit} ±{sd_val:.2f} (median {med_val:.2f}, n={len(values)})"
        )

cur.close()
mysql_conn.close()
