"""Read-only deeper exploration of ClaudMD_QA_Setup."""
from __future__ import annotations

import os
import sys

import pyodbc
from dotenv import load_dotenv

load_dotenv()


def connect():
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};SERVER={os.getenv('MASTER_DB_SERVER')};"
        f"DATABASE={os.getenv('MASTER_DB_NAME')};UID={os.getenv('MASTER_DB_USER')};"
        f"PWD={os.getenv('MASTER_DB_PASSWORD')};TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=20)


def main() -> None:
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
    )
    tables = cur.fetchall()
    print("ALL_TABLES:")
    for schema, name in tables:
        cur.execute(
            """
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            """,
            schema,
            name,
        )
        col_count = cur.fetchone()[0]
        print(f"  {schema}.{name} ({col_count} columns)")

    for schema, name in tables:
        print(f"\n=== {schema}.{name} ===")
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
            print(f"  {col[0]:40} {col[1]:15} len={col[2]} null={col[3]}")

        try:
            cur.execute(f"SELECT TOP 5 * FROM [{schema}].[{name}]")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            print(f"  SAMPLE_ROWS ({len(rows)}):")
            for row in rows:
                print("   ", dict(zip(cols, row)))
        except Exception as exc:
            print(f"  SAMPLE_ERROR: {exc}")

    # Search for activation key references
    print("\n=== ACTIVATION_KEY SEARCH ===")
    activation = os.getenv("DEFAULT_ACTIVATION_KEY", "20000002")
    for schema, name in tables:
        cur.execute(
            """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            """,
            schema,
            name,
        )
        cols = [r[0] for r in cur.fetchall()]
        for col in cols:
            if any(k in col.lower() for k in ("activ", "clinic", "db", "server", "connection", "database")):
                print(f"  candidate: {schema}.{name}.{col}")

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc, file=sys.stderr)
        sys.exit(1)
