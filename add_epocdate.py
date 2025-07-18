import os
import pymysql
from datetime import datetime, timedelta

MYSQL_USER = os.environ.get("MYSQLUSER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQLPW", "")
MYSQL_DB = os.environ.get("MYSQLDB", "test")

mysql_conn = pymysql.connect(
    host="localhost",
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB,
    charset="utf8mb4",
    autocommit=True,
)
cur = mysql_conn.cursor()

# Add epocdate column if it doesn't exist
cur.execute("SHOW COLUMNS FROM treatments LIKE 'epocdate'")
if not cur.fetchone():
    cur.execute("ALTER TABLE treatments ADD COLUMN epocdate BIGINT DEFAULT NULL")

# Fetch rows with created_at and mysqlid
cur.execute("SELECT mysqlid, created_at FROM treatments")
rows = cur.fetchall()

for mysqlid, created_at in rows:
    epoch_ms = None
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            # Apply 120 minute offset to align with the expected timezone
            dt += timedelta(minutes=120)
            epoch_ms = int(dt.timestamp() * 1000)
        except Exception:
            epoch_ms = None
    cur.execute("UPDATE treatments SET epocdate=%s WHERE mysqlid=%s", (epoch_ms, mysqlid))

cur.close()
mysql_conn.close()
