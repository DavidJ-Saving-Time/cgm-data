import os
import pymysql
from datetime import datetime, timedelta, timezone

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


def parse_time(value, offset_minutes=0):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            if value > 1e14:
                value = value / 1_000_000.0
            elif value > 1e11:
                value = value / 1000.0
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            string_value = str(value)
            if string_value.endswith("Z"):
                string_value = string_value[:-1] + "+00:00"
            dt = datetime.fromisoformat(string_value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None
    if offset_minutes:
        dt += timedelta(minutes=offset_minutes)
    return dt


def verify_glucose():
    mismatches = 0
    cur.execute(
        "SELECT f.entry_id, f.ts, e.date FROM fact_glucose f JOIN entries e ON f.entry_id = e.mysqlid"
    )
    for entry_id, ts, date_val in cur.fetchall():
        dt = parse_time(date_val, offset_minutes=120)
        if not dt:
            continue
        if int(dt.timestamp()) != ts:
            mismatches += 1
            print(f"Glucose mismatch id={entry_id}: {dt.timestamp()} vs {ts}")
    return mismatches


def verify_treatments():
    mismatches = 0
    cur.execute(
        "SELECT f.treatment_id, f.ts, t.epocdate FROM fact_meal f JOIN treatments t ON f.treatment_id = t.mysqlid"
    )
    for tid, ts, epocdate in cur.fetchall():
        dt = parse_time(epocdate)
        if not dt:
            continue
        if int(dt.timestamp()) != ts:
            mismatches += 1
            print(f"Meal mismatch id={tid}: {dt.timestamp()} vs {ts}")
    cur.execute(
        "SELECT fi.treatment_id, fi.ts, t.epocdate FROM fact_insulin fi JOIN treatments t ON fi.treatment_id = t.mysqlid"
    )
    for tid, ts, epocdate in cur.fetchall():
        dt = parse_time(epocdate)
        if not dt:
            continue
        if int(dt.timestamp()) != ts:
            mismatches += 1
            print(f"Insulin mismatch id={tid}: {dt.timestamp()} vs {ts}")
    return mismatches


def main():
    total = 0
    total += verify_glucose()
    total += verify_treatments()
    if total == 0:
        print("All timestamps match.")
    cur.close()
    mysql_conn.close()

if __name__ == "__main__":
    main()
