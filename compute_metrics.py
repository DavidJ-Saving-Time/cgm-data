import os
from collections import defaultdict
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


# Query meals paired with insulin doses
cur.execute(
    """
    SELECT m.treatment_id, m.ts, m.carbs, fi.units, dt.hour
    FROM fact_meal m
    JOIN fact_insulin fi ON fi.treatment_id = m.treatment_id
    JOIN dim_time dt ON m.time_id = dt.time_id
    """
)

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
