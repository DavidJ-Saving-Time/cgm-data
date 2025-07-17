import os
import json
from datetime import datetime, timedelta
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


def create_dimension_tables():
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_time (
            time_id INT AUTO_INCREMENT PRIMARY KEY,
            ts BIGINT NOT NULL,
            date DATE,
            hour INT,
            dow INT,
            month INT,
            year INT,
            UNIQUE KEY u_ts (ts)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dim_insulin_type (
            insulin_type_id INT AUTO_INCREMENT PRIMARY KEY,
            insulin_name VARCHAR(255) UNIQUE,
            insulin_class ENUM('bolus','basal','unknown') DEFAULT 'unknown'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def create_fact_tables():
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_glucose (
            entry_id INT PRIMARY KEY,
            time_id INT,
            ts BIGINT,
            sgv INT,
            delta DOUBLE,
            direction TEXT,
            FOREIGN KEY (time_id) REFERENCES dim_time(time_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_meal (
            treatment_id INT PRIMARY KEY,
            time_id INT,
            ts BIGINT,
            carbs DOUBLE,
            protein DOUBLE,
            fat DOUBLE,
            FOREIGN KEY (time_id) REFERENCES dim_time(time_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_insulin (
            fact_id INT AUTO_INCREMENT PRIMARY KEY,
            treatment_id INT,
            time_id INT,
            ts BIGINT,
            insulin_type_id INT,
            units DOUBLE,
            FOREIGN KEY (time_id) REFERENCES dim_time(time_id),
            FOREIGN KEY (insulin_type_id) REFERENCES dim_insulin_type(insulin_type_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def get_time_id(dt):
    hour_dt = dt.replace(minute=0, second=0, microsecond=0)
    ts_epoch = int(hour_dt.timestamp())
    cur.execute("SELECT time_id FROM dim_time WHERE ts=%s", (ts_epoch,))
    res = cur.fetchone()
    if res:
        return res[0]
    cur.execute(
        "INSERT INTO dim_time (ts, date, hour, dow, month, year) VALUES (%s,%s,%s,%s,%s,%s)",
        (
            ts_epoch,
            hour_dt.date(),
            hour_dt.hour,
            hour_dt.weekday(),
            hour_dt.month,
            hour_dt.year,
        ),
    )
    return cur.lastrowid


def classify_insulin(name: str) -> str:
    if not name:
        return "unknown"
    n = name.lower()
    if "novarap" in n or "novorapid" in n:
        return "bolus"
    if "tresiba" in n:
        return "basal"
    return "unknown"


def get_insulin_type_id(name: str) -> int:
    if name is None:
        name = "Unknown"
    cur.execute("SELECT insulin_type_id FROM dim_insulin_type WHERE insulin_name=%s", (name,))
    res = cur.fetchone()
    if res:
        return res[0]
    insulin_class = classify_insulin(name)
    cur.execute(
        "INSERT INTO dim_insulin_type (insulin_name, insulin_class) VALUES (%s,%s)",
        (name, insulin_class),
    )
    return cur.lastrowid


def parse_time(value, offset_minutes=0):
    """Parse various timestamp formats and apply an optional offset."""
    if value is None:
        return None
    try:
        # Numeric values are epoch based
        if isinstance(value, (int, float)):
            if value > 1e12:  # microseconds
                value = value / 1000.0
            elif value > 1e10:  # milliseconds
                value = value / 1000.0
            dt = datetime.utcfromtimestamp(value)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

    if offset_minutes:
        dt += timedelta(minutes=offset_minutes)
    return dt


def load_glucose():
    cur.execute(
        "SELECT mysqlid, date, sgv, delta, direction FROM entries"
    )
    for row in cur.fetchall():
        mysqlid, date_val, sgv, delta, direction = row
        dt = parse_time(date_val, offset_minutes=120)
        if not dt:
            continue
        time_id = get_time_id(dt)
        ts_epoch = int(dt.timestamp())
        cur.execute(
            "REPLACE INTO fact_glucose (entry_id, time_id, ts, sgv, delta, direction) VALUES (%s,%s,%s,%s,%s,%s)",
            (mysqlid, time_id, ts_epoch, sgv, delta, direction),
        )


def parse_insulin_json(text):
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Skip if any text field mentions priming
        priming = False
        for v in item.values():
            if isinstance(v, str) and "priming" in v.lower():
                priming = True
                break
        if priming:
            continue
        name = item.get("insulin") or item.get("insulinType") or item.get("name")
        units = item.get("units") or item.get("amount") or item.get("dose")
        if units is None:
            try:
                units = float(item.get("value"))
            except Exception:
                units = None
        result.append({"name": name, "units": units})
    return result


def load_treatments():
    cur.execute(
        "SELECT mysqlid, epocdate, eventType, carbs, protein, fat, insulinInjections, notes FROM treatments"
    )
    for (
        mysqlid,
        epocdate,
        event_type,
        carbs,
        protein,
        fat,
        injections_text,
        notes,
    ) in cur.fetchall():
        dt = parse_time(epocdate)
        if not dt:
            continue
        time_id = get_time_id(dt)
        ts_epoch = int(dt.timestamp())
        if event_type and "meal" in event_type.lower():
            cur.execute(
                "REPLACE INTO fact_meal (treatment_id, time_id, ts, carbs, protein, fat) VALUES (%s,%s,%s,%s,%s,%s)",
                (mysqlid, time_id, ts_epoch, carbs, protein, fat),
            )
        skip_insulin = notes and "priming" in notes.lower()
        injections = [] if skip_insulin else parse_insulin_json(injections_text)
        for inj in injections:
            name = inj.get("name") or "Unknown"
            units = inj.get("units")
            insulin_type_id = get_insulin_type_id(name)
            cur.execute(
                "INSERT INTO fact_insulin (treatment_id, time_id, ts, insulin_type_id, units) VALUES (%s,%s,%s,%s,%s)",
                (mysqlid, time_id, ts_epoch, insulin_type_id, units),
            )


def main():
    create_dimension_tables()
    create_fact_tables()
    load_glucose()
    load_treatments()
    cur.close()
    mysql_conn.close()


if __name__ == "__main__":
    main()
