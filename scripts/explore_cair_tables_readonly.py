"""Read-only: EHRHeaders, EHRVaccines, EHRVaccineThirdPartySubmissions schema."""
from __future__ import annotations

import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()


def clinic_conn():
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    master = pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={os.getenv('MASTER_DB_SERVER')};"
        f"DATABASE={os.getenv('MASTER_DB_NAME')};UID={os.getenv('MASTER_DB_USER')};"
        f"PWD={os.getenv('MASTER_DB_PASSWORD')};TrustServerCertificate=yes;"
    )
    row = master.cursor().execute(
        "SELECT DatabaseServer, DatabaseUser, DatabasePassword, DatabaseName "
        "FROM dbo.ClinicSetup WHERE ActivationKey = ?",
        os.getenv("DEFAULT_ACTIVATION_KEY", "20000002"),
    ).fetchone()
    master.close()
    return pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={row.DatabaseServer};DATABASE={row.DatabaseName};"
        f"UID={row.DatabaseUser};PWD={row.DatabasePassword};TrustServerCertificate=yes;"
    )


def print_cols(cur, table):
    print(f"\n=== {table} columns ===")
    cur.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
        ORDER BY ORDINAL_POSITION
        """,
        table,
    )
    for r in cur.fetchall():
        print(f"  {r.COLUMN_NAME:40} {r.DATA_TYPE:15} null={r.IS_NULLABLE}")


def sample(cur, sql, label, n=5):
    print(f"\n=== {label} ===")
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        print(f"rows={len(rows)}")
        for row in rows[:n]:
            print(dict(zip(cols, row)))
    except Exception as e:
        print("ERROR:", e)


def main():
    conn = clinic_conn()
    cur = conn.cursor()

    for t in ["EHRHeaders", "EHRVaccines", "EHRVaccineThirdPartySubmissions"]:
        print_cols(cur, t)

    sample(
        cur,
        """
        SELECT TOP 5 h.Id, h.CheckinId, h.IsPublish, h.ProviderId, h.IsDeleted,
               COUNT(v.Id) AS vaccine_count
        FROM dbo.EHRHeaders h
        LEFT JOIN dbo.EHRVaccines v ON v.CheckInId = h.CheckinId AND v.IsDeleted = 0
        WHERE h.IsPublish = 1 AND h.IsDeleted = 0
        GROUP BY h.Id, h.CheckinId, h.IsPublish, h.ProviderId, h.IsDeleted
        ORDER BY h.Id DESC
        """,
        "EHRHeaders IsPublish=1 with vaccine counts",
    )

    sample(
        cur,
        """
        SELECT TOP 10 *
        FROM dbo.EHRVaccineThirdPartySubmissions
        ORDER BY 1 DESC
        """,
        "EHRVaccineThirdPartySubmissions all columns",
    )

    sample(
        cur,
        """
        SELECT TOP 5 s.*, v.CheckInId, v.VaccineName, v.IsVaccine
        FROM dbo.EHRVaccineThirdPartySubmissions s
        LEFT JOIN dbo.EHRVaccines v ON v.Id = s.EHRVaccineId
        ORDER BY s.Id DESC
        """,
        "Submissions joined to vaccines",
    )

    conn.close()


if __name__ == "__main__":
    main()
