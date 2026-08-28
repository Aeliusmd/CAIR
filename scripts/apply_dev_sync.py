"""Apply CAIR schema sync to Development DB (from QA_2 reference only)."""
from __future__ import annotations

import sys
from pathlib import Path

import pyodbc

DEV = dict(
    server="10.103.0.211",
    database="ClaudMD_Development_Sithum",
    user="testuser",
    password="Test@123",
    driver="ODBC Driver 17 for SQL Server",
)

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "sync_dev_from_qa2.sql"


def connect():
    return pyodbc.connect(
        f"DRIVER={{{DEV['driver']}}};SERVER={DEV['server']};DATABASE={DEV['database']};"
        f"UID={DEV['user']};PWD={DEV['password']};TrustServerCertificate=yes;",
        autocommit=True,
        timeout=60,
    )


def run_sql_file(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    batches = [b.strip() for b in sql.split("\nGO") if b.strip()]
    cur = conn.cursor()
    for i, batch in enumerate(batches, 1):
        # Remove leading comment-only lines but keep SQL
        lines = batch.splitlines()
        sql_lines = [ln for ln in lines if not ln.strip().startswith("--")]
        executable = "\n".join(sql_lines).strip()
        if not executable:
            continue
        print(f"\n--- Batch {i} ---")
        try:
            cur.execute(executable)
            while cur.nextset():
                pass
            for row in cur.fetchall() if cur.description else []:
                print(row)
        except pyodbc.Error as e:
            print(f"ERROR in batch {i}: {e}")
            raise


def verify(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_NAME='EHRVaccineThirdPartySubmissions'"
    )
    print("\nVerify EHRVaccineThirdPartySubmissions:", "OK" if cur.fetchone() else "MISSING")

    cur.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME='EHRVaccines' AND COLUMN_NAME='IsSubmitted'"
    )
    print("Verify EHRVaccines.IsSubmitted:", "OK" if cur.fetchone() else "MISSING")


def main():
    print(f"Applying: {SQL_FILE}")
    print(f"Target: {DEV['server']}/{DEV['database']}")
    conn = connect()
    run_sql_file(conn, SQL_FILE)
    verify(conn)
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", type(e).__name__, e, file=sys.stderr)
        sys.exit(1)
