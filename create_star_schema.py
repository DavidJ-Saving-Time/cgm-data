import os
import json
from datetime import datetime
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
            ts DATETIME NOT NULL,
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
            insulin_type_id INT,
            units DOUBLE,
            FOREIGN KEY (time_id) REFERENCES dim_time(time_id),
            FOREIGN KEY (insulin_type_id) REFERENCES dim_insulin_type(insulin_type_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def get_time_id(dt):
    ts = dt.strftime("%Y-%m-%d %H:00:00")
    cur.execute("SELECT time_id FROM dim_time WHERE ts=%s", (ts,))
    res = cur.fetchone()
    if res:
        return res[0]
    cur.execute(
        "INSERT INTO dim_time (ts, date, hour, dow, month, year) VALUES (%s,%s,%s,%s,%s,%s)",
        (
            ts,
            dt.date(),
            dt.hour,
            dt.weekday(),
            dt.month,
            dt.year,
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


def parse_time(value):
    if value is None:
        return None
    try:
        # try epoch ms
        if isinstance(value, (int, float)):
            if value > 1e12:  # microseconds
                value = value / 1000.0
            elif value > 1e10:  # milliseconds
                value = value / 1000.0
            return datetime.utcfromtimestamp(value)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def load_glucose():
    cur.execute("SELECT mysqlid, date, sysTime, sgv, delta, direction FROM entries")
    for row in cur.fetchall():
        mysqlid, date_val, sys_time, sgv, delta, direction = row
        dt = parse_time(date_val) or parse_time(sys_time)
        if not dt:
            continue
        time_id = get_time_id(dt)
        cur.execute(
            "REPLACE INTO fact_glucose (entry_id, time_id, sgv, delta, direction) VALUES (%s,%s,%s,%s,%s)",
            (mysqlid, time_id, sgv, delta, direction),
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
        "SELECT mysqlid, created_at, timestamp, eventType, carbs, protein, fat, insulinInjections FROM treatments"
    )
    for (
        mysqlid,
        created_at,
        ts,
        event_type,
        carbs,
        protein,
        fat,
        injections_text,
    ) in cur.fetchall():
        dt = parse_time(created_at) or parse_time(ts)
        if not dt:
            continue
        time_id = get_time_id(dt)
        if event_type and "meal" in event_type.lower():
            cur.execute(
                "REPLACE INTO fact_meal (treatment_id, time_id, carbs, protein, fat) VALUES (%s,%s,%s,%s,%s)",
                (mysqlid, time_id, carbs, protein, fat),
            )
        injections = parse_insulin_json(injections_text)
        for inj in injections:
            name = inj.get("name") or "Unknown"
            units = inj.get("units")
            insulin_type_id = get_insulin_type_id(name)
            cur.execute(
                "INSERT INTO fact_insulin (treatment_id, time_id, insulin_type_id, units) VALUES (%s,%s,%s,%s)",
                (mysqlid, time_id, insulin_type_id, units),
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
