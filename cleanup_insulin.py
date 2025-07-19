import os
import pymysql

"""Remove insulin entries of 1 unit or less within 5 minutes of another dose.

Usage::

    python cleanup_insulin.py

The script uses MYSQLHOST, MYSQLUSER, MYSQLPW, and MYSQLDB environment
variables to connect to the database.
"""

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

cur.execute(
    """
    DELETE fi1
    FROM fact_insulin fi1
    WHERE fi1.units <= 1
      AND EXISTS (
          SELECT 1
          FROM fact_insulin fi2
          WHERE fi2.fact_id <> fi1.fact_id
            AND ABS(fi2.ts - fi1.ts) <= 300
      );
    """
)

cur.close()
mysql_conn.close()
