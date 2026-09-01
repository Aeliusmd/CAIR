"""Fill Modification column where Developer Comments ask open questions."""
from __future__ import annotations

import os

import openpyxl
from dotenv import load_dotenv

load_dotenv()

PATH = r"e:\Chamodya\CAIR\Required Fields mapping with DB 2-11-2021_Modified (2).xlsx"
OUT_PATH = r"e:\Chamodya\CAIR\Required Fields mapping with DB 2-11-2021_Modified (2)_updated.xlsx"

# Modification text only for rows where Developer Comments raise a question or need a decision.
# Researched against: cair emails.txt sample HL7, CAIR onboarding (SF-013259), ClaudMD schema.
MODIFICATIONS: dict[str, str] = {
    "MSH-6": "Use CAIR2 per CAIR sample HL7 (not CAIRLO). Config: RECEIVING_FACILITY=CAIR2.",
    "MSH-15": "Confirmed: send AL (not ER). CAIR sample uses AL|AL.",
    "MSH-16": "Confirmed: send AL (not ER). CAIR sample uses AL|AL.",
    "PID-3-1.4": (
        "Use CAIR org code SF-013259 as assigning authority (CAIR sample: "
        "AC10293^^^CA0012345^MR). Not the EHR app name."
    ),
    "PID-3-1.5": "Use MR per CAIR sample HL7 (Medical Record Number), not PI.",
    "PID-8": "Map ClaudMD GenderId: 1=M, 2=F, 3/Other=U. Implemented in worker.",
    "PID-10.1": (
        "Map to CDC CDCREC race code if Patients has race field; "
        "CAIR sample: 2106-3^^CDCREC. No race column mapped yet — EMR to confirm source."
    ),
    "PID-13": (
        "REQUIRED per CAIR email — at least one of home phone, cell, or email. "
        "DB: Patients.HomePhone, CellPhone, Email. Do not leave empty."
    ),
    "PID-22-1": (
        "Map to CDC CDCREC ethnicity code if available; "
        "CAIR sample: 2186-5^^CDCREC. EMR to confirm source column."
    ),
    "PD1-12": (
        "No DB column today. CAIR sample uses N (data can be shared). "
        "Y = lock from other providers. Default N unless EMR adds consent field."
    ),
    "PD1-13": (
        "Use EHRVaccines.VaccineDate (or visit date) when PD1-12 has no DB source. "
        "CAIR sample: 20260810."
    ),
    "RXA-3": (
        "Use EHRVaccines.VaccineDate + VaccineTime when set; "
        "else CheckInsHeader.CheckInDate + CheckInTime."
    ),
    "RXA-5": (
        "ClaudMD: ServiceCodes.NDCNumber (join via EHRVaccines.ServiceCodeId). "
        "CVX: add ServiceCodes.CvxCode (not in DB yet). CAIR accepts CVX or NDC, not both."
    ),
    "RXA-6": (
        "ClaudMD: EHRVaccines.Dosage. If unknown send 999 with blank RXA-7 per CAIR rule."
    ),
    "RXA-15": "ClaudMD: EHRVaccines.LotNumber. Required when RXA-9=00.",
    "OBX-1": "Confirmed: 1 per CAIR sample HL7.",
    "OBX-5.1": "Confirmed: V01 (Not VFC eligible). Do not leave blank — CAIR sample uses V01.",
    "OBX-11": "Confirmed: F (Final) per CAIR sample HL7.",
}


def main() -> None:
    wb = openpyxl.load_workbook(PATH)
    ws = wb["Sheet1"]
    updated = 0
    for row in range(2, ws.max_row + 1):
        seg = (ws.cell(row, 1).value or "").strip()
        dev = (ws.cell(row, 7).value or "").strip()
        if not dev or seg not in MODIFICATIONS:
            continue
        existing = (ws.cell(row, 9).value or "").strip()
        if existing and seg != "RXA-15":
            continue
        ws.cell(row, 9).value = MODIFICATIONS[seg]
        updated += 1
    wb.save(OUT_PATH)
    print(f"Updated {updated} Modification cells -> {OUT_PATH}")


if __name__ == "__main__":
    main()
