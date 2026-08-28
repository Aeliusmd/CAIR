"""Generate CAIR Quick Reference PDF — word-wrapped tables, column details."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

OUTPUT = Path(__file__).resolve().parents[1] / "CAIR_Quick_Reference.pdf"
MARGIN = 1.5 * cm
PAGE_W = A4[0] - 2 * MARGIN


def S():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=20, leading=26,
                                textColor=colors.HexColor("#1a365d"), spaceAfter=10),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=11, leading=14,
                              textColor=colors.HexColor("#4a5568"), spaceAfter=14),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=13, leading=17,
                               spaceBefore=12, spaceAfter=6, textColor=colors.white,
                               backColor=colors.HexColor("#2b6cb0"), borderPadding=(5, 7, 5, 7)),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11, leading=14,
                              spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#2b6cb0")),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=10, leading=14, spaceAfter=6),
        "bullet": ParagraphStyle("bu", parent=base["Normal"], fontSize=10, leading=14,
                                 leftIndent=12, spaceAfter=3),
        "code": ParagraphStyle("c", parent=base["Code"], fontName="Courier", fontSize=8.5,
                               leading=11, backColor=colors.HexColor("#f7fafc"),
                               borderPadding=6, spaceAfter=8),
        "th": ParagraphStyle("th", parent=base["Normal"], fontSize=9, leading=12,
                             textColor=colors.white, fontName="Helvetica-Bold"),
        "td": ParagraphStyle("td", parent=base["Normal"], fontSize=8.5, leading=12,
                             fontName="Helvetica"),
    }


def P(text: str, style) -> Paragraph:
    return Paragraph(str(text).replace("\n", "<br/>"), style)


def wrap_table(headers: list[str], rows: list[list[str]], col_fracs: list[float], styles):
    """Build table with Paragraph cells so text wraps instead of overlapping."""
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

    story.append(Paragraph("CAIR2 Integration — Quick Reference", s["title"]))
    story.append(Paragraph("ClaudMD / Aeliusmd | HL7 VXU v2.5.1 | SF-013259", s["sub"]))

    # --- 1 Architecture ---
    story.append(Paragraph("1. Architecture", s["h1"]))
    story.append(Preformatted(
        "EMR publishes visit (EHRHeaders.IsPublish = 1)\n"
        "EMR inserts EHRVaccineThirdPartySubmissions (SubmitStatus = 0)\n"
        "         |\n"
        "cair_service.py reads DB -> builds HL7 VXU -> sends SOAP -> updates status",
        s["code"],
    ))

    # --- 2 New tables? ---
    story.append(Paragraph("2. Do We Need New Tables?", s["h1"]))
    story.append(Paragraph(
        "<b>NO.</b> Use existing ClaudMD tables only. Our script does not create cair_outbox "
        "or any new table.",
        s["body"],
    ))

    # --- 3 Who inserts ---
    story.append(Paragraph("3. Who INSERTs What (Our Script Never INSERTs)", s["h1"]))
    story.append(wrap_table(
        ["Who", "Table", "When (INSERT)", "Columns inserted by EMR"],
        [
            ["ClaudMD EMR", "EHRVaccines", "Nurse saves vaccination",
             "CheckInId, ServiceCodeId, LotNumber, Dosage, VaccineDate, Manufacturer, Route, BodySite, IsVaccine"],
            ["ClaudMD EMR", "EHRHeaders", "Provider publishes visit", "CheckinId, IsPublish = 1"],
            ["ClaudMD EMR", "EHRVaccineThirdPartySubmissions", "Visit ready for CAIR",
             "EHRVaccineId, SubmitStatus = 0, AttemptCount = 0"],
            ["Our Python script", "Any table", "Never (production worker)", "No INSERT — read and UPDATE only"],
            ["Dev seed script only", "EHRVaccines + EHRVaccineThirdPartySubmissions", "Testing in Sithum DB",
             "INSERT test vaccines + queue rows — see Section 10"],
        ],
        [0.17, 0.28, 0.22, 0.33],
        s,
    ))

    # --- 4 What script does ---
    story.append(Paragraph("4. What Our Python Script Does (cair_service.py)", s["h1"]))
    story.append(wrap_table(
        ["Step", "Action", "DB operation"],
        [
            ["1", "Connect using .env — master DB (QA) or direct clinic DB (dev)", "READ ClinicSetup OR CLINIC_DB_*"],
            ["2", "Get each clinic connection string", "READ ClinicSetup columns: DatabaseServer, DatabaseName, DatabaseUser, DatabasePassword"],
            ["3", "Find pending CAIR submissions for published visits",
             "READ EHRVaccineThirdPartySubmissions WHERE SubmitStatus IN (0,3) AND EHRHeaders.IsPublish = 1"],
            ["4", "Load patient and vaccine data to build HL7",
             "READ EHRVaccines, Patients, CheckInsHeader, ServiceCodes (see Section 5)"],
            ["5", "Build HL7 VXU message", "No DB write — uses CAIR PDF spec + Excel mapping"],
            ["6", "Send to CAIR2 SOAP endpoint", "No DB write — submitSingleMessage (cair emails.txt)"],
            ["7", "On success — save result", "UPDATE EHRVaccineThirdPartySubmissions + UPDATE EHRVaccines.IsSubmitted = 1"],
            ["8", "On failure — save error", "UPDATE EHRVaccineThirdPartySubmissions (SubmitStatus, ErrorMessage, AttemptCount)"],
        ],
        [0.08, 0.42, 0.50],
        s,
    ))

    story.append(PageBreak())

    # --- 5 How script works ---
    story.append(Paragraph("5. How Our Script Works (Detailed)", s["h1"]))
    story.append(Paragraph(
        "The background service is a single Python process: <b>cair_service.py</b>. "
        "It runs continuously on a server, wakes up every 5 minutes (configurable), "
        "checks all active clinics for pending CAIR submissions, and processes them. "
        "It does not run inside ClaudMD — it is a separate background worker.",
        s["body"],
    ))

    story.append(Paragraph("5.1 Startup", s["h2"]))
    story.append(Preformatted(
        "1. Run:  python cair_service.py\n"
        "2. Load settings from .env file (DB server, CAIR SOAP URL, org code SF-013259)\n"
        "3. Create CairCoordinator\n"
        "4. Enter infinite loop — repeat every SCHEDULER_INTERVAL_SECONDS (default 300 = 5 min)",
        s["code"],
    ))

    story.append(Paragraph("5.2 Each Run Cycle (coordinator.run_once)", s["h2"]))
    story.append(Preformatted(
        "                    cair_service.py\n"
        "                          |\n"
        "              CairCoordinator.run_once()\n"
        "                          |\n"
        "         Connect to master DB OR direct clinic DB (see Section 7)\n"
        "         QA: READ ClinicSetup WHERE Active = 1\n"
        "         Dev: use CLINIC_DB_* from .env (skip ClinicSetup)\n"
        "                          |\n"
        "         For each clinic: check if pending submissions exist\n"
        "                          |\n"
        "         ThreadPoolExecutor (3 workers by default)\n"
        "              /         |         \\\n"
        "        Clinic A    Clinic B    Clinic C\n"
        "        (batch)     (batch)     (batch)",
        s["code"],
    ))

    story.append(Paragraph("5.3 Per Clinic Batch (process_clinic_batch)", s["h2"]))
    story.append(wrap_table(
        ["#", "What happens", "Python file / class"],
        [
            ["1", "Connect to clinic DB using ClinicSetup credentials", "cair_submission_repository.py"],
            ["2", "SELECT up to 100 pending submissions (SubmitStatus 0 or 3) where IsPublish=1", "CairSubmissionRepository.get_eligible_submissions()"],
            ["3", "Set SubmitStatus = 4 (PROCESSING) on selected rows", "CairSubmissionRepository.claim_submissions()"],
            ["4", "For each submission row — call process_submission()", "processor.py — SubmissionProcessor"],
        ],
        [0.06, 0.58, 0.36],
        s,
    ))

    story.append(Paragraph("5.4 Per Submission Record (process_submission)", s["h2"]))
    story.append(wrap_table(
        ["#", "Step", "What it does"],
        [
            ["1", "Load data", "JOIN EHRVaccines + Patients + CheckInsHeader + ServiceCodes + EHRHeaders"],
            ["2", "Build HL7", "vxu_builder.py creates MSH, PID, PD1, ORC, RXA, OBX segments per CAIR PDF + Excel"],
            ["3", "Send SOAP", "soap_client.py POSTs HL7 to CAIR stage/prod endpoint (submitSingleMessage)"],
            ["4", "Parse ACK", "ack_parser.py reads MSA segment: AA=accept, AE=error, AR=reject"],
            ["5a", "If AA (success)", "UPDATE submission SubmitStatus=1, save HL7+ACK, set EHRVaccines.IsSubmitted=1"],
            ["5b", "If AE (temp error)", "UPDATE SubmitStatus=3 (RETRY), increment AttemptCount, wait and retry later"],
            ["5c", "If AR or max retries", "UPDATE SubmitStatus=2 (FAILED), save ErrorMessage"],
        ],
        [0.06, 0.22, 0.72],
        s,
    ))

    story.append(Paragraph("5.5 Retry Logic", s["h2"]))
    story.append(wrap_table(
        ["Attempt", "Wait before retry", "After 5 failures"],
        [
            ["1", "5 minutes", ""],
            ["2", "15 minutes", ""],
            ["3", "30 minutes", ""],
            ["4", "60 minutes", ""],
            ["5", "120 minutes", "Mark as FAILED (SubmitStatus = 2)"],
        ],
        [0.20, 0.40, 0.40],
        s,
    ))
    story.append(Paragraph(
        "Retries are automatic. A failed row with SubmitStatus=3 is picked up again on the next run "
        "after the wait period. New pending rows (SubmitStatus=0) and retry rows share the same queue.",
        s["body"],
    ))

    story.append(Paragraph("5.6 Multi-Clinic Rules", s["h2"]))
    story.append(Paragraph("&bull; One shared worker pool (default 3 threads) — not one worker per clinic forever", s["bullet"]))
    story.append(Paragraph("&bull; Each worker handles one clinic batch (max 100 records), then moves to next clinic", s["bullet"]))
    story.append(Paragraph("&bull; Only one active batch per clinic at a time (avoids duplicate sends)", s["bullet"]))
    story.append(Paragraph("&bull; Clinics with no pending work are skipped", s["bullet"]))

    story.append(PageBreak())

    story.append(Paragraph("5.7 Script Components (File Map)", s["h2"]))
    story.append(wrap_table(
        ["File", "Role"],
        [
            ["cair_service.py", "Main entry — infinite scheduler loop"],
            ["cair_integration/config.py", "Reads .env — DB credentials, CAIR URL, batch size"],
            ["cair_integration/constants.py", "SubmitStatus values (0–4)"],
            ["worker/coordinator.py", "Finds clinics with work, dispatches to thread pool"],
            ["worker/processor.py", "Processes one submission: load -> HL7 -> send -> update"],
            ["worker/retry.py", "Calculates retry delay (exponential backoff)"],
            ["repository/cair_submission_repository.py", "All SQL READ and UPDATE queries"],
            ["hl7/vxu_builder.py", "Builds HL7 VXU message string"],
            ["cair/soap_client.py", "Sends HL7 to CAIR SOAP endpoint"],
            ["cair/ack_parser.py", "Parses CAIR ACK response (AA/AE/AR)"],
            ["demo_build_vxu.py", "Test HL7 output without database connection"],
            ["scripts/seed_sithum_cair_test_data.py", "Dev only — insert test vaccines + queue rows in Sithum DB"],
            ["run_dry_once.py", "One worker cycle — read DB, build HL7, optional dry-run"],
        ],
        [0.42, 0.58],
        s,
    ))

    story.append(Paragraph("5.8 Configuration (.env)", s["h2"]))
    story.append(Paragraph(
        "<b>Two modes:</b> QA uses <b>MASTER_DB_*</b> + ClinicSetup lookup. "
        "Development uses <b>CLINIC_DB_*</b> for a direct clinic connection (e.g. Sithum DB). "
        "When CLINIC_DB_* is set, ClinicSetup is skipped.",
        s["body"],
    ))
    story.append(wrap_table(
        ["Setting", "Example", "Purpose"],
        [
            ["APP_ENV", "development / qa", "Environment label"],
            ["CLINIC_DB_SERVER", "10.103.0.211", "Dev: direct clinic SQL Server"],
            ["CLINIC_DB_NAME", "ClaudMD_Development_Sithum", "Dev: clinic database name"],
            ["CLINIC_DB_USER / PASSWORD", "testuser / ***", "Dev: clinic DB login"],
            ["CLINIC_NAME", "Development Sithum", "Dev: display name for logs"],
            ["MASTER_DB_SERVER", "10.103.0.201", "QA: SQL Server for master DB"],
            ["MASTER_DB_NAME", "ClaudMD_QA_Setup", "QA: master database name"],
            ["DEFAULT_ACTIVATION_KEY", "20000002", "QA: clinic activation key"],
            ["CAIR_SOAP_URL", "stage endpoint", "Where to send HL7 messages"],
            ["CAIR_SOAP_USERNAME / PASSWORD", "(from CAIR onboarding)", "Required to actually send HL7"],
            ["SENDING_FACILITY_ID", "SF-013259", "CAIR org code (MSH-4)"],
            ["WORKER_BATCH_SIZE", "100", "Max submissions per clinic per run"],
            ["WORKER_POOL_SIZE", "3", "Parallel clinic workers"],
            ["SCHEDULER_INTERVAL_SECONDS", "300", "Seconds between each run cycle"],
            ["MAX_RETRY_ATTEMPTS", "5", "Retries before marking FAILED"],
        ],
        [0.32, 0.30, 0.38],
        s,
    ))

    story.append(PageBreak())

    # --- 6 Columns per table ---
    story.append(Paragraph("6. Columns Used Per Table", s["h1"]))
    story.append(Paragraph(
        "Below are the exact columns our script reads or updates in each table.",
        s["body"],
    ))

    story.append(Paragraph("ClinicSetup (Master DB — ClaudMD_QA_Setup)", s["h2"]))
    story.append(wrap_table(
        ["Column", "Used for", "Read / Write"],
        [
            ["ClinicID", "Clinic identifier", "READ"],
            ["ClinicName", "Display name", "READ"],
            ["DatabaseServer", "SQL Server host for clinic DB", "READ"],
            ["DatabaseName", "Clinic database name", "READ"],
            ["DatabaseUser", "Clinic DB login", "READ"],
            ["DatabasePassword", "Clinic DB password", "READ"],
            ["Active", "Filter Active = 1", "READ"],
            ["ActivationKey", "e.g. 20000002", "READ"],
        ],
        [0.28, 0.48, 0.24],
        s,
    ))

    story.append(Paragraph("EHRHeaders (Clinic DB)", s["h2"]))
    story.append(wrap_table(
        ["Column", "HL7 / purpose", "Read / Write"],
        [
            ["CheckinId", "Links to EHRVaccines.CheckInId", "READ"],
            ["IsPublish", "Must be 1 before CAIR send", "READ (filter)"],
            ["IsDeleted", "Must be 0", "READ (filter)"],
        ],
        [0.28, 0.48, 0.24],
        s,
    ))

    story.append(Paragraph("EHRVaccineThirdPartySubmissions (Clinic DB)", s["h2"]))
    story.append(wrap_table(
        ["Column", "Purpose", "Read / Write"],
        [
            ["Id", "Submission queue row ID", "READ"],
            ["EHRVaccineId", "FK to EHRVaccines.Id", "READ"],
            ["SubmitStatus", "0=pending, 1=success, 2=failed, 3=retry, 4=processing", "READ + UPDATE"],
            ["SubmittedDateTime", "When CAIR accepted", "UPDATE on success"],
            ["LastAttemptDateTime", "Last send attempt", "UPDATE"],
            ["AttemptCount", "Retry counter", "UPDATE"],
            ["ExternalReferenceId", "MSH-10 message control ID (GUID)", "UPDATE on success"],
            ["ErrorMessage", "CAIR error or exception text", "UPDATE on fail/retry"],
            ["RequestPayload", "HL7 VXU message sent", "UPDATE"],
            ["ResponsePayload", "CAIR ACK response", "UPDATE"],
            ["IsDeleted", "Must be 0", "READ (filter)"],
        ],
        [0.30, 0.46, 0.24],
        s,
    ))

    story.append(Paragraph("EHRVaccines (Clinic DB)", s["h2"]))
    story.append(wrap_table(
        ["Column", "HL7 field (PDF / Excel)", "Read / Write"],
        [
            ["Id", "Internal vaccine record ID", "READ"],
            ["CheckInId", "ORC-2/3 order number (Excel: checked_In.checkin_id)", "READ"],
            ["ServiceCodeId", "Join to ServiceCodes", "READ"],
            ["LotNumber", "RXA-15 substance lot number", "READ"],
            ["VaccineExpirationDate", "RXA-16 expiration date", "READ"],
            ["Dosage", "RXA-6 administered amount", "READ"],
            ["VaccineDate", "RXA-3 administration date", "READ"],
            ["VaccineTime", "RXA-3 administration time", "READ"],
            ["Manufacturer", "RXA-17 manufacturer (need MVX code)", "READ"],
            ["Route", "RXR-1 route", "READ"],
            ["BodySite", "RXR-2 injection site", "READ"],
            ["IsVaccine", "Filter IsVaccine = 1", "READ (filter)"],
            ["IsSubmitted", "Flag after CAIR success", "UPDATE = 1 on success"],
            ["IsDeleted", "Must be 0", "READ (filter)"],
        ],
        [0.28, 0.48, 0.24],
        s,
    ))

    story.append(PageBreak())

    story.append(Paragraph("CheckInsHeader (Clinic DB)", s["h2"]))
    story.append(wrap_table(
        ["Column", "HL7 field (PDF / Excel)", "Read / Write"],
        [
            ["Id", "ORC-2/3 placer/filler order number", "READ"],
            ["PatientId", "Join to Patients", "READ"],
            ["CheckInDate", "Visit date (fallback for RXA-3)", "READ"],
            ["CheckInTime", "Visit time (fallback for RXA-3)", "READ"],
            ["IsDeleted", "Must be 0", "READ (filter)"],
        ],
        [0.28, 0.48, 0.24],
        s,
    ))

    story.append(Paragraph("Patients (Clinic DB)", s["h2"]))
    story.append(wrap_table(
        ["Column", "HL7 field (PDF / Excel)", "Read / Write"],
        [
            ["AccountNumber", "PID-3 patient ID (Excel: Patient.Acc_no)", "READ"],
            ["LastName", "PID-5 patient name", "READ"],
            ["FirstName", "PID-5 patient name", "READ"],
            ["Initials", "PID-5 middle name", "READ"],
            ["DateOfBirth", "PID-7 date of birth", "READ"],
            ["GenderId", "PID-8 sex (lookup M/F/X/U)", "READ"],
            ["HomePhone", "PID-13 home phone (required per email)", "READ"],
            ["CellPhone", "PID-13 cell phone (required per email)", "READ"],
            ["Email", "PID-13 email (required per email)", "READ"],
            ["Address1", "PID-11 address", "READ"],
            ["City", "PID-11 city", "READ"],
            ["State", "PID-11 state", "READ"],
            ["ZipCode", "PID-11 zip", "READ"],
            ["IsDeleted", "Must be 0", "READ (filter)"],
        ],
        [0.28, 0.48, 0.24],
        s,
    ))

    story.append(Paragraph("ServiceCodes (Clinic DB)", s["h2"]))
    story.append(wrap_table(
        ["Column", "HL7 field (PDF / Excel)", "Read / Write"],
        [
            ["Id", "Join from EHRVaccines.ServiceCodeId", "READ"],
            ["NDCNumber", "RXA-5 vaccine code (Excel: Charge_rec_detail.NDC_number)", "READ"],
            ["Description", "RXA-5 vaccine description text", "READ"],
            ["CPTCode", "Billing only — not primary CAIR field", "READ (optional)"],
            ["CvxCode", "RXA-5 CVX code — NOT in DB yet, EMR must add", "READ (future)"],
            ["MvxCode", "RXA-17 MVX code — NOT in DB yet, EMR must add", "READ (future)"],
        ],
        [0.28, 0.48, 0.24],
        s,
    ))

    story.append(PageBreak())

    # --- 7 DB connection ---
    story.append(Paragraph("7. Database Connection", s["h1"]))

    story.append(Paragraph("7.1 QA Mode (Master DB + ClinicSetup)", s["h2"]))
    story.append(Preformatted(
        "STEP A — Master DB (from .env):\n"
        "  Server: 10.103.0.201\n"
        "  Database: ClaudMD_QA_Setup\n"
        "  READ dbo.ClinicSetup WHERE Active = 1\n"
        "\n"
        "STEP B — Clinic DB (per ClinicSetup row):\n"
        "  Example: ClaudMD_VCOMC_QA_2 (activation key 20000002)\n"
        "  READ  -> build HL7 from tables in Section 6\n"
        "  UPDATE -> EHRVaccineThirdPartySubmissions + EHRVaccines only",
        s["code"],
    ))

    story.append(Paragraph("7.2 Development Mode (Direct Clinic DB — Sithum)", s["h2"]))
    story.append(Paragraph(
        "The Sithum development database is a <b>clinic DB</b>, not registered in ClinicSetup. "
        "Set <b>CLINIC_DB_*</b> in .env and leave MASTER_DB_* commented out. "
        "CAIR-related tables were synced from QA_2 — same 6 tables and columns.",
        s["body"],
    ))
    story.append(Preformatted(
        "Direct connection (from .env):\n"
        "  Server:   10.103.0.211\n"
        "  Database: ClaudMD_Development_Sithum\n"
        "  User:     testuser\n"
        "\n"
        "Tables verified (match QA_2):\n"
        "  EHRHeaders, EHRVaccines, EHRVaccineThirdPartySubmissions,\n"
        "  CheckInsHeader, Patients, ServiceCodes",
        s["code"],
    ))

    story.append(Paragraph("SubmitStatus values (EHRVaccineThirdPartySubmissions.SubmitStatus)", s["h2"]))
    story.append(wrap_table(
        ["Value", "Name", "Set by"],
        [
            ["0", "PENDING", "EMR on INSERT"],
            ["1", "SUCCESS", "Our script on CAIR ACK = AA"],
            ["2", "FAILED", "Our script on permanent error"],
            ["3", "RETRY", "Our script on temporary error"],
            ["4", "PROCESSING", "Our script while sending"],
        ],
        [0.12, 0.28, 0.60],
        s,
    ))

    # --- 8 HL7 mapping ---
    story.append(Paragraph("8. HL7 Field Quick Map (PDF + Excel)", s["h1"]))
    story.append(wrap_table(
        ["HL7", "Source column", "Spec reference"],
        [
            ["MSH-4", ".env SENDING_FACILITY_ID = SF-013259", "CAIR PDF + onboarding email"],
            ["MSH-6", "CAIR2", "cair emails.txt sample"],
            ["MSH-9", "VXU^V04^VXU_V04", "CAIR PDF"],
            ["MSH-15/16", "AL / AL", "cair emails.txt sample"],
            ["PID-3", "Patients.AccountNumber", "Excel mapping"],
            ["PID-13", "Patients.CellPhone, HomePhone, Email", "cair emails.txt — required"],
            ["ORC-2/3", "CheckInsHeader.Id", "Excel mapping"],
            ["RXA-5", "ServiceCodes.NDCNumber or CVX", "Excel + CAIR PDF"],
            ["RXA-15", "EHRVaccines.LotNumber", "Excel mapping"],
            ["OBX-5", "V01 Not VFC eligible", "cair emails.txt sample"],
        ],
        [0.18, 0.42, 0.40],
        s,
    ))

    story.append(Paragraph("9. CAIR Endpoints & Commands", s["h1"]))
    story.append(wrap_table(
        ["Item", "Value"],
        [
            ["Stage endpoint", "cdph-interop-stage.cdph.ca.gov/.../client_ServiceHttpSoap12Endpoint"],
            ["SOAP operation", "submitSingleMessage"],
            ["Org code", "SF-013259"],
            ["Test HL7 (no DB)", "python demo_build_vxu.py"],
            ["Dry run (read DB, no send)", "python run_dry_once.py"],
            ["Run worker", "python cair_service.py"],
        ],
        [0.30, 0.70],
        s,
    ))

    story.append(PageBreak())

    # --- 10 Development & test data ---
    story.append(Paragraph("10. Development Testing (Sithum DB + Seed Script)", s["h1"]))
    story.append(Paragraph(
        "Use <b>scripts/seed_sithum_cair_test_data.py</b> to insert test records in the "
        "development clinic DB before running the CAIR worker. "
        "<b>Seeding does NOT send HL7</b> — it only creates queue rows (SubmitStatus = 0). "
        "HL7 is built and sent only when <b>cair_service.py</b> or <b>run_dry_once.py</b> runs.",
        s["body"],
    ))

    story.append(Paragraph("10.1 Seed Script Commands", s["h2"]))
    story.append(wrap_table(
        ["Command", "What it does"],
        [
            ["python scripts/seed_sithum_cair_test_data.py list",
             "Show published visits, vaccine codes with NDC, existing submissions"],
            ["python scripts/seed_sithum_cair_test_data.py seed",
             "Create up to 3 test vaccines + queue rows (default --count 3)"],
            ["python scripts/seed_sithum_cair_test_data.py seed --dry-run",
             "Preview actions without writing to the database"],
            ["python scripts/seed_sithum_cair_test_data.py verify",
             "Confirm records are eligible for the CAIR worker (read-only)"],
            ["python scripts/seed_sithum_cair_test_data.py reset",
             "Reset LOT-CAIR-TEST-* submissions back to PENDING for re-testing"],
        ],
        [0.48, 0.52],
        s,
    ))

    story.append(Paragraph("10.2 What the Seed Script Inserts", s["h2"]))
    story.append(wrap_table(
        ["Table", "Action", "Details"],
        [
            ["EHRVaccines", "INSERT or UPDATE", "LotNumber, VaccineDate, Manufacturer, Route, BodySite, IsVaccine=1, ServiceCodeId with NDC"],
            ["EHRVaccineThirdPartySubmissions", "INSERT", "EHRVaccineId, SubmitStatus=0 (PENDING), AttemptCount=0"],
            ["EHRHeaders", "No change", "Uses existing published visits (IsPublish = 1)"],
            ["Patients / CheckInsHeader", "No change", "Uses existing patient demographics"],
        ],
        [0.30, 0.18, 0.52],
        s,
    ))
    story.append(Paragraph(
        "The script auto-discovers published visits where the patient has phone and/or email "
        "(PID-13 requirement) and picks vaccine ServiceCodes that have an NDC number. "
        "Test lot numbers use prefix <b>LOT-CAIR-TEST-</b>. Safe to re-run — skips vaccines "
        "that already have a submission row.",
        s["body"],
    ))

    story.append(Paragraph("10.3 Testing Workflow (Step by Step)", s["h2"]))
    story.append(Preformatted(
        "1. Set CLINIC_DB_* in .env (Sithum development DB)\n"
        "2. python scripts/seed_sithum_cair_test_data.py seed\n"
        "3. python scripts/seed_sithum_cair_test_data.py verify\n"
        "       -> SubmitStatus should still be 0, RequestPayload empty (no HL7 sent yet)\n"
        "4. python run_dry_once.py\n"
        "       -> builds HL7 from DB; does not send to CAIR unless configured\n"
        "5. Add CAIR_SOAP_USERNAME and CAIR_SOAP_PASSWORD to .env\n"
        "6. python cair_service.py\n"
        "       -> sends HL7 to CAIR stage; updates SubmitStatus + saves RequestPayload",
        s["code"],
    ))

    story.append(Paragraph("10.4 How to Tell If HL7 Was Sent", s["h2"]))
    story.append(wrap_table(
        ["Check", "Not sent yet", "Sent / processed"],
        [
            ["SubmitStatus", "0 (PENDING)", "1=success, 2=failed, 3=retry, 4=processing"],
            ["RequestPayload", "NULL / empty", "Contains HL7 VXU message text"],
            ["SubmittedDateTime", "NULL", "Set on CAIR success (ACK = AA)"],
            ["ResponsePayload", "NULL", "Contains CAIR ACK response"],
        ],
        [0.28, 0.36, 0.36],
        s,
    ))
    story.append(Paragraph(
        "<b>Note:</b> CAIR_SOAP_USERNAME and CAIR_SOAP_PASSWORD must be set in .env before "
        "the worker can send to CAIR. Without credentials, only dry-run / verify steps work.",
        s["body"],
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
