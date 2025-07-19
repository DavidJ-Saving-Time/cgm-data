import os
from collections import defaultdict
from datetime import datetime
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

# Maximum difference between a meal and an insulin injection in seconds.
# Doses within this window are associated with the meal.
TIME_WINDOW = 50 * 60  # 30 minutes


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
args = parser.parse_args()


# Map an hour in dim_time to a time bucket.
# Expected time ranges: 04-12 = morning, 12-18 = afternoon, else evening.
def time_bucket(hour: int) -> str:
    if 4 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "evening"


def nearest_glucose(ts: int, before: bool = True, offset: int = 0):
    if before:
        cur.execute(
            "SELECT sgv FROM fact_glucose WHERE ts <= %s ORDER BY ts DESC LIMIT 1",
            (ts - offset,),
        )
    else:
        cur.execute(
            "SELECT sgv FROM fact_glucose WHERE ts >= %s ORDER BY ts ASC LIMIT 1",
            (ts + offset,),
        )
    row = cur.fetchone()
    return row[0] if row else None


# Query meals paired with insulin doses based on temporal proximity
query = """
    SELECT m.treatment_id, m.ts, m.carbs, fi.units, dt.hour
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

cur.execute(query, params)

stats = defaultdict(lambda: defaultdict(list))

for tid, ts, carbs, units, hour in cur.fetchall():
    if units is None or units == 0:
        continue
    pre = nearest_glucose(ts, before=True)
    post = nearest_glucose(ts, before=False, offset=2 * 3600)
    bucket = time_bucket(hour)

    if carbs:
        stats[bucket]["carb_ratio"].append(carbs / units)
        if pre is not None and post is not None:
            stats[bucket]["carb_absorption"].append((post - pre) / carbs)
    if pre is not None and post is not None:
        stats[bucket]["insulin_sensitivity"].append((pre - post) / units)


for bucket in ["morning", "afternoon", "evening"]:
    print(f"\n=== {bucket.capitalize()} ===")
    data = stats.get(bucket, {})
    if not data:
        print("No records")
        continue
    for metric, values in data.items():
        avg_val = sum(values) / len(values)
        print(f"{metric}: {avg_val:.2f} (n={len(values)})")

cur.close()
mysql_conn.close()
