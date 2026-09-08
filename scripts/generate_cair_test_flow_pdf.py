"""Generate CAIR Test Flow PDF — project status, job flow, DB fields + live HL7.

Reads one EHRVaccineThirdPartySubmissions row (prefer Id=7) and rebuilds HL7
with vxu_builder so the PDF matches the current code. DB access is read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "CAIR_Test_Flow.pdf"
MARGIN = 1.5 * cm
PAGE_W = A4[0] - 2 * MARGIN
PREFERRED_SUBMISSION_ID = 7


def S():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "t", parent=base["Title"], fontSize=20, leading=26,
            textColor=colors.HexColor("#1a365d"), spaceAfter=8,
        ),
        "sub": ParagraphStyle(
            "s", parent=base["Normal"], fontSize=11, leading=14,
            textColor=colors.HexColor("#4a5568"), spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=13, leading=17,
            spaceBefore=12, spaceAfter=6, textColor=colors.white,
            backColor=colors.HexColor("#2b6cb0"), borderPadding=(5, 7, 5, 7),
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=11, leading=14,
            spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#2b6cb0"),
        ),
        "bullet": ParagraphStyle(
            "bu", parent=base["Normal"], fontSize=10, leading=14,
            leftIndent=12, spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "c", parent=base["Code"], fontName="Courier", fontSize=8.5,
            leading=11, backColor=colors.HexColor("#f7fafc"),
            borderPadding=6, spaceAfter=8,
        ),
        "th": ParagraphStyle(
            "th", parent=base["Normal"], fontSize=9, leading=12,
            textColor=colors.white, fontName="Helvetica-Bold",
        ),
        "td": ParagraphStyle(
            "td", parent=base["Normal"], fontSize=8.5, leading=12,
            fontName="Helvetica",
        ),
    }


def P(text: str, style) -> Paragraph:
    return Paragraph(str(text).replace("\n", "<br/>"), style)


def bullet(text: str, styles) -> Paragraph:
    return P(f"&bull; {text}", styles["bullet"])


def xml_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def load_live_sample():
    """Read-only: load preferred submission + build current HL7."""
    from cair_integration.config import build_direct_clinic_config, get_settings
    from cair_integration.hl7.vxu_builder import build_vxu_message
    from cair_integration.repository.cair_submission_repository import (
        CairSubmissionRepository,
    )

    settings = get_settings()
    clinic = build_direct_clinic_config(settings)
    if not clinic or not settings.clinic_db_connection:
        return None

    repo = CairSubmissionRepository(settings.clinic_db_connection, clinic)
    with repo._connect() as conn:
        rows = conn.execute(
            """
            SELECT s.Id, s.SubmitStatus, s.AttemptCount,
                   LEFT(ISNULL(s.ErrorMessage, ''), 200) AS Err,
                   v.Id AS VaccineId, v.CheckInId, v.LotNumber, v.Dosage,
                   v.VaccineDate, v.VaccineExpirationDate,
                   p.AccountNumber, p.FirstName, p.LastName, p.DateOfBirth,
                   p.GenderId, p.Address1, p.City, p.State, p.ZipCode,
                   p.HomePhone, p.CellPhone, p.Email,
                   sc.NDCNumber, sc.Description AS VaccineDesc,
                   pr.NationalProviderIdentifier AS NPI,
                   pr.FirstName AS ProvFirst, pr.LastName AS ProvLast
            FROM dbo.EHRVaccineThirdPartySubmissions s
            JOIN dbo.EHRVaccines v ON v.Id = s.EHRVaccineId
            JOIN dbo.CheckInsHeader ci ON ci.Id = v.CheckInId
            JOIN dbo.Patients p ON p.Id = ci.PatientId
            LEFT JOIN dbo.ServiceCodes sc ON sc.Id = v.ServiceCodeId
            LEFT JOIN dbo.Providers pr ON pr.Id = ci.ProviderId
            ORDER BY s.Id
            """
        ).fetchall()

    if not rows:
        return None

    chosen = next((r for r in rows if r.Id == PREFERRED_SUBMISSION_ID), rows[0])
    payload = repo.load_vxu_payload(int(chosen.Id))
    control_id = f"DOC-TEST-SUBMISSION-{chosen.Id}"
    hl7 = build_vxu_message(payload, message_control_id=control_id)
    return {
        "settings": settings,
        "clinic": clinic,
        "rows": rows,
        "chosen": chosen,
        "payload": payload,
        "hl7": hl7,
        "control_id": control_id,
    }


def wrap_table(headers: list[str], rows: list[list[str]], col_fracs: list[float], styles):
    widths = [PAGE_W * f for f in col_fracs]
    data = [[P(h, styles["th"]) for h in headers]]
    for row in rows:
        data.append([P(c, styles["td"]) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build():
    s = S()
    story = []

    story.append(Paragraph("CAIR Test Flow", s["title"]))
    story.append(Paragraph(
        "ClaudMD / Aeliusmd &rarr; CAIR2 HL7 VXU | Sithum Dev DB | Vendor Org SF-013259 | "
        "Updated Sep 2026",
        s["sub"],
    ))

    # 1. What we done
    story.append(Paragraph("1. What We Done", s["h1"]))
    for item in [
        "Built a Python CAIR integration that reads vaccination data from ClaudMD DB, "
        "builds HL7 VXU messages, and sends them to CAIR2 over SOAP (submitSingleMessage).",
        "Synced Sithum dev DB (ClaudMD_Development_Sithum) with QA_2 so all CAIR tables/columns match.",
        "Configured .env for Sithum dev using CLINIC_DB_* (direct clinic DB connection).",
        "Created scripts/seed_sithum_cair_test_data.py and scripts/retry_submission.py for testing.",
        "Seeded 7 test submissions in Sithum DB; live sends to CAIR onboarding endpoint completed.",
        "Fixed SOAP client to SOAP 1.2 per CAIR WSDL (resolved HTTP 500: SOAP11 binding disabled).",
        "Received SOAP login for SF-013259; credentials set in .env and login verified (HTTP 200).",
        "Updated HL7 builder from CAIR ACK errors: race/ethnicity (DataGroups), address sanitize, "
        "provider NPI, dashed NDC, PD1=N, OBX funding source, MSH-22/RXA-11.4 clinic site org.",
        "Updated Excel Modification column in Required Fields mapping workbook for implemented fields.",
        "Confirmed clinic site org for MSH-22 / RXA-11.4: SF-012218 (PROVIDER_ORG_ID). "
        "Vendor SF-013259 and sample CA0054321 were rejected; SF-012218 accepted (no org blocking error).",
        "Mapped provider professional suffix (ORC-12.21 / RXA-10.21): prefer Providers.Degree; "
        "if Degree empty, use Title only when it is a short credential (e.g. MD).",
        "Latest ACK for submission <b>3</b> is <b>MSA|AA</b> (success) — only informational RXA-6 amount note remains.",
    ]:
        story.append(bullet(item, s))

    # 2. Background job & workers
    story.append(Paragraph("2. How Background Job Runs", s["h1"]))
    for item in [
        "Run <b>python cair_service.py</b> — one long-running process for all clinics.",
        "Every 5 minutes it wakes up, checks for pending work, processes a batch, then sleeps again.",
        "In dev (Sithum): connects directly to one clinic DB from CLINIC_DB_*.",
        "In QA/prod: reads ClinicSetup from master DB, then connects to each active clinic DB.",
        "For each pending row: read DB &rarr; build HL7 &rarr; send SOAP &rarr; update status in the same table.",
        "Up to 3 clinics can be processed in parallel inside that one process (WORKER_POOL_SIZE=3).",
    ]:
        story.append(bullet(item, s))

    story.append(Spacer(1, 6))
    story.append(Preformatted(
        "cair_service.py  (every 5 min)\n"
        "    |\n"
        "    +-- Dev:  CLINIC_DB_*  ->  ClaudMD_Development_Sithum\n"
        "    +-- QA:   Master DB  ->  ClinicSetup  ->  each clinic DB\n"
        "    |\n"
        "    Find SubmitStatus = 0 or 3  AND  EHRHeaders.IsPublish = 1\n"
        "    |\n"
        "    Build HL7 VXU  ->  SOAP submitSingleMessage  ->  CAIR2\n"
        "    |\n"
        "    UPDATE EHRVaccineThirdPartySubmissions + EHRVaccines",
        s["code"],
    ))

    story.append(Paragraph("2.1 How Workers Work (3 Layers)", s["h2"]))
    story.append(wrap_table(
        ["Layer", "File", "Role"],
        [
            ["1 — Scheduler", "cair_service.py",
             "Starts once, runs forever. Every SCHEDULER_INTERVAL_SECONDS (300s = 5 min) "
             "calls coordinator.run_once(), then sleeps."],
            ["2 — Coordinator", "worker/coordinator.py (CairCoordinator)",
             "Finds clinics with pending work. Dispatches each clinic to a thread "
             "in ThreadPoolExecutor (WORKER_POOL_SIZE=3)."],
            ["3 — Processor", "worker/processor.py (SubmissionProcessor)",
             "Per clinic: loads up to WORKER_BATCH_SIZE (100) pending rows, "
             "processes each submission one by one."],
        ],
        [0.14, 0.30, 0.56],
        s,
    ))
    story.append(Paragraph(
        "<b>One background job, not one per clinic.</b> A single cair_service.py process handles "
        "all clinics. Inside it, up to 3 clinic batches run in parallel threads.",
        s["bullet"],
    ))

    story.append(Paragraph("2.2 Each Run Cycle (coordinator.run_once)", s["h2"]))
    story.append(Preformatted(
        "cair_service.py\n"
        "      |\n"
        "CairCoordinator.run_once()\n"
        "      |\n"
        "  [Dev]  CLINIC_DB_* -> check has_eligible_work() -> 1 clinic\n"
        "  [QA]   Master DB -> ClinicSetup (Active=1) -> check each clinic\n"
        "      |\n"
        "ThreadPoolExecutor (max 3 workers)\n"
        "   /        |        \\\n"
        "Clinic A   Clinic B   Clinic C   (only clinics with pending rows)\n"
        "  batch      batch      batch",
        s["code"],
    ))

    story.append(Paragraph("2.3 Per Clinic Batch (process_clinic_batch)", s["h2"]))
    story.append(wrap_table(
        ["Step", "What happens", "DB / code"],
        [
            ["1", "Connect to clinic DB", "CairSubmissionRepository"],
            ["2", "SELECT up to 100 rows: SubmitStatus=0 or 3, IsPublish=1",
             "get_eligible_submissions()"],
            ["3", "Set SubmitStatus = 4 (PROCESSING) on selected rows",
             "claim_submissions()"],
            ["4", "For each row — process_submission()", "SubmissionProcessor"],
        ],
        [0.08, 0.50, 0.42],
        s,
    ))

    story.append(Paragraph("2.4 Per Submission (process_submission)", s["h2"]))
    story.append(wrap_table(
        ["Step", "Action", "Result"],
        [
            ["1", "Load patient + vaccine from DB (JOIN Patients, EHRVaccines, etc.)",
             "VxuPayload"],
            ["2", "Build HL7 VXU message", "vxu_builder.py"],
            ["3", "POST SOAP 1.2 submitSingleMessage (username, password, facilityID, hl7Message)",
             "soap_client.py"],
            ["4", "Parse ACK (MSA segment)", "ack_parser.py — AA / AE / AR"],
            ["5a", "ACK = AA (accept)", "SubmitStatus=1, save HL7+ACK, IsSubmitted=1"],
            ["5b", "HTTP error, ACK = AE, or timeout (temp error)", "SubmitStatus=3, AttemptCount+1, retry later"],
            ["5c", "Missing SOAP credentials or ACK = AR / max retries (5)", "SubmitStatus=2, save ErrorMessage"],
        ],
        [0.08, 0.52, 0.40],
        s,
    ))

    story.append(Paragraph("2.5 Retry Logic", s["h2"]))
    story.append(wrap_table(
        ["Attempt", "Wait before retry", "After 5 failures"],
        [
            ["1", "5 minutes", ""],
            ["2", "15 minutes", ""],
            ["3", "30 minutes", ""],
            ["4", "60 minutes", ""],
            ["5", "120 minutes", "Mark FAILED (SubmitStatus = 2)"],
        ],
        [0.20, 0.40, 0.40],
        s,
    ))
    story.append(bullet(
        "Rows with SubmitStatus=3 (RETRY) are picked up again after the wait period on the next run cycle.",
        s,
    ))

    story.append(Paragraph("2.6 Worker Config (.env)", s["h2"]))
    story.append(wrap_table(
        ["Setting", "Default", "Purpose"],
        [
            ["SCHEDULER_INTERVAL_SECONDS", "300", "Seconds between each run cycle (5 min)"],
            ["WORKER_POOL_SIZE", "3", "Max clinics processed in parallel"],
            ["WORKER_BATCH_SIZE", "100", "Max submissions per clinic per cycle"],
            ["MAX_RETRY_ATTEMPTS", "5", "Retries before marking FAILED"],
        ],
        [0.38, 0.14, 0.48],
        s,
    ))

    story.append(PageBreak())
    story.append(Paragraph("3. CAIR Endpoints &amp; DB (Sithum Dev Now)", s["h1"]))

    story.append(Paragraph("CAIR SOAP Endpoints (Onboarding vs Production)", s["h2"]))
    story.append(P(
        "<b>Onboarding / stage (used now):</b> URL in .env (CAIR_SOAP_URL) on "
        "<b>cdph-interop-stage.cdph.ca.gov</b> — for SF-013259 testing only; HL7 is sent via "
        "<b>SOAP 1.2 submitSingleMessage</b>. "
        "<b>Production (later):</b> URL on <b>cdph-interop-prod.cdph.ca.gov</b> — "
        "switch after CAIR approves go-live.",
        s["bullet"],
    ))
    story.append(wrap_table(
        ["Environment", "Submission endpoint (CAIR_SOAP_URL)"],
        [
            ["Onboarding / stage (now)",
             "https://cdph-interop-stage.cdph.ca.gov/services/"
             "client_Service.client_ServiceHttpSoap12Endpoint"],
            ["Production (after approval)",
             "https://cdph-interop-prod.cdph.ca.gov/services/"
             "client_Service.client_ServiceHttpSoap12Endpoint"],
        ],
        [0.22, 0.78],
        s,
    ))
    story.append(Paragraph("SOAP 1.2 envelope (per WSDL)", s["h2"]))
    story.append(wrap_table(
        ["Item", "Value"],
        [
            ["WSDL (reference)", "https://cdph-interop-stage.cdph.ca.gov/CASTG-WS/IISService?WSDL"],
            ["SOAP version", "1.2 (Soap12Endpoint — SOAP 1.1 returns HTTP 500)"],
            ["Namespace", "urn:cdc:iisb:2011"],
            ["SOAP action", "urn:cdc:iisb:2011:submitSingleMessage"],
            ["Body fields", "username, password, facilityID (SF-013259), hl7Message"],
            [".env credentials", "CAIR_SOAP_USERNAME / CAIR_SOAP_PASSWORD — set and verified"],
            ["SOAP facilityID", "SF-013259 = vendor/integration org (same as MSH-4)"],
        ],
        [0.30, 0.70],
        s,
    ))

    story.append(Paragraph("Two CAIR org codes (important)", s["h2"]))
    story.append(wrap_table(
        ["Field", "What it means", "Our value"],
        [
            ["SOAP facilityID / MSH-4", "Vendor / integration org (who sends)",
             "SF-013259 — verified"],
            ["MSH-22 / RXA-11.4", "Clinic site org (where vaccine was given)",
             "SF-012218 — PROVIDER_ORG_ID (accepted by CAIR)"],
        ],
        [0.28, 0.40, 0.32],
        s,
    ))
    story.append(bullet(
        "Tested MSH-22 values: SF-013259 rejected (&ldquo;cannot be a vendor&rdquo;); "
        "CA0054321 rejected (sample doc only); <b>SF-012218 accepted</b> — org blocking error cleared.",
        s,
    ))

    story.append(Paragraph("What DB We Use", s["h2"]))
    story.append(wrap_table(
        ["Item", "Value"],
        [
            ["Server", "10.103.0.211"],
            ["Database", "ClaudMD_Development_Sithum"],
            ["Tables read", "EHRVaccineThirdPartySubmissions, EHRVaccines, EHRHeaders, "
             "CheckInsHeader, Patients, ServiceCodes, Providers, DataGroups"],
            ["Tables updated", "EHRVaccineThirdPartySubmissions, EHRVaccines only"],
            ["Worker inserts?", "No — production worker never INSERTs (read + UPDATE only)"],
            ["MSH-22 source now", ".env PROVIDER_ORG_ID=SF-012218 (not in DB yet). "
             "Locations has internal Id only — longer term store CairOrgCode per location."],
        ],
        [0.28, 0.72],
        s,
    ))

    story.append(PageBreak())

    # 4. Fields sent
    story.append(Paragraph("4. What Fields We Send (HL7 from DB)", s["h1"]))
    story.append(wrap_table(
        ["Source table", "Columns used in HL7"],
        [
            ["Patients", "AccountNumber, FirstName, LastName, DOB, GenderId, "
             "HomePhone, CellPhone, Email, Address1, City, State, Zip, RaceId, EthnicityId"],
            ["DataGroups", "Race / ethnicity Description &rarr; CDCREC codes (PID-10, PID-22)"],
            ["CheckInsHeader", "Id (check-in), CheckInDate, CheckInTime, ProviderId, LocationId"],
            ["Providers", "NationalProviderIdentifier, FirstName, LastName (ORC-12 / RXA-10)"],
            ["EHRVaccines", "LotNumber, VaccineDate, VaccineTime, Dosage, Manufacturer, "
             "Route, BodySite, VaccineExpirationDate"],
            ["ServiceCodes", "NDCNumber (dashed in HL7), Description"],
            ["EHRHeaders", "IsPublish = 1 (filter — only published visits)"],
            [".env config", "SENDING_FACILITY_ID=SF-013259 (MSH-4); "
             "PROVIDER_ORG_ID=SF-012218 (MSH-22 / RXA-11.4)"],
        ],
        [0.26, 0.74],
        s,
    ))

    # 5. Fields updated
    story.append(Paragraph("5. What Fields We Update After Send", s["h1"]))
    story.append(Paragraph("EHRVaccineThirdPartySubmissions", s["h2"]))
    story.append(wrap_table(
        ["Column", "Purpose"],
        [
            ["SubmitStatus", "0 pending &rarr; 4 processing &rarr; 1 success / 2 failed / 3 retry"],
            ["RequestPayload", "HL7 message sent"],
            ["ResponsePayload", "CAIR ACK response"],
            ["SubmittedDateTime", "When CAIR accepted"],
            ["LastAttemptDateTime", "Last send attempt time"],
            ["AttemptCount", "Retry counter"],
            ["ErrorMessage", "Error text on fail/retry"],
            ["ExternalReferenceId", "MSH-10 message control ID"],
        ],
        [0.32, 0.68],
        s,
    ))
    story.append(Paragraph("EHRVaccines", s["h2"]))
    story.append(bullet("<b>IsSubmitted = 1</b> on success only.", s))

    # 6. IsPublish
    story.append(Paragraph("6. IsPublish = 1 — What It Means", s["h1"]))
    story.append(bullet(
        "<b>EHRHeaders.IsPublish</b> = whether the visit/chart is published in ClaudMD "
        "(provider finalized the EHR).", s,
    ))
    story.append(bullet(
        "<b>IsPublish = 1</b> &rarr; visit is ready; CAIR worker may pick up vaccines for that check-in.", s,
    ))
    story.append(bullet(
        "<b>IsPublish = 0</b> &rarr; visit not published; worker skips it even if a queue row exists.", s,
    ))
    story.append(bullet(
        "<b>It does NOT mean &ldquo;sent to CAIR.&rdquo;</b> It only means the visit is ready to send.", s,
    ))

    # 7. CAIR sent or not
    story.append(Paragraph("7. DB Columns — Was CAIR Sent or Not?", s["h1"]))
    story.append(Paragraph("Main column: EHRVaccineThirdPartySubmissions.SubmitStatus", s["h2"]))
    story.append(wrap_table(
        ["Value", "Meaning"],
        [
            ["0", "Not sent yet (pending)"],
            ["1", "Sent successfully to CAIR"],
            ["2", "Failed permanently"],
            ["3", "Failed temporarily — will retry"],
            ["4", "Currently sending"],
        ],
        [0.15, 0.85],
        s,
    ))
    story.append(Paragraph("Also on EHRVaccineThirdPartySubmissions:", s["h2"]))
    for item in [
        "RequestPayload — HL7 sent (empty = not sent yet)",
        "ResponsePayload — CAIR ACK response",
        "SubmittedDateTime — when CAIR accepted it",
        "ErrorMessage — error if failed",
    ]:
        story.append(bullet(item, s))

    story.append(Paragraph("Secondary flag: EHRVaccines.IsSubmitted", s["h2"]))
    story.append(bullet("0 or NULL &rarr; vaccine not reported to CAIR yet.", s))
    story.append(bullet("1 &rarr; vaccine successfully sent to CAIR (worker sets on success).", s))

    story.append(Spacer(1, 6))
    story.append(Preformatted(
        "EHRHeaders.IsPublish = 1          ->  Visit is ready (gate before send)\n"
        "        +\n"
        "EHRVaccineThirdPartySubmissions.SubmitStatus = 0  ->  Queued for CAIR\n"
        "        |\n"
        "   Worker sends HL7\n"
        "        |\n"
        "SubmitStatus = 1  +  EHRVaccines.IsSubmitted = 1  ->  Sent to CAIR",
        s["code"],
    ))
    story.append(Paragraph(
        "<b>Quick rule:</b> check <b>SubmitStatus</b> on EHRVaccineThirdPartySubmissions — "
        "that is the main &ldquo;CAIR sent or not&rdquo; column.",
        s["bullet"],
    ))

    # 8. Status now
    story.append(Paragraph("8. Status Right Now", s["h1"]))
    story.append(wrap_table(
        ["Check", "Current state"],
        [
            ["Test data in Sithum DB", "Ready (7 submissions seeded)"],
            ["SOAP envelope", "Fixed — SOAP 1.2 (HTTP 500 resolved)"],
            ["CAIR SOAP credentials", "Received and set — login works (HTTP 200)"],
            ["Vendor org (MSH-4 / SOAP)", "SF-013259 — working"],
            ["Clinic site org (MSH-22 / RXA-11.4)", "SF-012218 — accepted (org blocker cleared)"],
            ["Best test record", "Submission 3 — Oak Pereraa (SubmitStatus=1 SUCCESS, MSA|AA)"],
            ["HL7 field fixes", "MSH-22/ORC-12.9/ORC-12.21/RXA-10.21 OK; PID-10/11/22 fixed in DB"],
            ["Tried MSH-22 = SF-013259", "Rejected — cannot be a vendor"],
            ["Tried MSH-22 = CA0054321", "Rejected — sample doc code only"],
            ["Tried MSH-22 = SF-012218", "Accepted — no MSH-22 / RXA-11.4 org error"],
            ["Latest ACK (submission 3)", "MSA|AA — success; only informational RXA-6 amount note"],
            ["Remaining ACK issues", "None blocking — RXA-6 info only (optional to chase)"],
            ["PID-10 / PID-11 / PID-22", "Fixed in DB — cleared from ACK"],
            ["ORC-12.9 assigning authority", "Fixed — not in ACK"],
            ["ORC-12.21 / RXA-10.21 degree",
             "Fixed — Degree empty, Title=MD → sent MD; cleared from ACK"],
            ["ACK = AA (success)", "Yes — submission 3 (2026-09-07)"],
            ["DB CairOrgCode?", "Not on Locations yet — using .env PROVIDER_ORG_ID=SF-012218"],
        ],
        [0.40, 0.60],
        s,
    ))

    story.append(Paragraph("9. Next Steps", s["h1"]))
    for item in [
        "Keep .env: SENDING_FACILITY_ID=SF-013259 and PROVIDER_ORG_ID=SF-012218.",
        "Ask CAIR to review test submissions (especially submission 3 MSA|AA) before production go-live.",
        "Longer term: EMR adds Locations.CairOrgCode and map "
        "CheckInsHeader.LocationId &rarr; MSH-22 / RXA-11.4 per site (replace .env for multi-clinic).",
        "Optional: investigate informational RXA-6 amount warning (0.5 + mL^mL^UCUM still returns Info).",
    ]:
        story.append(bullet(item, s))

    story.append(PageBreak())

    # 10. HL7 field mapping (with required / status / sent vs should)
    story.append(Paragraph("10. Each Field — Source, Required, Status, Sent vs Should Send", s["h1"]))
    story.append(P(
        "Based on current code + latest successful submission <b>3</b> (Oak Pereraa, MSA|AA). "
        "See Required legend below. "
        "<b>Sent / should send</b> uses latest tested values where applicable.",
        s["bullet"],
    ))
    story.append(Paragraph("Required column legend", s["h2"]))
    story.append(wrap_table(
        ["Code", "Meaning"],
        [
            ["R", "Required — must send a value"],
            ["RE", "Required but may be empty — field present; value can be blank"],
            ["C", "Conditional — required only in some cases (e.g. if shot was given / RXA-9=00)"],
            ["O", "Optional — not required by CAIR (we may still send it)"],
        ],
        [0.12, 0.88],
        s,
    ))
    story.append(Paragraph("Field mapping", s["h2"]))
    story.append(P(
        "<b>Kind</b> = where the value comes from: "
        "<b>DB</b> (ClaudMD table.column), <b>.env</b> (config), "
        "<b>Fixed</b> (hard-coded in HL7 builder), or <b>Code</b> (default / map in code). "
        "Link path for doctor: CheckInsHeader.ProviderId &rarr; Providers.",
        s["bullet"],
    ))
    story.append(wrap_table(
        ["HL7", "Kind", "Source (table.field or .env)", "Req", "Status", "Sent / should"],
        [
            ["MSH-3", "Fixed", "Code — sending application name ClaudMD",
             "O", "OK", "ClaudMD / keep"],
            ["MSH-4", ".env", ".env SENDING_FACILITY_ID (= SF-013259 vendor org)",
             "R", "OK", "SF-013259 / keep (not for MSH-22)"],
            ["MSH-6", ".env", ".env RECEIVING_FACILITY",
             "R", "OK", "CAIR2 / keep"],
            ["MSH-9", "Fixed", "Code — VXU^V04^VXU_V04",
             "R", "OK", "keep"],
            ["MSH-11", ".env", ".env PROCESSING_ID",
             "R", "OK", "P / keep"],
            ["MSH-15/16", "Fixed", "Code — AL|AL",
             "R", "OK", "AL|AL / keep"],
            ["MSH-21", "Fixed", "Code — Z22^CDCPHINVS",
             "RE", "OK", "keep"],
            ["MSH-22", ".env", ".env PROVIDER_ORG_ID (= SF-012218 clinic site). "
             "Later: Locations.CairOrgCode",
             "RE", "OK", "SF-012218 / keep"],
            ["PID-3", "DB+.env", "DB Patients.AccountNumber + .env SENDING_FACILITY_ID "
             "(…^^^SF-013259^MR)",
             "R", "OK", "MRN^^^SF-013259^MR / keep"],
            ["PID-5", "DB", "DB Patients.LastName, Patients.FirstName "
             "(+ Initials if middle)",
             "R", "OK", "Last^First / keep"],
            ["PID-7", "DB", "DB Patients.DateOfBirth",
             "R", "OK", "YYYYMMDD / keep"],
            ["PID-8", "DB+Code", "DB Patients.GenderId → code map "
             "(1=M, 2=F, 3=U, 4=X)",
             "R", "OK", "M/F/U/X / keep"],
            ["PID-10", "DB+Code", "DB Patients.RaceId → DataGroups.Description "
             "→ CDCREC map (cdc_codes)",
             "RE", "OK", "2106-3^^CDCREC when RaceId set"],
            ["PID-11", "DB", "DB Patients.Address1, City, State, ZipCode "
             "(skip placeholder address)",
             "RE", "OK", "street^^city^ST^zip^^H"],
            ["PID-13", "DB", "DB Patients.HomePhone, CellPhone, Email",
             "RE", "OK", "at least one contact"],
            ["PID-22", "DB+Code", "DB Patients.EthnicityId → DataGroups.Description "
             "→ CDCREC map",
             "RE", "OK", "2186-5^^CDCREC when set"],
            ["PD1-12", "Code", "Code default N (no DB consent column yet)",
             "R", "OK", "N / keep"],
            ["PD1-13", "DB", "DB EHRVaccines.VaccineDate "
             "(else CheckInsHeader.CheckInDate)",
             "C", "OK", "vaccine date / keep"],
            ["ORC-1", "Fixed", "Code — RE",
             "R", "OK", "RE / keep"],
            ["ORC-3 / ORC-4", "DB+.env", "DB EHRVaccines.CheckInId "
             "(= CheckInsHeader.Id) + .env SENDING_FACILITY_ID",
             "RE", "OK", "checkinId^SF-013259 / keep"],
            ["ORC-12", "DB", "DB via CheckInsHeader.ProviderId → Providers: "
             "NationalProviderIdentifier, LastName, FirstName; "
             ".21 from Degree (else short Title e.g. MD). "
             ".9 fixed NPPES&amp;OID&amp;ISO in code",
             "RE", "OK AA", "…NPI^^^^^^^^MD (Degree empty, Title=MD)"],
            ["RXA-3", "DB", "DB EHRVaccines.VaccineDate + VaccineTime "
             "(else CheckInsHeader.CheckInDate/Time)",
             "R", "OK", "YYYYMMDD / keep"],
            ["RXA-5", "DB", "DB ServiceCodes.NDCNumber "
             "(via EHRVaccines.ServiceCodeId); dashed in code",
             "R", "OK", "58160-0821-11^^NDC / keep"],
            ["RXA-6", "DB", "DB EHRVaccines.Dosage",
             "R", "OK*", "0.5 (CAIR may Info-warn)"],
            ["RXA-7", "Code", "Code — mL^mL^UCUM when dose ≠ 999; else blank",
             "C", "OK", "mL^mL^UCUM / keep"],
            ["RXA-9", "Fixed", "Code — 00^NEW IMMUNIZATION RECORD^NIP001",
             "R", "OK", "keep"],
            ["RXA-10", "DB", "Same as ORC-12 — Providers via "
             "CheckInsHeader.ProviderId (NPI, name, Degree/Title → .21)",
             "C", "OK AA", "same …^^^^^^^^MD"],
            ["RXA-11.4", ".env", ".env PROVIDER_ORG_ID (same as MSH-22)",
             "C/R", "OK", "^^^SF-012218 / keep"],
            ["RXA-15", "DB", "DB EHRVaccines.LotNumber",
             "C/R", "OK", "lot / keep"],
            ["RXA-20/21", "Fixed", "Code — CP|A",
             "C/R", "OK", "CP|A / keep"],
            ["OBX VFC", "Code", "Code default V01^Not VFC eligible^HL70064 "
             "(no DB VFC column yet)",
             "R", "OK", "V01 / keep"],
            ["OBX funding", "Code", "Code default PHC70^Private^CDCPHINVS "
             "(2nd OBX)",
             "RE", "OK", "PHC70 / keep"],
        ],
        [0.12, 0.10, 0.30, 0.08, 0.10, 0.30],
        s,
    ))
    story.append(bullet(
        "<b>AA achieved</b> on submission 3. Professional suffix (.21): "
        "use <b>Providers.Degree</b> if set; if Degree is empty, use <b>Providers.Title</b> "
        "only when it is a short credential (MD, NP, RN, …). "
        "Example: Degree empty + Title=MD &rarr; HL7 ends with <b>^^^^^^^^MD</b>.",
        s,
    ))

    story.append(PageBreak())
    story.append(Paragraph("11. Latest Test — Submission 2 (after PID DB fixes)", s["h1"]))
    story.append(P(
        "Patient <b>97</b> (BAGYA ADIKARI) updated in DB: Address1=123 Main St, "
        "City/State/Zip=Los Angeles/CA/90210, RaceId=1082 (White), EthnicityId=1084 "
        "(Not Hispanic or Latino). Resent submission <b>2</b>. "
        "MSH-4 = <b>SF-013259</b>, MSH-22 / RXA-11.4 = <b>SF-012218</b>. "
        "SOAP HTTP 200. ACK = <b>MSA|AE</b>. "
        "PID-10 / PID-11 / PID-22 / ORC-12.9 <b>cleared</b> from ACK.",
        s["bullet"],
    ))

    story.append(Paragraph("11.1 HL7 VXU message sent", s["h2"]))
    story.append(Preformatted(
        "MSH|^~\\&|ClaudMD|SF-013259||CAIR2|20260908060823+0000||VXU^V04^VXU_V04|"
        "59eabeb3-a0b3-4174-a7a8-9a6c2d06c991|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|SF-012218\n"
        "PID|1||100064^^^SF-013259^MR||BAGYA ^ADIKARI^^^^^^L||20000714|F||2106-3^^CDCREC|"
        "123 Main St^^Los Angeles^CA^90210^^H||^PRN^CP^^^123^4663421||ENG^English^HL70296|"
        "||||||2186-5^^CDCREC||N||||||\n"
        "PD1||||||||||||N|20260816||||\n"
        "ORC|RE||1595^SF-013259|1595^SF-013259||||||||"
        "1093461063^noor^brian^^^^^^NPPES&2.16.840.1.113883.4.6&ISO^^^^NPI|||||\n"
        "RXA|0|1|20260816||58160-0842-52^^NDC|0.5|mL^^UCUM||00^NEW IMMUNIZATION RECORD^NIP001|"
        "1093461063^noor^brian^^^^^^NPPES&2.16.840.1.113883.4.6&ISO^^^^NPI|"
        "^^^SF-012218||||LOT-CAIR-TEST-001|||||CP|A|20260908060823+0000\n"
        "OBX|1|CE|64994-7^Vaccine funding program eligibility category^LN|1|"
        "V01^Not VFC eligible^HL70064|||||F||||20260816\n"
        "OBX|2|CE|30963-3^Vaccine funding source^LN|1|PHC70^Private^CDCPHINVS|||||F||||20260816",
        s["code"],
    ))

    story.append(Paragraph("11.2 CAIR ACK", s["h2"]))
    story.append(Preformatted(
        "MSA|AE|59eabeb3-a0b3-4174-a7a8-9a6c2d06c991\n"
        "ERR||RXA^1^10^21|...|W|...|Administering Provider degree missing from RXA-10.21.\n"
        "ERR||ORC^1^12^21|...|W|...|Ordering Provider degree missing from ORC-12.21.\n"
        "ERR||RXA^1|...|I|...|Incoming Immunization already exists in the system.",
        s["code"],
    ))

    story.append(Paragraph("11.3 ACK items", s["h2"]))
    story.append(wrap_table(
        ["Field", "Sev.", "What we sent", "How should send", "Source / what to do"],
        [
            ["ORC-12.9", "OK",
             "NPPES&amp;2.16.840.1.113883.4.6&amp;ISO",
             "Same (keep)",
             "Code — fixed"],
            ["MSH-22 / RXA-11.4", "OK",
             "SF-012218",
             "SF-012218 (keep)",
             ".env PROVIDER_ORG_ID"],
            ["PID-11.1", "OK / Fixed",
             "123 Main St^^Los Angeles^CA^90210^^H",
             "Same (keep)",
             "DB — Patients.Address1/City/State/Zip updated"],
            ["PID-10", "OK / Fixed",
             "2106-3^^CDCREC",
             "Same (keep)",
             "DB — RaceId=1082 (White)"],
            ["PID-22", "OK / Fixed",
             "2186-5^^CDCREC",
             "Same (keep)",
             "DB — EthnicityId=1084 (Not Hispanic or Latino)"],
            ["RXA-10.21", "Warn",
             "1093461063^noor^brian^^^^^^NPPES&amp;...&amp;ISO^^^^NPI  (no .21)",
             "...NPI^^^^^^^^MD  (title = MD/NP/RN/PA/DO)",
             "DB — Providers degree; map to .21"],
            ["ORC-12.21", "Warn",
             "Same provider — no .21",
             "...NPI^^^^^^^^MD  (same title)",
             "DB — same Providers degree; map to .21"],
            ["RXA", "Info",
             "Retry of same immunization",
             "Use a new vaccine/submission for clean AA test",
             "CAIR — dose already stored from earlier send"],
        ],
        [0.11, 0.10, 0.25, 0.26, 0.28],
        s,
    ))
    story.append(bullet(
        "<b>Title</b> = credential after name (MD, NP, RN, PA, DO), e.g. brian noor, <b>MD</b>.",
        s,
    ))
    story.append(bullet(
        "Next: add provider degree in DB + HL7 map, then send a <b>new</b> submission for ACK = <b>AA</b>.",
        s,
    ))

    story.append(PageBreak())
    story.append(Paragraph("12. Latest Test — New Message (Submission 3) provider degree + AA", s["h1"]))
    story.append(P(
        "Sent a <b>new</b> submission (Id <b>3</b>) — not a retry of #2/#6/#7. "
        "Patient Oak Pereraa, NDC <b>58160-0821-11</b>, provider brian noor "
        "(NPI 1093461063). "
        "Providers row: <b>Degree</b> empty, <b>Title</b>=MD — so HL7 ORC-12.21 / RXA-10.21 "
        "sent <b>MD</b> (prefer Degree; else short Title credential only). "
        "Dosage <b>0.5</b> with unit <b>mL^mL^UCUM</b>. "
        "MSH-4 = <b>SF-013259</b>, MSH-22 / RXA-11.4 = <b>SF-012218</b>. "
        "SOAP HTTP 200. ACK = <b>MSA|AA</b>. "
        "Sithum DB: <b>SubmitStatus=1 (SUCCESS)</b>.",
        s["bullet"],
    ))

    story.append(Paragraph("12.1 HL7 VXU message sent (RXA / provider focus)", s["h2"]))
    story.append(Preformatted(
        "MSH|^~\\&|ClaudMD|SF-013259||CAIR2|...||VXU^V04^VXU_V04|"
        "e53c9776-48dd-431a-82bf-ffb6cc8ee086|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|SF-012218\n"
        "PID|1||100075^^^SF-013259^MR||Pereraa^Oak...||...|...||2106-3^^CDCREC|"
        "123 Oak Street^^Springfield^IL^62701^^H||...|||||||2186-5^^CDCREC||...\n"
        "PD1||||||||||||N|...\n"
        "ORC|RE||1649^SF-013259|1649^SF-013259||||||||"
        "1093461063^noor^brian^^^^^^NPPES&2.16.840.1.113883.4.6&ISO^^^^NPI^^^^^^^^MD|||||\n"
        "RXA|0|1|20260816||58160-0821-11^^NDC|0.5|mL^mL^UCUM||00^NEW IMMUNIZATION RECORD^NIP001|"
        "1093461063^noor^brian^^^^^^NPPES&2.16.840.1.113883.4.6&ISO^^^^NPI^^^^^^^^MD|"
        "^^^SF-012218||||LOT-CAIR-TEST-002|20270630||||CP|A|...\n"
        "OBX|1|CE|64994-7^...|1|V01^Not VFC eligible^HL70064|...\n"
        "OBX|2|CE|30963-3^...|1|PHC70^Private^CDCPHINVS|...",
        s["code"],
    ))

    story.append(Paragraph("12.2 CAIR ACK", s["h2"]))
    story.append(Preformatted(
        "MSA|AA|e53c9776-48dd-431a-82bf-ffb6cc8ee086\n"
        "ERR||RXA^1^6|...|I|...|Informational: RXA-6 Administered amount is invalid.",
        s["code"],
    ))

    story.append(Paragraph("12.3 ACK items", s["h2"]))
    story.append(wrap_table(
        ["Field", "Sev.", "What we sent", "How should send", "Source / note"],
        [
            ["ORC-12.21 / RXA-10.21", "OK",
             "...NPI^^^^^^^^MD",
             "Send one suffix: Degree first, else short Title",
             "From Providers table for the visit doctor. "
             "Rule: (1) if Degree filled → use it; "
             "(2) else if Title is short credential (MD/NP/RN…) → use Title; "
             "(3) else blank. "
             "This test: Degree empty + Title=MD → sent MD"],
            ["RXA-6", "Info",
             "0.5",
             "0.5 (keep) or 999 if unknown",
             "Informational only — does not block AA"],
            ["RXA-7", "OK",
             "mL^mL^UCUM",
             "mL^mL^UCUM (CAIR PDF)",
             "Code"],
            ["RXA-5", "OK",
             "58160-0821-11^^NDC",
             "Same (keep)",
             "ServiceCodes.NDCNumber dashed 5-4-2"],
            ["MSH-22 / RXA-11.4", "OK",
             "SF-012218",
             "Same (keep)",
             ".env PROVIDER_ORG_ID"],
            ["ORC-12.9", "OK",
             "NPPES&amp;OID&amp;ISO",
             "Same (keep)",
             "Code — assigning authority"],
            ["MSA", "AA",
             "MSA|AA",
             "MSA|AA (success)",
             "Sithum SubmitStatus=1 SUCCESS"],
        ],
        [0.14, 0.08, 0.22, 0.24, 0.32],
        s,
    ))
    story.append(bullet(
        "<b>How we take Degree and Title (for ORC-12.21 and RXA-10.21):</b> "
        "Both come from the visit doctor in <b>Providers</b>. "
        "We send only <b>one</b> value after the NPI: "
        "(1) use <b>Degree</b> if it has a value; "
        "(2) if Degree is empty, use <b>Title</b> only when Title is a short credential "
        "like MD, DO, NP, RN, PA (not a long job name like Physical Therapist); "
        "(3) if neither works, leave .21 empty. "
        "Example this test — brian noor: Degree empty, Title=MD &rarr; HL7 "
        "<b>...NPI^^^^^^^^MD</b> in both ORC-12 and RXA-10.",
        s,
    ))
    story.append(bullet(
        "That MD suffix cleared the ORC-12.21 / RXA-10.21 warnings. "
        "First clean <b>MSA|AA</b> on a new dose. "
        "RXA-6 info remains non-blocking.",
        s,
    ))

    return story


def main():
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    doc.build(build())
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
