import os
import json
from pymongo import MongoClient
import pymysql

# Environment variables
MONGODB_URI = os.environ.get("MONGODBKEY")
MYSQL_USER = os.environ.get("MYSQLUSER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQLPW", "")
MYSQL_DB = os.environ.get("MYSQLDB", "test")

if not MONGODB_URI:
    raise RuntimeError("MONGODBKEY environment variable not set")

# Connect to MongoDB
mongo_client = MongoClient(MONGODB_URI)
mongo_db = mongo_client.get_default_database()

# Connect to MySQL
mysql_conn = pymysql.connect(
    host="localhost",
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB,
    charset="utf8mb4",
    autocommit=True,
)
cur = mysql_conn.cursor()


ENTRY_FIELDS = [
    "_id",
    "date",
    "dateString",
    "delta",
    "device",
    "direction",
    "filtered",
    "noise",
    "rssi",
    "sgv",
    "sysTime",
    "type",
    "unfiltered",
    "utcOffset",
]

TREATMENT_FIELDS = [
    "_id",
    "carbs",
    "created_at",
    "duration",
    "enteredBy",
    "eventType",
    "fat",
    "insulin",
    "insulinInjections",
    "notes",
    "profile",
    "protein",
    "sysTime",
    "timestamp",
    "utcOffset",
    "uuid",
]


def create_tables():
    """Create the tables we need if they don't already exist."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            mysqlid INT(11) NOT NULL AUTO_INCREMENT,
            _id VARCHAR(255) DEFAULT NULL,
            date DOUBLE DEFAULT NULL,
            dateString TEXT DEFAULT NULL,
            delta DOUBLE DEFAULT NULL,
            device TEXT DEFAULT NULL,
            direction TEXT DEFAULT NULL,
            filtered DOUBLE DEFAULT NULL,
            noise INT(11) DEFAULT NULL,
            rssi INT(11) DEFAULT NULL,
            sgv INT(11) DEFAULT NULL,
            sysTime TEXT DEFAULT NULL,
            type TEXT DEFAULT NULL,
            unfiltered DOUBLE DEFAULT NULL,
            utcOffset INT(11) DEFAULT NULL,
            PRIMARY KEY (mysqlid)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS treatments (
            mysqlid INT(11) NOT NULL AUTO_INCREMENT,
            _id VARCHAR(255) DEFAULT NULL,
            carbs DOUBLE DEFAULT NULL,
            created_at TEXT DEFAULT NULL,
            duration INT(11) DEFAULT NULL,
            enteredBy TEXT DEFAULT NULL,
            eventType TEXT DEFAULT NULL,
            fat TEXT DEFAULT NULL,
            insulin DOUBLE DEFAULT NULL,
            insulinInjections TEXT DEFAULT NULL,
            notes TEXT DEFAULT NULL,
            profile TEXT DEFAULT NULL,
            protein TEXT DEFAULT NULL,
            sysTime TEXT DEFAULT NULL,
            timestamp TEXT DEFAULT NULL,
            utcOffset INT(11) DEFAULT NULL,
            uuid TEXT DEFAULT NULL,
            PRIMARY KEY (mysqlid)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def prepare_value(value):
    """Convert Mongo values to something MySQL can store."""
    if value is None:
        return None
    try:
        import bson
        if isinstance(value, bson.ObjectId):
            return str(value)
    except Exception:
        pass
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def upsert_row(table, fields, doc):
    doc_id = str(doc.get("_id")) if doc.get("_id") is not None else None

    cur.execute(f"SELECT mysqlid FROM {table} WHERE _id=%s", (doc_id,))
    existing = cur.fetchone()

    values = [prepare_value(doc.get(f)) for f in fields]

    if existing:
        # Build update statement without _id
        update_cols = ", ".join(f"`{f}`=%s" for f in fields if f != "_id")
        update_vals = [prepare_value(doc.get(f)) for f in fields if f != "_id"]
        update_vals.append(doc_id)
        cur.execute(
            f"UPDATE {table} SET {update_cols} WHERE _id=%s",
            update_vals,
        )
    else:
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(f"`{f}`" for f in fields)
        cur.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            values,
        )


def sync_collection(collection_name, fields):
    collection = mongo_db[collection_name]
    for doc in collection.find({}):
        upsert_row(collection_name, fields, doc)


def main():
    create_tables()
    sync_collection("entries", ENTRY_FIELDS)
    sync_collection("treatments", TREATMENT_FIELDS)

    cur.close()
    mysql_conn.close()
    mongo_client.close()


if __name__ == "__main__":
    main()
