"""Read-only: inspect key CAIR-related tables in clinic DB."""
from __future__ import annotations

import os
import sys

import pyodbc
from dotenv import load_dotenv

load_dotenv()


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


def print_columns(cur, table):
    cur.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
        ORDER BY ORDINAL_POSITION
        """,
        table,
    )
    print(f"\n=== {table} columns ===")
    for row in cur.fetchall():
        print(f"  {row.COLUMN_NAME:35} {row.DATA_TYPE:15} len={row.CHARACTER_MAXIMUM_LENGTH}")


def sample(cur, sql, label, limit=3):
    print(f"\n=== {label} ===")
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        print(f"rows={len(rows)}")
        for row in rows[:limit]:
            print(dict(zip(cols, row)))
    except Exception as exc:
        print("ERROR:", exc)


def main():
    activation = os.getenv("DEFAULT_ACTIVATION_KEY", "20000002")
    master = connect_master()
    mcur = master.cursor()
    mcur.execute(
        """
        SELECT DatabaseServer, DatabaseUser, DatabasePassword, DatabaseName
        FROM dbo.ClinicSetup WHERE ActivationKey = ?
        """,
        activation,
    )
    c = mcur.fetchone()
    master.close()

    conn = connect_clinic(c.DatabaseServer, c.DatabaseName, c.DatabaseUser, c.DatabasePassword)
    cur = conn.cursor()

    for table in ["Patients", "EHRVaccines", "CheckInsHeader", "ServiceCodes", "EHRHeaders", "Transactions"]:
        print_columns(cur, table)

    sample(
        cur,
        """
        SELECT TOP 3 Id, AccNo, FirstName, LastName, DateOfBirth, Sex,
               HomePhone, CellPhone, Email, Address, City, State, Zip
        FROM dbo.Patients
        WHERE RecordStatusId = 1
        ORDER BY Id DESC
        """,
        "Patients sample",
    )

    sample(
        cur,
        """
        SELECT TOP 5 v.Id, v.CheckInId, v.VaccineName, v.VaccineDate, v.LotNumber,
               v.VaccineExpirationDate, v.IsVaccine, v.VaccinatorId,
               sc.Code, sc.Description, sc.CPTCode, sc.NDCNumber
        FROM dbo.EHRVaccines v
        LEFT JOIN dbo.ServiceCodes sc ON sc.Id = v.ServiceCodeId
        WHERE v.IsDeleted = 0
        ORDER BY v.Id DESC
        """,
        "EHRVaccines + ServiceCodes join",
    )

    sample(
        cur,
        """
        SELECT TOP 3 Id, CheckInDate, CheckInTime, PatientId, LocationId
        FROM dbo.CheckInsHeader
        ORDER BY Id DESC
        """,
        "CheckInsHeader sample",
    )

    sample(
        cur,
        """
        SELECT TOP 10 Code, Description, CPTCode, NDCNumber
        FROM dbo.ServiceCodes
        WHERE Description LIKE '%Vaccine%' OR Description LIKE '%vaccin%'
        ORDER BY Id
        """,
        "Vaccine ServiceCodes",
    )

    sample(
        cur,
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME='EHRVaccines'
        ORDER BY ORDINAL_POSITION
        """,
        "EHRVaccines all column names only",
        limit=50,
    )

    cur.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME='EHRVaccines'
        """
    )
    vacc_cols = {r.COLUMN_NAME for r in cur.fetchall()}
    print("\nEHRVaccines has ServiceCodeId:", "ServiceCodeId" in vacc_cols)
    print("EHRVaccines columns:", sorted(vacc_cols))

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc, file=sys.stderr)
        sys.exit(1)
