"""Read-only samples: patients and actual vaccine rows."""
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
        os.getenv("DEFAULT_ACTIVATION_KEY"),
    ).fetchone()
    master.close()
    return pyodbc.connect(
        f"DRIVER={{{driver}}};SERVER={row.DatabaseServer};DATABASE={row.DatabaseName};"
        f"UID={row.DatabaseUser};PWD={row.DatabasePassword};TrustServerCertificate=yes;"
    )


def main():
    conn = clinic_conn()
    cur = conn.cursor()

    print("=== Patients sample ===")
    cur.execute(
        """
        SELECT TOP 3 Id, AccountNumber, MRN, FirstName, LastName, DateOfBirth,
               GenderId, HomePhone, CellPhone, Email, Address1, City, State, ZipCode
        FROM dbo.Patients
        WHERE IsDeleted = 0
        ORDER BY Id DESC
        """
    )
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        print(dict(zip(cols, row)))

    print("\n=== EHRVaccines where IsVaccine = 1 ===")
    cur.execute(
        """
        SELECT TOP 5
            v.Id, v.CheckInId, v.VaccineName, v.VaccineDate, v.LotNumber,
            v.Route, v.BodySite, v.Manufacturer, v.Dosage, v.IsSubmitted,
            sc.Code, sc.Description, sc.CPTCode, sc.NDCNumber
        FROM dbo.EHRVaccines v
        LEFT JOIN dbo.ServiceCodes sc ON sc.Id = v.ServiceCodeId
        WHERE v.IsDeleted = 0 AND v.IsVaccine = 1
        ORDER BY v.Id DESC
        """
    )
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print("count", len(rows))
    for row in rows:
        print(dict(zip(cols, row)))

    print("\n=== EHRVaccines counts ===")
    cur.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN IsVaccine = 1 THEN 1 ELSE 0 END) AS vaccines,
            SUM(CASE WHEN LotNumber IS NOT NULL AND LotNumber <> '' THEN 1 ELSE 0 END) AS with_lot,
            SUM(CASE WHEN Route IS NOT NULL AND Route <> '' THEN 1 ELSE 0 END) AS with_route
        FROM dbo.EHRVaccines
        WHERE IsDeleted = 0
        """
    )
    print(cur.fetchone())

    print("\n=== Vaccine ServiceCodes ===")
    cur.execute(
        """
        SELECT TOP 15 Code, Description, CPTCode, NDCNumber
        FROM dbo.ServiceCodes
        WHERE (Description LIKE '%Vaccin%' OR Description LIKE '%Hepatitis%' OR Description LIKE '%Influenza%')
          AND IsDeleted = 0
        """
    )
    for row in cur.fetchall():
        print(tuple(row))

    print("\n=== Active clinics in master ===")
    master = pyodbc.connect(
        f"DRIVER={{{os.getenv('MASTER_DB_DRIVER')}}};SERVER={os.getenv('MASTER_DB_SERVER')};"
        f"DATABASE={os.getenv('MASTER_DB_NAME')};UID={os.getenv('MASTER_DB_USER')};"
        f"PWD={os.getenv('MASTER_DB_PASSWORD')};TrustServerCertificate=yes;"
    )
    mcur = master.cursor()
    mcur.execute(
        "SELECT ClinicID, ClinicName, ActivationKey, Active, DatabaseName FROM dbo.ClinicSetup ORDER BY ClinicID"
    )
    for row in mcur.fetchall():
        print(tuple(row))
    master.close()
    conn.close()


if __name__ == "__main__":
    main()
