"""Compare Development DB vs QA_2 clinic DB for CAIR-required tables. Read-only compare."""
from __future__ import annotations

import os
import sys

import pyodbc

# CAIR app tables (clinic DB) — only sync what exists in QA_2 reference
CAIR_CLINIC_TABLES = [
    "EHRHeaders",
    "EHRVaccines",
    "EHRVaccineThirdPartySubmissions",
    "CheckInsHeader",
    "Patients",
    "ServiceCodes",
]

DEV = dict(
    server="10.103.0.211",
    database="ClaudMD_Development_Sithum",
    user="testuser",
    password="Test@123",
    driver="ODBC Driver 17 for SQL Server",
)

QA_MASTER = dict(
    server="10.103.0.201",
    database="ClaudMD_QA_Setup",
    user="testuser",
    password="Test@123",
    driver="ODBC Driver 17 for SQL Server",
)

QA2_ACTIVATION_KEY = "20000002"


def conn_str(cfg: dict, database: str | None = None) -> str:
    db = database or cfg["database"]
    return (
        f"DRIVER={{{cfg['driver']}}};SERVER={cfg['server']};DATABASE={db};"
        f"UID={cfg['user']};PWD={cfg['password']};TrustServerCertificate=yes;"
    )


def connect(cfg: dict, database: str | None = None):
    return pyodbc.connect(conn_str(cfg, database), timeout=30)


def table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?",
        table,
    )
    return cur.fetchone() is not None


def list_tables(cur) -> set[str]:
    cur.execute(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA='dbo' AND TABLE_TYPE='BASE TABLE'"
    )
    return {r.TABLE_NAME for r in cur.fetchall()}


def get_columns(cur, table: str) -> list[tuple]:
    cur.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
               NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
        ORDER BY ORDINAL_POSITION
        """,
        table,
    )
    return [tuple(r) for r in cur.fetchall()]


def get_create_table_ddl(cur, table: str) -> str:
    """Get approximate CREATE TABLE from sys tables (for scripting)."""
    cur.execute(
        """
        SELECT
            c.name AS col_name,
            t.name AS type_name,
            c.max_length,
            c.precision,
            c.scale,
            c.is_nullable,
            c.is_identity,
            dc.definition AS default_def
        FROM sys.columns c
        JOIN sys.types t ON c.user_type_id = t.user_type_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        WHERE c.object_id = OBJECT_ID(?)
        ORDER BY c.column_id
        """,
        f"dbo.{table}",
    )
    rows = cur.fetchall()
    if not rows:
        return ""
    parts = []
    for r in rows:
        col = f"[{r.col_name}] "
        if r.type_name in ("nvarchar", "varchar", "nchar", "char"):
            if r.max_length == -1:
                col += f"{r.type_name}(MAX)"
            elif r.type_name.startswith("n"):
                col += f"{r.type_name}({r.max_length // 2})"
            else:
                col += f"{r.type_name}({r.max_length})"
        elif r.type_name in ("decimal", "numeric"):
            col += f"{r.type_name}({r.precision},{r.scale})"
        elif r.type_name == "datetimeoffset":
            col += "datetimeoffset(7)"
        elif r.type_name == "datetime2":
            col += "datetime2(7)"
        elif r.type_name == "time":
            col += "time(7)"
        else:
            col += r.type_name
        if r.is_identity:
            col += " IDENTITY(1,1)"
        col += " NULL" if r.is_nullable else " NOT NULL"
        if r.default_def:
            col += f" DEFAULT {r.default_def}"
        parts.append(col)
    return f"CREATE TABLE [dbo].[{table}] (\n  " + ",\n  ".join(parts) + "\n);"


def resolve_qa2_clinic():
    with connect(QA_MASTER) as conn:
        row = conn.cursor().execute(
            """
            SELECT DatabaseServer, DatabaseName, DatabaseUser, DatabasePassword, ClinicName
            FROM dbo.ClinicSetup WHERE ActivationKey = ?
            """,
            QA2_ACTIVATION_KEY,
        ).fetchone()
    if not row:
        raise RuntimeError(f"QA clinic not found for key {QA2_ACTIVATION_KEY}")
    return row


def main():
    print("=== Resolving QA_2 clinic from QA master ===")
    qa2 = resolve_qa2_clinic()
    print(f"  QA_2 clinic: {qa2.ClinicName} @ {qa2.DatabaseServer}/{qa2.DatabaseName}")

    qa2_cfg = {
        **QA_MASTER,
        "server": qa2.DatabaseServer,
        "database": qa2.DatabaseName,
        "user": qa2.DatabaseUser,
        "password": qa2.DatabasePassword,
    }

    print("\n=== Development DB ===")
    print(f"  {DEV['server']}/{DEV['database']}")

    with connect(DEV) as dev_conn, connect(qa2_cfg) as qa2_conn:
        dev_cur = dev_conn.cursor()
        qa2_cur = qa2_conn.cursor()

        dev_tables = list_tables(dev_cur)
        qa2_tables = list_tables(qa2_cur)
        print(f"\nDev table count: {len(dev_tables)}")
        print(f"QA_2 table count: {len(qa2_tables)}")

        print("\n=== CAIR tables status ===")
        missing_in_dev = []
        present_both = []
        missing_in_qa2 = []

        for t in CAIR_CLINIC_TABLES:
            in_dev = t in dev_tables
            in_qa2 = t in qa2_tables
            status = []
            if in_dev:
                status.append("DEV")
            if in_qa2:
                status.append("QA2")
            print(f"  {t:40} DEV={'Y' if in_dev else 'N'}  QA2={'Y' if in_qa2 else 'N'}")
            if in_qa2 and not in_dev:
                missing_in_dev.append(t)
            if in_dev and in_qa2:
                present_both.append(t)
            if in_dev and not in_qa2:
                missing_in_qa2.append(t)

        if missing_in_qa2:
            print("\nWARNING: These exist in DEV but NOT in QA_2 (will NOT add to dev):")
            for t in missing_in_qa2:
                print(f"  - {t}")

        print(f"\nTables to CREATE in Development (exist in QA_2, missing in Dev): {missing_in_dev}")

        for t in missing_in_dev:
            print(f"\n--- DDL from QA_2: {t} ---")
            ddl = get_create_table_ddl(qa2_cur, t)
            print(ddl[:3000] if len(ddl) > 3000 else ddl)

        # Column diff for tables present in both
        for t in present_both:
            dev_cols = {c[0] for c in get_columns(dev_cur, t)}
            qa2_cols = {c[0] for c in get_columns(qa2_cur, t)}
            only_qa2 = qa2_cols - dev_cols
            only_dev = dev_cols - qa2_cols
            if only_qa2 or only_dev:
                print(f"\n--- Column diff: {t} ---")
                if only_qa2:
                    print(f"  In QA_2 only (may need ALTER): {sorted(only_qa2)}")
                if only_dev:
                    print(f"  In DEV only (extra, not in QA_2): {sorted(only_dev)}")

        # Check ClinicSetup on dev master - dev DB might BE the clinic DB
        print("\n=== Is Development DB a master or clinic DB? ===")
        print(f"  ClinicSetup in dev: {'Y' if 'ClinicSetup' in dev_tables else 'N'}")
        print(f"  EHRVaccineThirdPartySubmissions in dev: {'Y' if 'EHRVaccineThirdPartySubmissions' in dev_tables else 'N'}")

    return missing_in_dev


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", type(e).__name__, e, file=sys.stderr)
        sys.exit(1)
