# CGM Data Tools

Scripts for importing, transforming and analyzing continuous glucose monitor (CGM) and treatment records.

Most scripts expect a MySQL database and read connection settings from the following environment variables:

- `MYSQLHOST` (default `localhost`)
- `MYSQLUSER` (default `root`)
- `MYSQLPW`   (default empty)
- `MYSQLDB`   (default `test`)

Several utilities also use `MONGODBKEY` to connect to a Nightscout MongoDB instance.

## Data import

- **`mongo_to_mysql.py`** – copy the `entries` and `treatments` collections from MongoDB into MySQL tables.
- **`int_mongo_to_mysql.py`** – similar to the above but reads the schema from `mondodbschema.txt` so nested values can be stored as JSON.
- **`create_star_schema.py`** – populate star‑schema tables (`dim_time`, `dim_insulin_type`, `fact_glucose`, `fact_meal`, `fact_insulin`) using the raw tables. Timestamps are normalised and insulin injections are parsed from JSON.
- **`add_epocdate.py`** – add an epoch timestamp column to the `treatments` table based on `created_at`.

## Data cleaning and classification

- **`cleanup_insulin.py`** – delete insulin doses of 1 unit or less occurring within five minutes of another dose.
- **`classify_meals.py`** – assign `hypo`, `snack` or `meal` labels to rows in `fact_meal` based on carbohydrate amount and nearby insulin injections.

## Analysis tools

- **`compute_metrics.py`** – compute average insulin sensitivity, carbohydrate ratio and absorption by time of day. Insulin sensitivity is reported in mmol/L per unit. Accepts optional `--start` and `--end` dates (`YYYY-MM-DD`).
- **`verify_time_consistency.py`** – check that timestamps in the star schema match the source tables.

## PHP helpers

- **`july7_overview.php`** – command‑line summary of meals, insulin and glucose spikes for a given date (defaults to 7 July).
- **`overview_graph.php`** – web page showing daily glucose, meals, insulin and calculated insulin‑on‑board (IOB) using Chart.js.
- **`list_meal_entries.php`** – output all meal entries from the `treatments` table as JSON.

Additional scripts such as `entries.py` and `mongodb.py` provide simple examples for connecting to MongoDB or examining collection schemas. The repository also contains a sample database dump in `nillabg.sql`.

