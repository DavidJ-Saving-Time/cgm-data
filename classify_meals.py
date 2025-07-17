import os
import pymysql

MYSQL_HOST = os.environ.get("MYSQLHOST", "localhost")
MYSQL_USER = os.environ.get("MYSQLUSER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQLPW", "")
MYSQL_DB = os.environ.get("MYSQLDB", "nillabg")

mysql_conn = pymysql.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB,
    charset="utf8mb4",
    autocommit=True,
)
cur = mysql_conn.cursor()


def ensure_column():
    cur.execute("SHOW COLUMNS FROM fact_meal LIKE 'classification'")
    if not cur.fetchone():
        cur.execute(
            "ALTER TABLE fact_meal ADD COLUMN classification ENUM('hypo','snack','meal')"
        )

def classify(carbs, protein, fat, ts):
    """Return meal classification based on macros and insulin timing."""

    c = carbs or 0
    p = protein or 0
    f = fat or 0

    # Check for insulin injections within 30 minutes of the meal
    cur.execute(
        "SELECT 1 FROM fact_insulin WHERE ts BETWEEN %s AND %s LIMIT 1",
        (ts - 1800, ts + 1800),
    )
    has_insulin = cur.fetchone() is not None

    if (c < 4 and p == 0 and f == 0) or (c > 0 and not has_insulin):
        return "hypo"
    if 4 < c < 7:
        return "snack"
    return "meal"

def main():
    ensure_column()
    cur.execute("SELECT treatment_id, carbs, protein, fat, ts FROM fact_meal")
    for tid, carbs, protein, fat, ts in cur.fetchall():
        category = classify(carbs, protein, fat, ts)
        cur.execute(
            "UPDATE fact_meal SET classification=%s WHERE treatment_id=%s",
            (category, tid),
        )

    cur.close()
    mysql_conn.close()

if __name__ == "__main__":
    main()
