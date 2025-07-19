# CGM Data Tools

This repository contains various scripts for processing continuous glucose monitor (CGM) and treatment data stored in MySQL.

## Cleaning Insulin Records

Use `cleanup_insulin.py` to remove insulin doses of 1 unit or less that occur within five minutes of another injection. Set the database connection environment variables (``MYSQLHOST``, ``MYSQLUSER``, ``MYSQLPW``, and ``MYSQLDB``) then run:

```bash
python cleanup_insulin.py
```
