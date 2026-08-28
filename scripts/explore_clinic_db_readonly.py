"""Read-only: resolve activation key clinic DB and explore vaccination tables."""
from __future__ import annotations

import os
import sys

import pyodbc
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = (
    "patient", "vaccin", "immun", "checkin", "checked", "charge", "service",
    "lot", "ndc", "cvx", "mvx", "visit", "injection", "medication",
)


def connect_master():
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    return pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={os.getenv('MASTER_DB_SERVER')};"
        f"DATABASE={os.getenv('MASTER_DB_NAME')};UID={os.getenv('MASTER_DB_USER')};"
        f"PWD={os.getenv('MASTER_DB_PASSWORD')};TrustServerCertificate=yes;",
        timeout=20,
    )


def connect_clinic(server, database, user, password):
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    return pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;",
        timeout=20,
    )


def list_tables(cur):
    cur.execute(
        """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
    )
    return cur.fetchall()


def print_columns(cur, schema, name):
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
    print(f"\nCOLUMNS {schema}.{name}:")
    for col in cur.fetchall():
        print(f"  {col[0]:40} {col[1]:15} len={col[2]} null={col[3]}")


def main() -> None:
    activation = os.getenv("DEFAULT_ACTIVATION_KEY", "20000002")
    master = connect_master()
    mcur = master.cursor()
    mcur.execute(
        """
        SELECT ClinicID, ClinicName, DatabaseServer, DatabaseUser,
               DatabasePassword, DatabaseName, Active, ActivationKey
        FROM dbo.ClinicSetup
        WHERE ActivationKey = ?
        """,
        activation,
    )
    clinic = mcur.fetchone()
    if not clinic:
        print("NO_CLINIC for ActivationKey:", activation)
        mcur.execute(
            "SELECT ClinicID, ClinicName, ActivationKey, Active, DatabaseName FROM dbo.ClinicSetup ORDER BY ClinicID"
        )
        print("AVAILABLE_CLINICS:")
        for row in mcur.fetchall():
            print(f"  {row.ClinicID:5} key={row.ActivationKey} active={row.Active} db={row.DatabaseName}")
        master.close()
        return

    print("CLINIC_FOUND:")
    print(f"  ClinicID={clinic.ClinicID}")
    print(f"  ClinicName={clinic.ClinicName}")
    print(f"  DatabaseServer={clinic.DatabaseServer}")
    print(f"  DatabaseName={clinic.DatabaseName}")
    print(f"  Active={clinic.Active}")
    print(f"  ActivationKey={clinic.ActivationKey}")

    clinic_conn = connect_clinic(
        clinic.DatabaseServer,
        clinic.DatabaseName,
        clinic.DatabaseUser,
        clinic.DatabasePassword,
    )
    ccur = clinic_conn.cursor()
    ccur.execute("SELECT DB_NAME()")
    print("CLINIC_DB:", ccur.fetchone()[0])

    tables = list_tables(ccur)
    print("CLINIC_TOTAL_TABLES:", len(tables))

    matched = [(s, t) for s, t in tables if any(k in t.lower() for k in KEYWORDS)]
    print("MATCHED_TABLES:", len(matched))
    for schema, name in matched:
        print(f"  {schema}.{name}")

    priority_names = [
        "patient", "checked_in", "checkin", "vaccination", "vaccinations",
        "charge_rec_detail", "charge_rec", "servicecodes", "service_codes",
        "servicemaster", "service_master", "immunization",
    ]
    for target in priority_names:
        for schema, name in tables:
            if name.lower() == target:
                print_columns(ccur, schema, name)

    # Fuzzy search for vaccination-related columns anywhere
    print("\nCOLUMN_SEARCH (vaccin/ndc/cvx/lot/checkin):")
    ccur.execute(
        """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE LOWER(COLUMN_NAME) LIKE '%vaccin%'
           OR LOWER(COLUMN_NAME) LIKE '%immun%'
           OR LOWER(COLUMN_NAME) LIKE '%ndc%'
           OR LOWER(COLUMN_NAME) LIKE '%cvx%'
           OR LOWER(COLUMN_NAME) LIKE '%mvx%'
           OR LOWER(COLUMN_NAME) LIKE '%lot%'
           OR LOWER(COLUMN_NAME) LIKE '%checkin%'
           OR LOWER(COLUMN_NAME) LIKE '%acc_no%'
        ORDER BY TABLE_NAME, COLUMN_NAME
        """
    )
    for row in ccur.fetchall():
        print(f"  {row.TABLE_NAME}.{row.COLUMN_NAME} ({row.DATA_TYPE})")

    master.close()
    clinic_conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc, file=sys.stderr)
        sys.exit(1)
