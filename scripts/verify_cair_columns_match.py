"""Verify CAIR-related columns match between Dev Sithum and QA_2."""
from __future__ import annotations

import pyodbc

CAIR_TABLES = [
    "EHRHeaders",
    "EHRVaccines",
    "EHRVaccineThirdPartySubmissions",
    "CheckInsHeader",
    "Patients",
    "ServiceCodes",
]

DEV = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.103.0.211;DATABASE=ClaudMD_Development_Sithum;UID=testuser;PWD=Test@123;TrustServerCertificate=yes;"
QA2 = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.103.0.201;DATABASE=ClaudMD_VCOMC_QA_2;UID=TestUser;PWD=Test@123;TrustServerCertificate=yes;"


def cols(cur, table):
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=? ORDER BY ORDINAL_POSITION",
        table,
    )
    return [r.COLUMN_NAME for r in cur.fetchall()]


def main():
    dev = pyodbc.connect(DEV, timeout=30)
    qa2 = pyodbc.connect(QA2, timeout=30)
    dc, qc = dev.cursor(), qa2.cursor()
    all_ok = True
    for t in CAIR_TABLES:
        d, q = set(cols(dc, t)), set(cols(qc, t))
        only_dev, only_qa2 = d - q, q - d
        cair_only_qa2 = {c for c in only_qa2 if c in (
            "IsSubmitted", "SubmitStatus", "EHRVaccineId", "RequestPayload",
            "ResponsePayload", "ExternalReferenceId", "LastAttemptDateTime",
            "SubmittedDateTime", "AttemptCount",
        )} | only_qa2
        status = "OK" if not only_qa2 else f"MISSING IN DEV: {sorted(only_qa2)}"
        if only_dev:
            status += f" | EXTRA IN DEV: {sorted(only_dev)}"
        if only_qa2:
            all_ok = False
        print(f"{t}: {status}")
    print("\nALL CAIR COLUMNS MATCH:" if all_ok else "\nCOLUMN GAPS REMAIN:", all_ok)
    dev.close()
    qa2.close()


if __name__ == "__main__":
    main()
