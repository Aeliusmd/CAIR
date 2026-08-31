"""Generate CAIR Test Flow PDF — project status, job flow, DB fields."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

OUTPUT = Path(__file__).resolve().parents[1] / "CAIR_Test_Flow.pdf"
MARGIN = 1.5 * cm
PAGE_W = A4[0] - 2 * MARGIN


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
        "ClaudMD / Aeliusmd &rarr; CAIR2 HL7 VXU | Sithum Dev DB | Org SF-013259",
        s["sub"],
    ))

    # 1. What we done
    story.append(Paragraph("1. What We Done", s["h1"]))
    for item in [
        "Built a Python CAIR integration that reads vaccination data from ClaudMD DB, "
        "builds HL7 VXU messages, and sends them to CAIR2 over SOAP (submitSingleMessage).",
        "Synced Sithum dev DB (ClaudMD_Development_Sithum) with QA_2 so all CAIR tables/columns match.",
        "Configured .env for Sithum dev using CLINIC_DB_* (direct clinic DB connection).",
        "Created scripts/seed_sithum_cair_test_data.py to insert test vaccines + queue rows for testing.",
        "Seeded 7 pending submissions in Sithum DB — no HL7 sent to CAIR yet.",
        "Added docs/PDFs with setup, flow, and testing steps.",
        "Org code from onboarding email is set: SF-013259. Stage SOAP URL is set.",
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
            ["3", "POST SOAP submitSingleMessage to CAIR endpoint", "soap_client.py"],
            ["4", "Parse ACK (MSA segment)", "ack_parser.py — AA / AE / AR"],
            ["5a", "ACK = AA (accept)", "SubmitStatus=1, save HL7+ACK, IsSubmitted=1"],
            ["5b", "ACK = AE or timeout (temp error)", "SubmitStatus=3, AttemptCount+1, retry later"],
            ["5c", "ACK = AR or max retries (5)", "SubmitStatus=2, save ErrorMessage"],
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

    story.append(Paragraph("CAIR SOAP Endpoints (Test vs Real)", s["h2"]))
    story.append(P(
        "<b>Test endpoint (used now):</b> Stage/onboarding URL in .env (CAIR_SOAP_URL) on "
        "<b>cdph-interop-stage.cdph.ca.gov</b> — for SF-013259 testing only; HL7 is sent here via "
        "<b>submitSingleMessage</b>. "
        "<b>Real endpoint (later):</b> Production URL on <b>cdph-interop-prod.cdph.ca.gov</b> — "
        "switch after CAIR approves go-live; same operation, different server.",
        s["bullet"],
    ))
    story.append(wrap_table(
        ["Environment", "Submission endpoint (CAIR_SOAP_URL)"],
        [
            ["Test / onboarding (now)",
             "https://cdph-interop-stage.cdph.ca.gov/services/"
             "client_Service.client_ServiceHttpSoap12Endpoint"],
            ["Production / real (after approval)",
             "https://cdph-interop-prod.cdph.ca.gov/services/"
             "client_Service.client_ServiceHttpSoap12Endpoint"],
        ],
        [0.22, 0.78],
        s,
    ))

    story.append(Paragraph("What DB We Use", s["h2"]))
    story.append(wrap_table(
        ["Item", "Value"],
        [
            ["Server", "10.103.0.211"],
            ["Database", "ClaudMD_Development_Sithum"],
            ["Tables read", "EHRVaccineThirdPartySubmissions, EHRVaccines, EHRHeaders, "
             "CheckInsHeader, Patients, ServiceCodes"],
            ["Tables updated", "EHRVaccineThirdPartySubmissions, EHRVaccines only"],
            ["Worker inserts?", "No — production worker never INSERTs (read + UPDATE only)"],
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
             "HomePhone, CellPhone, Email, Address, City, State, Zip"],
            ["CheckInsHeader", "Id (check-in), CheckInDate, CheckInTime"],
            ["EHRVaccines", "LotNumber, VaccineDate, VaccineTime, Dosage, Manufacturer, "
             "Route, BodySite, VaccineExpirationDate"],
            ["ServiceCodes", "NDCNumber, Description"],
            ["EHRHeaders", "IsPublish = 1 (filter — only published visits)"],
            [".env config", "SF-013259 in HL7 as org code (MSH-4, PID-3, RXA site, etc.)"],
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
            ["Test data in Sithum DB", "Ready"],
            ["IsPublish on test visits", "1 (ready)"],
            ["SubmitStatus (7 rows)", "0 — not sent to CAIR yet"],
            ["EHRVaccines.IsSubmitted", "0 — not sent yet"],
            ["RequestPayload", "Empty — confirms no HL7 was sent"],
            ["Worker (cair_service.py)", "Not run yet"],
        ],
        [0.38, 0.62],
        s,
    ))

    story.append(Paragraph("9. Next Steps", s["h1"]))
    for item in [
        "Run: python scripts/seed_sithum_cair_test_data.py verify",
        "Run: python cair_service.py",
        "Email CAIRDataExchange@cdph.ca.gov — request review of test submissions for org SF-013259",
    ]:
        story.append(bullet(item, s))

    story.append(PageBreak())

    # 10. HL7 example + field mapping only
    story.append(Paragraph("10. HL7 Built from This Record (Sithum DB — submission Id 7)", s["h1"]))
    story.append(Preformatted(
        "MSH|^~\\&|ClaudMD|SF-013259||CAIR2|...|VXU^V04^VXU_V04|...|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|SF-013259\n"
        "PID|1||100031^^^SF-013259^MR||TEST^KEVIN...|20030314|F|...|ADDRESS 1*^^MAYFAIR^NY^12302...\n"
        " |^PRN^PH^^^123^1323123~^NET^Internet^sakvith@aeliusmd.com~^PRN^CP^^^213^1231231|...\n"
        "PD1||||||||||||Y|||||\n"
        "ORC|RE||1622^SF-013259|1622^SF-013259|...\n"
        "RXA|0|1|20260816||58160082152^^NDC|0.5|mL^^UCUM|...|^^^SF-013259|...|LOT-CAIR-TEST-003|...\n"
        "OBX|1|CE|64994-7^...|1|V01^Not VFC eligible^HL70064|...|20260816",
        s["code"],
    ))

    story.append(Paragraph("Each field — where it comes from", s["h2"]))
    story.append(wrap_table(
        ["HL7 part", "Field", "Where it comes from"],
        [
            ["MSH", "ClaudMD", ".env / code — sending application name"],
            ["MSH", "SF-013259", ".env SENDING_FACILITY_ID — your CAIR org code"],
            ["MSH", "CAIR2", ".env RECEIVING_FACILITY — California registry"],
            ["MSH", "VXU^V04^VXU_V04", "Fixed — vaccination update message type"],
            ["MSH", "P", ".env PROCESSING_ID — P = production/training mode"],
            ["MSH", "AL | AL", "Fixed — always accept ack (per CAIR email)"],
            ["MSH", "Z22^CDCPHINVS", "Fixed — immunization message profile"],
            ["MSH", "SF-013259 (MSH-22)", ".env RESPONSIBLE_ORG_ID — site that gave vaccine"],
            ["PID", "100031^^^SF-013259^MR", "Patients.AccountNumber + org code SF-013259"],
            ["PID", "TEST^KEVIN", "Patients.LastName + Patients.FirstName"],
            ["PID", "20030314", "Patients.DateOfBirth"],
            ["PID", "F", "Patients.GenderId (2 = Female)"],
            ["PID", "ADDRESS 1*^^MAYFAIR^NY^12302", "Patients.Address1, City, State, ZipCode"],
            ["PID", "^PRN^PH^^^123^1323123", "Patients.HomePhone — home phone in PID-13"],
            ["PID", "^NET^Internet^sakvith@aeliusmd.com", "Patients.Email — email in PID-13"],
            ["PID", "^PRN^CP^^^213^1231231", "Patients.CellPhone — cell phone in PID-13"],
            ["PD1", "Y", "Default in code — protection indicator"],
            ["ORC", "RE", "Fixed — replace/update order"],
            ["ORC", "1622^SF-013259", "EHRVaccines.CheckInId (= CheckInsHeader.Id) + org code"],
            ["RXA", "20260816", "EHRVaccines.VaccineDate — vaccination date"],
            ["RXA", "58160082152^^NDC", "ServiceCodes.NDCNumber — vaccine product code"],
            ["RXA", "0.5 | mL^^UCUM", "EHRVaccines.Dosage — dose amount and unit"],
            ["RXA", "^^^SF-013259", ".env RESPONSIBLE_ORG_ID — where shot was given"],
            ["RXA", "LOT-CAIR-TEST-003", "EHRVaccines.LotNumber — vaccine lot number"],
            ["OBX", "64994-7^Vaccine funding...", "Fixed — VFC eligibility observation code"],
            ["OBX", "V01^Not VFC eligible", "Default in code — not VFC eligible"],
            ["OBX", "20260816", "EHRVaccines.VaccineDate — observation date"],
        ],
        [0.12, 0.38, 0.50],
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
