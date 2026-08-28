"""Read-only schema exploration for ClaudMD_QA_Setup. No DDL/DML."""
from __future__ import annotations

import os
import sys

import pyodbc
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = (
    "patient", "vaccin", "immun", "checkin", "checked", "charge", "service",
    "cair", "clinic", "lot", "ndc", "cvx", "mvx", "visit", "appointment",
)


def connect():
    server = os.getenv("MASTER_DB_SERVER")
    database = os.getenv("MASTER_DB_NAME")
    user = os.getenv("MASTER_DB_USER")
    password = os.getenv("MASTER_DB_PASSWORD")
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    if not all([server, database, user, password]):
        raise RuntimeError("Missing DB env vars in .env")
    conn_str = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=20)


def main() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT DB_NAME()")
    print("DATABASE:", cur.fetchone()[0])

    cur.execute(
        """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
    )
    tables = cur.fetchall()
    print("TOTAL_TABLES:", len(tables))

    matched = [
        (s, t)
        for s, t in tables
        if any(k in t.lower() for k in KEYWORDS)
    ]
    print("MATCHED_TABLES:", len(matched))
    for schema, name in matched:
        print(f"  {schema}.{name}")

    priority = [
        "patient", "checked_in", "checkin", "vaccination", "charge_rec_detail",
        "servicecodes", "service_codes", "clinic", "clinic_registry",
    ]
    for target in priority:
        hits = [(s, t) for s, t in tables if t.lower() == target]
        for schema, name in hits:
            print(f"\nCOLUMNS {schema}.{name}:")
            cur.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """,
                schema,
                name,
            )
            for col in cur.fetchall():
                print(f"  {col[0]:35} {col[1]:15} len={col[2]} null={col[3]}")

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc, file=sys.stderr)
        sys.exit(1)
