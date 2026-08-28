"""Generate full-detail CAIR project documentation PDF (clear, readable)."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = Path(__file__).resolve().parents[1] / "CAIR_Project_Guide.pdf"

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=22,
            leading=28,
            spaceAfter=12,
            textColor=colors.HexColor("#1a365d"),
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontSize=12,
            leading=16,
            spaceAfter=18,
            textColor=colors.HexColor("#4a5568"),
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=15,
            leading=20,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.white,
            backColor=colors.HexColor("#2b6cb0"),
            borderPadding=(6, 8, 6, 8),
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#2b6cb0"),
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            spaceAfter=8,
            alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            leftIndent=14,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=9,
            leading=12,
            backColor=colors.HexColor("#f7fafc"),
            borderColor=colors.HexColor("#e2e8f0"),
            borderWidth=1,
            borderPadding=8,
            spaceAfter=10,
        ),
    }


def h1(text: str, s) -> Paragraph:
    return Paragraph(text, s["h1"])


def h2(text: str, s) -> Paragraph:
    return Paragraph(text, s["h2"])


def p(text: str, s) -> Paragraph:
    return Paragraph(text, s["body"])


def bullet(text: str, s) -> Paragraph:
    return Paragraph(f"&bull; {text}", s["bullet"])


def code(text: str, s) -> Preformatted:
    return Preformatted(text, s["code"])


def table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6cb0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 13),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def build_story(s):
    story = []
    cw = PAGE_W - 2 * MARGIN

    story.append(Paragraph("CAIR2 Integration Project", s["title"]))
    story.append(
        Paragraph(
            "Complete Technical Guide &mdash; ClaudMD / Aeliusmd<br/>"
            "HL7 v2.5.1 VXU | California Immunization Registry | Version 1.0",
            s["subtitle"],
        )
    )

    # 1 OVERVIEW
    story.append(h1("1. Project Overview", s))
    story.append(
        p(
            "This project sends vaccination records from ClaudMD clinic EMR databases to "
            "<b>CAIR2</b> (California Immunization Registry). CAIR2 is the statewide system "
            "that stores immunization history for California residents. Healthcare providers "
            "are required to report vaccinations electronically using standard HL7 messages.",
            s,
        )
    )
    story.append(
        p(
            "<b>What we build:</b> A Python background service that reads vaccination data from "
            "each clinic database, converts it to an HL7 VXU message, submits it to CAIR2 via "
            "SOAP, and records success or failure for retries.",
            s,
        )
    )
    story.append(
        code(
            "FLOW:\n"
            "  Nurse saves vaccination in ClaudMD (EHRVaccines table)\n"
            "       |\n"
            "  Queue record created (outbox table OR IsSubmitted = 0)\n"
            "       |\n"
            "  cair_service.py runs every 5 minutes\n"
            "       |\n"
            "  Coordinator reads master DB (ClinicSetup) for active clinics\n"
            "       |\n"
            "  Worker pool (3 threads) processes batches per clinic\n"
            "       |\n"
            "  Build HL7 VXU message from patient + vaccine data\n"
            "       |\n"
            "  POST to CAIR SOAP endpoint (submitSingleMessage)\n"
            "       |\n"
            "  Parse ACK response: AA=accepted, AE=retry, AR=rejected",
            s,
        )
    )

    # 2 ORG & ENDPOINTS
    story.append(h1("2. Your CAIR Onboarding Details", s))
    story.append(
        table(
            [
                ["Setting", "Value"],
                ["Organization", "Aeliusmd Inc"],
                ["CAIR Org Code", "SF-013259"],
                ["Contact email", "CAIRDataExchange@cdph.ca.gov"],
                ["Spec document", "CAIR2_HL7v2.5.1DataExchangeSpecs.pdf v3.10"],
                ["Message type", "VXU (Unsolicited Vaccination Update)"],
                ["HL7 version", "2.5.1 only"],
                ["Transport", "SOAP web service (not MLLP/TCP)"],
            ],
            [5 * cm, 12.5 * cm],
        )
    )
    story.append(Spacer(1, 12))
    story.append(h2("SOAP Endpoints", s))
    story.append(
        table(
            [
                ["Environment", "URL / Operation"],
                [
                    "ONBOARDING (test first)",
                    "Endpoint: https://cdph-interop-stage.cdph.ca.gov/services/"
                    "client_Service.client_ServiceHttpSoap12Endpoint",
                ],
                [
                    "WSDL (stage)",
                    "https://cdph-interop-stage.cdph.ca.gov/CASTG-WS/IISService?WSDL",
                ],
                [
                    "PRODUCTION",
                    "Endpoint: https://cdph-interop-prod.cdph.ca.gov/services/"
                    "client_Service.client_ServiceHttpSoap12Endpoint",
                ],
                [
                    "WSDL (prod)",
                    "https://cdph-interop-prod.cdph.ca.gov/CAPRD-WS/IISService?WSDL",
                ],
                ["VXU operation", "submitSingleMessage"],
                ["Query operation", "submitSingleQuery (QBP/RSP - optional)"],
                ["Old endpoint (DO NOT USE)", "https://cair.cdph.ca.gov/CAPRD-WS/IISService"],
            ],
            [4.5 * cm, 13 * cm],
        )
    )

    story.append(PageBreak())

    # 3 HL7 MESSAGE
    story.append(h1("3. HL7 VXU Message Structure", s))
    story.append(
        p(
            "A VXU message is a pipe-delimited (|) text document. Each line is a segment. "
            "Every vaccination submission must be a <b>full VXU</b> with all required fields, "
            "even when updating an existing record.",
            s,
        )
    )
    story.append(
        table(
            [
                ["Segment", "Required", "Purpose"],
                ["MSH", "Yes", "Message header: sender, receiver, timestamp, message type"],
                ["PID", "Yes", "Patient: name, DOB, sex, address, phone/email"],
                ["PD1", "Yes", "Privacy: protection indicator, publicity code"],
                ["NK1", "Optional", "Next of kin / guardian"],
                ["ORC", "Yes", "Order control: links vaccination to check-in"],
                ["RXA", "Yes", "Vaccine administration: code, dose, lot, date"],
                ["RXR", "Optional", "Route and body site (e.g. IM, left arm)"],
                ["OBX", "Optional", "Observations: VFC funding eligibility"],
            ],
            [2.5 * cm, 2 * cm, 13 * cm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(h2("Official CAIR Sample Message (from cair emails.txt)", s))
    story.append(
        code(
            "MSH|^~\\&||CA0012345||CAIR2|20260816023022-0700||VXU^V04^VXU_V04|\n"
            "  3f2504e0-4f89-11d3-9a0c-0305e82c3301|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|CA0054321\n"
            "PID|1||AC10293^^^CA0012345^MR||Alvarez^Maria^^^^^|^^^^^^|19880412|F||\n"
            "  2106-3^^CDCREC|123 Main St^^Sacramento^CA^95814||\n"
            "  ^NET^Internet^maria.alvarez@example.com~^PRN^CP^^^916^5550134||^^|||||||\n"
            "  2186-5^^CDCREC|||\n"
            "PD1|||||||||||^^|N|20260810|||||\n"
            "ORC|RE|48213^CMC|48213^CMC|||||||||\n"
            "RXA|0|1|20260810||00069-1000-03^^NDC|0.3|mL^^UCUM||\n"
            "  00^NEW IMMUNIZATION RECORD^NIP001||^^^CA0054321||||FA7205||PFR^^MVX|||CP|A|\n"
            "  20260816023022-0700\n"
            "OBX|1|CE|64994-7^Vaccine funding program eligibility category^LN|1|\n"
            "  V01^Not VFC eligible^HL70064||||||F|||20260810",
            s,
        )
    )

    # 4 FIELD REFERENCE
    story.append(h1("4. Complete HL7 Field Reference", s))
    story.append(h2("MSH - Message Header", s))
    story.append(
        table(
            [
                ["Field", "Usage", "Value / Example", "Notes"],
                ["MSH-1", "R", "|", "Field separator"],
                ["MSH-2", "R", "^~\\&", "Encoding characters"],
                ["MSH-4", "R", "SF-013259", "Sending facility = your CAIR org code"],
                ["MSH-6", "R", "CAIR2", "Receiving facility"],
                ["MSH-7", "R", "20260816023022-0700", "Message datetime"],
                ["MSH-9", "R", "VXU^V04^VXU_V04", "Message type"],
                ["MSH-10", "R", "GUID", "Unique message control ID"],
                ["MSH-11", "R", "P or T", "P=production, T=training/test"],
                ["MSH-12", "R", "2.5.1", "HL7 version - only 2.5.1 accepted"],
                ["MSH-15", "RE", "AL", "Accept acknowledgment type"],
                ["MSH-16", "RE", "AL", "Application acknowledgment type"],
                ["MSH-22", "RE", "SF-013259", "Responsible org / site where vaccine given"],
            ],
            [2.2 * cm, 1.5 * cm, 5.5 * cm, 8.3 * cm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(h2("PID - Patient Identification", s))
    story.append(
        table(
            [
                ["Field", "Usage", "ClaudMD Source", "Example"],
                ["PID-3", "R", "Patients.AccountNumber", "AC10293^^^SF-013259^MR"],
                ["PID-5", "R", "Patients.LastName, FirstName", "Alvarez^Maria"],
                ["PID-7", "R", "Patients.DateOfBirth", "19880412"],
                ["PID-8", "R", "Patients.GenderId (lookup)", "F / M / X / U"],
                ["PID-11", "RE", "Address1, City, State, ZipCode", "123 Main St^^Sacramento^CA^95814"],
                ["PID-13", "RE", "CellPhone, HomePhone, Email", "See PID-13 section below"],
                ["PID-22", "RE", "EthnicityId (lookup)", "2186-5^^CDCREC"],
            ],
            [2 * cm, 1.5 * cm, 5.5 * cm, 8.5 * cm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(h2("RXA - Vaccine Administration", s))
    story.append(
        table(
            [
                ["Field", "Usage", "ClaudMD Source", "Example"],
                ["RXA-1", "R", "Hardcoded", "0"],
                ["RXA-2", "R", "Hardcoded", "1"],
                ["RXA-3", "R", "EHRVaccines.VaccineDate", "20260810"],
                ["RXA-5", "R", "ServiceCodes.NDCNumber or CVX", "00069-1000-03^^NDC"],
                ["RXA-6", "R", "EHRVaccines.Dosage", "0.3 (use 999 if unknown)"],
                ["RXA-7", "R", "Hardcoded if dose known", "mL^^UCUM"],
                ["RXA-9.1", "R", "Hardcoded", "00 = given shot (not historical)"],
                ["RXA-11.4", "R", "CAIR site ID", "SF-013259"],
                ["RXA-15", "R", "EHRVaccines.LotNumber", "FA7205"],
                ["RXA-16", "RE", "EHRVaccines.VaccineExpirationDate", "20270531"],
                ["RXA-17", "R", "EHRVaccines.Manufacturer / MVX", "PFR^^MVX"],
                ["RXA-20", "RE", "Hardcoded", "CP = complete"],
                ["RXA-21", "RE", "Hardcoded", "A = add new record"],
                ["OBX-5", "R", "VFC eligibility code", "V01^Not VFC eligible^HL70064"],
            ],
            [2 * cm, 1.5 * cm, 5.5 * cm, 8.5 * cm],
        )
    )

    story.append(PageBreak())

    # 5 PID-13
    story.append(h1("5. PID-13 Contact Information (CRITICAL)", s))
    story.append(
        p(
            "<b>CAIR requires at least one of: home phone, cell phone, or email.</b> "
            "Messages without valid contact info receive warnings or rejection:",
            s,
        )
    )
    story.append(
        code(
            "ERR||PID^1^13|101|Warning: Home Phone or Cell Phone is missing or invalid\n"
            "ERR||PID^1^13|102|Warning: Invalid Client Email",
            s,
        )
    )
    story.append(
        table(
            [
                ["Contact Type", "PID-13.2", "PID-13.3", "PID-13.4", "PID-13.6", "PID-13.7"],
                ["Home phone", "PRN", "PH", "-", "area code", "number"],
                ["Cell phone", "PRN", "CP", "-", "area code", "number"],
                ["Email", "NET", "Internet", "email@address.com", "-", "-"],
            ],
            [3 * cm, 2 * cm, 2.5 * cm, 4.5 * cm, 2.5 * cm, 3 * cm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(h2("PID-13 Format Examples", s))
    story.append(
        code(
            "Cell phone only:\n"
            "  ^PRN^CP^^^916^5550134\n\n"
            "Email + cell phone:\n"
            "  ^NET^Internet^maria.alvarez@example.com~^PRN^CP^^^916^5550134\n\n"
            "Home + email + cell:\n"
            "  ^PRN^PH^^^213^5555555~^NET^Internet^email@x.com~^PRN^CP^^^213^5551234",
            s,
        )
    )
    story.append(
        p(
            "<b>QA database finding:</b> Patients table has CellPhone populated but Email is "
            "mostly NULL. Update patient intake to collect email or ensure cell phone is always present.",
            s,
        )
    )

    # 6 VACCINE CODES
    story.append(h1("6. Vaccine Codes Explained", s))
    story.append(
        table(
            [
                ["Code", "Full Name", "Used In", "Example", "Purpose"],
                ["CVX", "CDC Vaccine Code", "RXA-5", "08=Hep B, 207=COVID", "Clinical vaccine identity"],
                ["MVX", "Manufacturer Code", "RXA-17", "PFR=Pfizer, MSD=Merck", "Who made the vaccine"],
                ["NDC", "National Drug Code", "RXA-5", "00069-1000-03", "Product package ID"],
                ["CPT", "Billing Code", "NOT in VXU", "90471", "Reimbursement only"],
                ["HL70064", "VFC Eligibility", "OBX-5", "V01, V03", "Funding category"],
            ],
            [2 * cm, 3.5 * cm, 2.5 * cm, 4 * cm, 5.5 * cm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        p(
            "<b>Important:</b> CAIR accepts CVX <b>or</b> NDC in RXA-5, not both together. "
            "CPT codes are for billing and are NOT used as the primary vaccine identifier in CAIR.",
            s,
        )
    )
    story.append(h2("Fields That Must Be Added to ServiceCodes (from CAIR email)", s))
    story.append(
        table(
            [
                ["Field", "Type", "Priority", "Description"],
                ["CvxCode", "varchar(10)", "MUST HAVE", "CDC vaccine code. String not int (e.g. 09)"],
                ["MvxCode", "varchar(10)", "MUST HAVE", "Manufacturer code e.g. SKB, PFR"],
                ["IsVaccineProduct", "bit", "MUST HAVE", "Exclude admin fees from reporting"],
                ["RegistryApprovedOn", "date", "MUST HAVE", "Null = do not report to CAIR"],
                ["RouteCode", "varchar(20)", "SHOULD HAVE", "C28161=IM. CAIR rejects without route"],
                ["DoseAmount", "decimal(9,3)", "SHOULD HAVE", "e.g. 0.5"],
                ["DoseUnit", "varchar(12)", "SHOULD HAVE", "e.g. mL"],
                ["Ndc11", "varchar(11)", "SHOULD HAVE", "11-digit NDC (10-digit is ambiguous)"],
                ["CvxText / MvxText", "varchar(200)", "SHOULD HAVE", "Human-readable labels"],
            ],
            [3.5 * cm, 3 * cm, 2.5 * cm, 8.5 * cm],
        )
    )

    story.append(PageBreak())

    # 7 DATABASE
    story.append(h1("7. ClaudMD Database Structure", s))
    story.append(h2("Master Database: ClaudMD_QA_Setup", s))
    story.append(
        p(
            "Server: 10.103.0.201 | Database: ClaudMD_QA_Setup<br/>"
            "This is the <b>clinic registry</b>, not the EMR data. It lists all clinics and "
            "their individual database connection details.",
            s,
        )
    )
    story.append(
        table(
            [
                ["ClinicSetup Column", "Purpose"],
                ["ClinicID", "Internal clinic identifier"],
                ["ClinicName", "Display name"],
                ["DatabaseServer", "SQL Server for this clinic"],
                ["DatabaseName", "Clinic EMR database name"],
                ["DatabaseUser / DatabasePassword", "Connection credentials"],
                ["ActivationKey", "e.g. 20000002"],
                ["Active", "1 = clinic is active"],
            ],
            [6 * cm, 11.5 * cm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(h2("Active QA Clinics (from database read)", s))
    story.append(
        table(
            [
                ["ActivationKey", "ClinicName", "DatabaseName"],
                ["20000001", "ClaudMD_VCOMC_QA_1", "ClaudMD_VCOMC_QA_1"],
                ["20000002", "ClaudMD_VCOMC_QA_2", "ClaudMD_VCOMC_QA_2"],
                ["20000003", "ClaudMD_VCOMC_QA_3", "ClaudMD_VCOMC_QA_3"],
                ["20000004", "ClaudMD_Medcube_QA", "ClaudMD_Medcube_QA"],
                ["20000005", "Aelius_vcomc_QA", "Aelius_vcomc_QA"],
            ],
            [3.5 * cm, 6 * cm, 8 * cm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(h2("Clinic EMR Database Tables (421 tables per clinic)", s))
    story.append(
        table(
            [
                ["CAIR Concept", "ClaudMD Table", "Key Columns"],
                ["Patient", "dbo.Patients", "AccountNumber, FirstName, LastName, DateOfBirth, GenderId, CellPhone, HomePhone, Email"],
                ["Check-in / Visit", "dbo.CheckInsHeader", "Id, PatientId, CheckInDate, CheckInTime, ProviderId"],
                ["Vaccination", "dbo.EHRVaccines", "CheckInId, ServiceCodeId, VaccineDate, LotNumber, Dosage, Route, IsVaccine, IsSubmitted"],
                ["Service / Product", "dbo.ServiceCodes", "Code, Description, CPTCode, NDCNumber"],
                ["Billing charges", "dbo.Transactions", "CheckInId, ServiceCodeId, Units, NDCNumber"],
            ],
            [3.5 * cm, 4.5 * cm, 9.5 * cm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(h2("EHRVaccines - Full Column List", s))
    story.append(
        code(
            "Id, CheckInId, ServiceCodeId, OrderServicesId, VaccineName, LotNumber,\n"
            "VaccineExpirationDate, Dosage, VaccinatorId, BodySite, Route, Manufacturer,\n"
            "VaccineDate, VaccineTime, IsVaccine, IsSubmitted, IsDeleted, Dose,\n"
            "VisPublicationDate, VaccineNotDoneReasonId, Remarks",
            s,
        )
    )
    story.append(
        p(
            "<b>Key flags:</b> IsVaccine=1 means real vaccine (not TB test etc). "
            "IsSubmitted=0 means not yet sent to CAIR. QA currently has 24 EHRVaccines rows "
            "but 0 with IsVaccine=1 and 0 with lot numbers filled.",
            s,
        )
    )

    story.append(PageBreak())

    # 8 ARCHITECTURE
    story.append(h1("8. Worker Architecture (Multi-Clinic)", s))
    story.append(
        code(
            "                    SCHEDULER (every 5 min)\n"
            "                            |\n"
            "                    CLINIC COORDINATOR\n"
            "              reads ClaudMD_QA_Setup.ClinicSetup\n"
            "                            |\n"
            "              finds clinics with pending CAIR work\n"
            "                            |\n"
            "         +------------------+------------------+\n"
            "         |                  |                  |\n"
            "     Worker 1           Worker 2           Worker 3\n"
            "   Clinic A batch     Clinic B batch     Clinic C batch\n"
            "   (max 100 rows)     (max 100 rows)     (max 100 rows)\n"
            "         |                  |                  |\n"
            "    Build HL7 VXU     Build HL7 VXU     Build HL7 VXU\n"
            "    Send SOAP          Send SOAP          Send SOAP\n"
            "    Update status      Update status      Update status",
            s,
        )
    )
    story.append(h2("Outbox Status Flow", s))
    story.append(
        table(
            [
                ["Status", "Meaning", "Next Action"],
                ["PENDING", "New vaccination queued", "Worker picks up on next run"],
                ["PROCESSING", "Worker claimed record", "Building/sending HL7"],
                ["SENT", "CAIR accepted (ACK=AA)", "Done"],
                ["RETRY", "Temporary failure (timeout/network)", "Retry after backoff delay"],
                ["FAILED", "Permanent error (bad data)", "Manual review required"],
            ],
            [3 * cm, 6 * cm, 8.5 * cm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(h2("Retry Schedule (Exponential Backoff)", s))
    story.append(
        table(
            [
                ["Attempt", "Wait Before Retry"],
                ["1", "5 minutes"],
                ["2", "15 minutes"],
                ["3", "30 minutes"],
                ["4", "60 minutes"],
                ["5", "120 minutes"],
                ["6+", "Mark as FAILED"],
            ],
            [4 * cm, 13.5 * cm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        p(
            "<b>Multi-clinic rules:</b> Workers are a shared pool (not 1 worker per clinic forever). "
            "Only one active batch per clinic at a time to avoid race conditions. "
            "Retries and new PENDING records share the same queue.",
            s,
        )
    )

    # 9 PROJECT FILES
    story.append(h1("9. Project Files & Setup", s))
    story.append(
        table(
            [
                ["File", "Purpose"],
                ["cair_service.py", "Main background worker - run continuously"],
                ["demo_build_vxu.py", "Generate sample HL7 without database"],
                ["scripts/seed_sithum_cair_test_data.py", "Dev: insert test vaccines + CAIR queue rows"],
                ["run_dry_once.py", "One worker cycle — read DB, build HL7 (dry-run)"],
                ["cair_integration/hl7/vxu_builder.py", "Builds HL7 VXU from data models"],
                ["cair_integration/cair/soap_client.py", "Sends HL7 to CAIR SOAP endpoint"],
                ["cair_integration/cair/ack_parser.py", "Parses ACK response (AA/AE/AR)"],
                ["cair_integration/worker/coordinator.py", "Multi-clinic job dispatcher"],
                ["cair_integration/worker/processor.py", "Processes one outbox record"],
                ["cair_integration/outbox/repository.py", "Database access layer"],
                ["cair_integration/vaccination_service.py", "Creates outbox on vaccine save"],
                [".env", "Credentials and config (never commit to git)"],
                ["sql/schema.sql", "Outbox table DDL (optional - adapt for ClaudMD)"],
            ],
            [7 * cm, 10.5 * cm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(h2("Environment Variables (.env)", s))
    story.append(
        p(
            "<b>QA mode</b> — MASTER_DB_* + ClinicSetup. "
            "<b>Development mode</b> — CLINIC_DB_* direct to Sithum clinic DB (skips ClinicSetup).",
            s,
        )
    )
    story.append(
        code(
            "# Development (Sithum clinic DB)\n"
            "APP_ENV=development\n"
            "CLINIC_DB_SERVER=10.103.0.211\n"
            "CLINIC_DB_NAME=ClaudMD_Development_Sithum\n"
            "CLINIC_DB_USER=testuser\n"
            "CLINIC_DB_PASSWORD=***\n"
            "\n"
            "# QA (master DB + ClinicSetup)\n"
            "MASTER_DB_SERVER=10.103.0.201\n"
            "MASTER_DB_NAME=ClaudMD_QA_Setup\n"
            "MASTER_DB_USER=testuser\n"
            "MASTER_DB_PASSWORD=***\n"
            "DEFAULT_ACTIVATION_KEY=20000002\n"
            "\n"
            "CAIR_SOAP_URL=https://cdph-interop-stage.cdph.ca.gov/services/\n"
            "  client_Service.client_ServiceHttpSoap12Endpoint\n"
            "CAIR_SOAP_USERNAME=   # required to send HL7\n"
            "CAIR_SOAP_PASSWORD=   # required to send HL7\n"
            "SENDING_FACILITY_ID=SF-013259\n"
            "RECEIVING_FACILITY=CAIR2\n"
            "WORKER_BATCH_SIZE=100\n"
            "WORKER_POOL_SIZE=3\n"
            "SCHEDULER_INTERVAL_SECONDS=300",
            s,
        )
    )
    story.append(h2("Commands to Run", s))
    story.append(
        code(
            "pip install -r requirements.txt\n"
            "python scripts/seed_sithum_cair_test_data.py seed    # dev test data\n"
            "python scripts/seed_sithum_cair_test_data.py verify  # check queue\n"
            "python demo_build_vxu.py       # Test HL7 without database\n"
            "python run_dry_once.py         # Build HL7 from DB (no CAIR send)\n"
            "python cair_service.py         # Start background worker",
            s,
        )
    )
    story.append(h2("Development Testing (Sithum DB)", s))
    story.append(
        p(
            "The seed script inserts EHRVaccines and EHRVaccineThirdPartySubmissions for testing. "
            "<b>It does not send HL7.</b> SubmitStatus stays 0 and RequestPayload is empty until "
            "cair_service.py runs with valid CAIR SOAP credentials.",
            s,
        )
    )
    story.append(
        table(
            [
                ["Seed command", "Purpose"],
                ["list", "Show published visits and existing submissions"],
                ["seed", "Create test vaccines + queue rows (SubmitStatus=0)"],
                ["verify", "Confirm worker can pick up pending rows"],
                ["reset", "Reset LOT-CAIR-TEST-* rows back to PENDING"],
            ],
            [6 * cm, 11.5 * cm],
        )
    )

    story.append(PageBreak())

    # 10 ACK
    story.append(h1("10. ACK Response Handling", s))
    story.append(
        p(
            "After submitting a VXU, CAIR returns an HL7 ACK (acknowledgment) message:",
            s,
        )
    )
    story.append(
        code(
            "MSH|^~\\&|CAIR2|CAIRLO|MyEMR|SF-013259|...||ACK^V04^ACK|{message_id}|P|2.5.1\n"
            "MSA|AA|{message_id}\n"
            "ERR|...  (only if errors)",
            s,
        )
    )
    story.append(
        table(
            [
                ["MSA-1 Code", "Meaning", "Action"],
                ["AA", "Application Accept", "Mark outbox as SENT"],
                ["AE", "Application Error", "Schedule RETRY (temporary)"],
                ["AR", "Application Reject", "Mark as FAILED (fix data)"],
            ],
            [3 * cm, 5 * cm, 9.5 * cm],
        )
    )

    # 11 INVENTORY
    story.append(h1("11. Inventory Decrementing (Optional CAIR Feature)", s))
    story.append(
        p(
            "CAIR can automatically decrement vaccine inventory when a shot is reported. "
            "This is OFF by default. Contact CAIR Data Exchange team to enable.",
            s,
        )
    )
    story.append(
        table(
            [
                ["Field", "Requirement"],
                ["MSH-22", "Must match CAIR site ID where inventory is stored"],
                ["RXA-5.1", "Vaccine code must match inventory"],
                ["RXA-9.1", "Must be 00 (given shot, not historical)"],
                ["RXA-11.4", "Must match MSH-22 site ID"],
                ["RXA-15", "Lot number must match CAIR inventory"],
                ["RXA-20", "CP, PA, or empty"],
                ["RXA-21", "A or U"],
                ["OBX-5.1", "VFC funding must match lot funding category"],
            ],
            [3.5 * cm, 14 * cm],
        )
    )

    # 12 BLOCKERS
    story.append(h1("12. Current Blockers & Action Items", s))
    story.append(
        table(
            [
                ["#", "Blocker", "Owner", "Action"],
                ["1", "No CvxCode/MvxCode in ServiceCodes", "EMR team", "Add columns + CDC lookup tables"],
                ["2", "Patient email mostly NULL", "EMR team", "Require email or cell at intake"],
                ["3", "Lot number never filled", "Clinical staff", "Make mandatory on vaccine entry"],
                ["4", "Route field empty", "EMR team", "Add RouteCode default per vaccine product"],
                ["5", "No test vaccine data (IsVaccine=0)", "QA team", "Create test vaccination records"],
                ["6", "NDC empty on vaccine codes", "EMR team", "Populate NDC or use CVX mapping"],
                ["7", "Not tested on CAIR stage", "Dev team", "Submit test VXU, email CAIR team"],
                ["8", "GenderId is int not M/F", "Dev team", "Add lookup GenderId to HL7 sex code"],
            ],
            [1 * cm, 5.5 * cm, 3 * cm, 8 * cm],
        )
    )

    # 13 TESTING
    story.append(h1("13. Testing Checklist", s))
    for item in [
        "Configure .env — CLINIC_DB_* for Sithum dev or MASTER_DB_* for QA",
        "Run scripts/seed_sithum_cair_test_data.py seed then verify (dev DB)",
        "Confirm SubmitStatus=0 and RequestPayload empty — no HL7 sent yet",
        "Configure .env with stage SOAP endpoint, credentials, and SF-013259",
        "Run demo_build_vxu.py and verify HL7 output matches CAIR sample format",
        "Run run_dry_once.py to build HL7 from real DB rows without sending",
        "Create test patient with CellPhone AND Email populated",
        "Create EHRVaccines record with IsVaccine=1, LotNumber, Route, Dosage filled",
        "Add CVX/MVX codes to the linked ServiceCode record",
        "Submit test message to CAIR stage endpoint (cair_service.py)",
        "Email CAIRDataExchange@cdph.ca.gov to request review of test submissions",
        "Fix any ERR warnings in ACK response",
        "Switch to production endpoint after CAIR approval",
        "Deploy cair_service.py on server with scheduler running every 5 minutes",
    ]:
        story.append(bullet(item, s))

    story.append(Spacer(1, 20))
    story.append(
        p(
            "<b>Document generated from:</b> CAIR2_HL7v2.5.1DataExchangeSpecs.pdf, "
            "Required Fields mapping Excel, cair emails.txt, ClaudMD QA database inspection, "
            "and cair_integration Python implementation.",
            s,
        )
    )

    return story


def main():
    s = styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title="CAIR2 Integration Project Guide",
        author="Aeliusmd",
    )

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawString(MARGIN, 1.2 * cm, "CAIR2 Integration Project Guide | Aeliusmd | Confidential")
        canvas.drawRightString(PAGE_W - MARGIN, 1.2 * cm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(build_story(s), onFirstPage=on_page, onLaterPages=on_page)
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
