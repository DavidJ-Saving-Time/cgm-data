import os
import json
import ast
from pymongo import MongoClient
import pymysql

# Load environment variables
MONGODB_URI = os.environ.get("MONGODBKEY")
MYSQL_USER = os.environ.get("MYSQLUSER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQLPW", "")
MYSQL_DB = os.environ.get("MYSQLDB", "test")

if MONGODB_URI is None:
    raise RuntimeError("MONGODBKEY environment variable not set")

# Read MongoDB schema
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "mondodbschema.txt")
with open(SCHEMA_FILE, "r") as f:
    schema = ast.literal_eval(f.read())

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


def mysql_type(field_types):
    """Return a MySQL column type for a set of python type names"""
    if "int" in field_types and field_types == {"int"}:
        return "INT"
    if "float" in field_types and field_types <= {"float", "int"}:
        return "DOUBLE"
    return "TEXT"


# Create tables for each collection based on schema
for coll_name, fields in schema.items():
    if not fields:
        # store entire document as JSON
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS `{coll_name}` (doc JSON)"
        )
        continue
    columns = []
    for field, types in fields.items():
        if field == "_id":
            col_type = "VARCHAR(255)"
        else:
            col_type = mysql_type(set(types))
        columns.append(f"`{field}` {col_type}")
    column_sql = ", ".join(columns)
    cur.execute(f"CREATE TABLE IF NOT EXISTS `{coll_name}` ({column_sql})")


# Function to prepare values for insertion

def prepare_value(value):
    if value is None:
        return None
    # Convert ObjectId, dicts, lists etc to JSON strings
    try:
        import bson
        if isinstance(value, bson.ObjectId):
            return str(value)
    except Exception:
        pass
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


# Copy data from MongoDB to MySQL
for coll_name, fields in schema.items():
    collection = mongo_db[coll_name]
    docs = collection.find({})

    if not fields:
        # Insert whole document as JSON
        for doc in docs:
            cur.execute(
                f"INSERT INTO `{coll_name}` (doc) VALUES (%s)",
                (json.dumps(doc, default=str),),
            )
        continue

    field_names = list(fields.keys())
    placeholders = ", ".join(["%s"] * len(field_names))
    insert_sql = f"INSERT INTO `{coll_name}` ({', '.join('`'+f+'`' for f in field_names)}) VALUES ({placeholders})"

    for doc in docs:
        values = [prepare_value(doc.get(f)) for f in field_names]
        cur.execute(insert_sql, values)

cur.close()
mysql_conn.close()
mongo_client.close()
