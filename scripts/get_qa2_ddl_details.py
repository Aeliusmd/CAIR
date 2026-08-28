"""Get full DDL details from QA_2 for EHRVaccineThirdPartySubmissions and EHRVaccines.IsSubmitted."""
from __future__ import annotations

import pyodbc

QA2 = dict(
    server="10.103.0.201",
    database="ClaudMD_VCOMC_QA_2",
    user="TestUser",
    password="Test@123",
    driver="ODBC Driver 17 for SQL Server",
)


def connect():
    return pyodbc.connect(
        f"DRIVER={{{QA2['driver']}}};SERVER={QA2['server']};DATABASE={QA2['database']};"
        f"UID={QA2['user']};PWD={QA2['password']};TrustServerCertificate=yes;",
        timeout=30,
    )


def main():
    conn = connect()
    cur = conn.cursor()

    print("=== PK / FK / Indexes for EHRVaccineThirdPartySubmissions ===")
    cur.execute("""
        SELECT
            i.name AS index_name,
            i.is_primary_key,
            i.is_unique,
            COL_NAME(ic.object_id, ic.column_id) AS column_name
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE i.object_id = OBJECT_ID('dbo.EHRVaccineThirdPartySubmissions')
        ORDER BY i.name, ic.key_ordinal
    """)
    for r in cur.fetchall():
        print(r)

    print("\n=== Foreign keys ===")
    cur.execute("""
        SELECT
            fk.name AS fk_name,
            OBJECT_NAME(fk.parent_object_id) AS parent_table,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_col,
            OBJECT_NAME(fk.referenced_object_id) AS ref_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ref_col
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE fk.parent_object_id = OBJECT_ID('dbo.EHRVaccineThirdPartySubmissions')
    """)
    for r in cur.fetchall():
        print(r)

    print("\n=== IsSubmitted column on EHRVaccines (QA_2) ===")
    cur.execute("""
        SELECT c.name, t.name, c.max_length, c.is_nullable, dc.definition
        FROM sys.columns c
        JOIN sys.types t ON c.user_type_id = t.user_type_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        WHERE c.object_id = OBJECT_ID('dbo.EHRVaccines') AND c.name = 'IsSubmitted'
    """)
    for r in cur.fetchall():
        print(r)

    conn.close()


if __name__ == "__main__":
    main()
