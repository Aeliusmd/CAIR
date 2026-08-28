"""Check if Sithum DB is registered in ClinicSetup."""
import pyodbc

BASE = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "UID=testuser;PWD=Test@123;TrustServerCertificate=yes;"
)


def q(conn_str, sql):
    with pyodbc.connect(conn_str, timeout=20) as conn:
        return conn.execute(sql).fetchall()


# QA master
rows = q(
    BASE + "SERVER=10.103.0.201;DATABASE=ClaudMD_QA_Setup;",
    """
    SELECT ClinicID, ClinicName, DatabaseServer, DatabaseName, ActivationKey, Active
    FROM dbo.ClinicSetup
    WHERE DatabaseName LIKE '%Sithum%' OR ClinicName LIKE '%Sithum%'
    """,
)
print("QA Setup Sithum entries:", rows)

# Databases on 211
rows = q(
    BASE + "SERVER=10.103.0.211;DATABASE=master;",
    """
    SELECT name FROM sys.databases
    WHERE name LIKE '%Sithum%' OR name LIKE '%Setup%' OR name LIKE '%ClaudMD%'
    """,
)
print("211 databases:", [r[0] for r in rows])

# Check ClinicSetup on 211 DBs
for db in [r[0] for r in rows]:
    try:
        cnt = q(
            BASE + f"SERVER=10.103.0.211;DATABASE={db};",
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='ClinicSetup'",
        )[0][0]
        if cnt:
            sithum = q(
                BASE + f"SERVER=10.103.0.211;DATABASE={db};",
                """
                SELECT ClinicID, ClinicName, DatabaseName, Active
                FROM dbo.ClinicSetup
                WHERE DatabaseName LIKE '%Sithum%'
                """,
            )
            print(f"ClinicSetup in {db}:", sithum)
    except Exception as exc:
        print(f"Skip {db}: {exc}")
