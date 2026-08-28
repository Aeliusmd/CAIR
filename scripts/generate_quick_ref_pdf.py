"""Generate CAIR project quick-reference PDF."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF


class QuickRefPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "CAIR2 Integration - Quick Reference", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, "Aeliusmd | ClaudMD | HL7 VXU v2.5.1", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def section(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(230, 240, 255)
        self.cell(0, 7, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 4.5, text)
        self.ln(1)

    def code(self, text: str):
        self.set_font("Courier", "", 7.5)
        self.set_fill_color(245, 245, 245)
        self.multi_cell(0, 3.8, text, fill=True)
        self.ln(1)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int]):
        self.set_font("Helvetica", "B", 8)
        for i, h in enumerate(headers):
            self.cell(widths[i], 6, h, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)
        for row in rows:
            line_h = 5
            x0, y0 = self.get_x(), self.get_y()
            heights = []
            for i, cell in enumerate(row):
                self.set_xy(x0 + sum(widths[:i]), y0)
                self.multi_cell(widths[i], line_h, cell, border=0)
                heights.append(self.get_y() - y0)
            row_h = max(heights) if heights else line_h
            x = x0
            for i, cell in enumerate(row):
                self.rect(x, y0, widths[i], row_h)
                self.set_xy(x + 1, y0 + 1)
                self.multi_cell(widths[i] - 2, line_h, cell)
                x += widths[i]
            self.set_xy(x0, y0 + row_h)
        self.ln(2)


def build_pdf(output: Path) -> None:
    pdf = QuickRefPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.body(
        "Goal: Send vaccination records from ClaudMD clinics to CAIR2 "
        "(California Immunization Registry) using HL7 v2.5.1 VXU messages over SOAP."
    )

    pdf.section("1. Architecture (30-second view)")
    pdf.code(
        "Nurse saves vaccine (EHRVaccines, IsVaccine=1)\n"
        "        |\n"
        "Queue row (outbox or IsSubmitted=0)\n"
        "        |\n"
        "cair_service.py (every 5 min, worker pool)\n"
        "        |\n"
        "Build HL7 VXU -> SOAP submitSingleMessage -> CAIR2\n"
        "        |\n"
        "ACK: AA=success | AE=retry | AR=failed"
    )

    pdf.section("2. Your Environment")
    pdf.table(
        ["Item", "Value"],
        [
            ["Org code (Aeliusmd)", "SF-013259"],
            ["Master DB", "ClaudMD_QA_Setup @ 10.103.0.201"],
            ["Activation key (example)", "20000002 -> ClaudMD_VCOMC_QA_2"],
            ["Clinic registry table", "dbo.ClinicSetup"],
            ["CAIR contact", "CAIRDataExchange@cdph.ca.gov"],
        ],
        [55, 125],
    )

    pdf.section("3. CAIR SOAP Endpoints")
    pdf.table(
        ["Env", "URL"],
        [
            ["ONBOARDING (test now)", "cdph-interop-stage.cdph.ca.gov/.../client_ServiceHttpSoap12Endpoint"],
            ["WSDL (stage)", "cdph-interop-stage.cdph.ca.gov/CASTG-WS/IISService?WSDL"],
            ["PRODUCTION", "cdph-interop-prod.cdph.ca.gov/.../client_ServiceHttpSoap12Endpoint"],
            ["SOAP operation", "submitSingleMessage (VXU)"],
        ],
        [40, 140],
    )

    pdf.section("4. Sample HL7 VXU Message (from CAIR email)")
    pdf.code(
        "MSH|^~\\&||CA0012345||CAIR2|20260816023022-0700||VXU^V04^VXU_V04|\n"
        "  {GUID}|P|2.5.1|||AL|AL|||||Z22^CDCPHINVS|CA0054321\n"
        "PID|1||AC10293^^^CA0012345^MR||Alvarez^Maria|...|19880412|F|...\n"
        "  |^NET^Internet^maria@example.com~^PRN^CP^^^916^5550134|...\n"
        "ORC|RE|48213^CMC|48213^CMC|...\n"
        "RXA|0|1|20260810||00069-1000-03^^NDC|0.3|mL^^UCUM||\n"
        "  00^NEW IMMUNIZATION RECORD^NIP001||^^^CA0054321||||FA7205||PFR^^MVX|||CP|A\n"
        "OBX|1|CE|64994-7^...^LN|1|V01^Not VFC eligible^HL70064||||||F|||20260810"
    )

    pdf.section("5. HL7 Segments - What Each Does")
    pdf.table(
        ["Segment", "Purpose", "Example"],
        [
            ["MSH", "Message header", "VXU^V04^VXU_V04, facility ID, AL|AL"],
            ["PID", "Patient demographics", "Name, DOB, sex, address, PID-13 phone/email"],
            ["PD1", "Privacy/consent", "Protection indicator Y/N"],
            ["ORC", "Order control", "RE, check-in ID"],
            ["RXA", "Vaccine given", "NDC/CVX, dose, lot, date, CP|A"],
            ["RXR", "Route & site", "IM, left arm (optional)"],
            ["OBX", "VFC eligibility", "V01 = not VFC eligible"],
        ],
        [18, 52, 110],
    )

    pdf.add_page()
    pdf.section("6. ClaudMD Database Mapping (Real Tables)")
    pdf.table(
        ["CAIR / Excel field", "ClaudMD table.column"],
        [
            ["Patient ID (PID-3)", "Patients.AccountNumber"],
            ["Check-in ID (ORC-2/3)", "CheckInsHeader.Id"],
            ["Vaccination record", "EHRVaccines"],
            ["Vaccine code (RXA-5)", "ServiceCodes.NDCNumber (CVX missing!)"],
            ["Dose (RXA-6)", "EHRVaccines.Dosage"],
            ["Lot (RXA-15)", "EHRVaccines.LotNumber"],
            ["Manufacturer (RXA-17)", "EHRVaccines.Manufacturer (need MVX code)"],
            ["Admin date (RXA-3)", "EHRVaccines.VaccineDate + VaccineTime"],
            ["Phone/email (PID-13)", "Patients.CellPhone, HomePhone, Email"],
            ["Already submitted?", "EHRVaccines.IsSubmitted"],
            ["Filter real vaccines", "EHRVaccines.IsVaccine = 1"],
        ],
        [55, 125],
    )

    pdf.section("7. PID-13 Contact - REQUIRED by CAIR")
    pdf.body(
        "CAIR rejects/warns if phone AND email are both missing. "
        "At least one must be sent in PID-13."
    )
    pdf.code(
        "Home phone:  ^PRN^PH^^^213^5555555\n"
        "Cell phone:  ^PRN^CP^^^916^5550134\n"
        "Email:       ^NET^Internet^patient@email.com\n"
        "\n"
        "All together (separated by ~):\n"
        "^PRN^PH^^^213^5555555~^NET^Internet^email@x.com~^PRN^CP^^^916^5551234"
    )
    pdf.body("QA issue: most Patients have CellPhone but Email is NULL.")

    pdf.section("8. Vaccine Codes")
    pdf.table(
        ["Code", "Used for", "Example"],
        [
            ["CVX", "Vaccine type (clinical)", "08=Hep B, 207=COVID"],
            ["MVX", "Manufacturer", "PFR=Pfizer, MSD=Merck"],
            ["NDC", "Product package", "00069-1000-03"],
            ["CPT", "Billing only", "NOT used in CAIR VXU primary field"],
        ],
        [20, 55, 105],
    )
    pdf.body(
        "BLOCKER: ServiceCodes has no CvxCode or MvxCode columns yet. "
        "Must add per CAIR email requirements before reporting works."
    )

    pdf.section("9. Outbox / Worker Flow")
    pdf.code(
        "Status flow:\n"
        "  PENDING -> PROCESSING -> SENT\n"
        "                      -> RETRY (network/timeout, retry later)\n"
        "                      -> FAILED (bad data, manual fix)\n"
        "\n"
        "Worker query (one queue for new + retries):\n"
        "  WHERE status='PENDING'\n"
        "     OR (status='RETRY' AND next_retry_at <= now)\n"
        "\n"
        "Multi-clinic: 3 workers, 1 batch per clinic at a time,\n"
        "shared pool (not 1 worker per clinic forever)."
    )

    pdf.section("10. MSH Key Fields Cheat Sheet")
    pdf.table(
        ["Field", "Value", "Notes"],
        [
            ["MSH-4", "SF-013259", "Your CAIR org code"],
            ["MSH-6", "CAIR2", "Receiving facility"],
            ["MSH-9", "VXU^V04^VXU_V04", "Message type"],
            ["MSH-10", "GUID", "Unique per message"],
            ["MSH-11", "P or T", "P=production, T=training"],
            ["MSH-15/16", "AL / AL", "Always get ACK"],
            ["MSH-22", "Site ID", "Where vaccine was given"],
        ],
        [22, 45, 113],
    )

    pdf.section("11. RXA Key Fields Cheat Sheet")
    pdf.table(
        ["Field", "Value", "Notes"],
        [
            ["RXA-1/2", "0 / 1", "Fixed counters"],
            ["RXA-3", "YYYYMMDD", "Vaccine date"],
            ["RXA-5", "NDC or CVX", "One only, not both"],
            ["RXA-6", "0.3 or 999", "999 if dose unknown"],
            ["RXA-7", "mL^^UCUM", "Unit if dose known"],
            ["RXA-9.1", "00", "00=given shot (not historical)"],
            ["RXA-15", "FA7205", "Lot number"],
            ["RXA-20/21", "CP / A", "Complete / Add"],
            ["OBX-5", "V01", "VFC eligibility code"],
        ],
        [22, 40, 118],
    )

    pdf.add_page()
    pdf.section("12. Project Files")
    pdf.table(
        ["File", "Purpose"],
        [
            ["cair_service.py", "Background worker - run continuously"],
            ["demo_build_vxu.py", "Test HL7 generation without DB"],
            ["cair_integration/hl7/vxu_builder.py", "Builds HL7 message"],
            ["cair_integration/cair/soap_client.py", "Sends to CAIR SOAP"],
            ["cair_integration/worker/coordinator.py", "Multi-clinic dispatcher"],
            [".env", "DB + CAIR credentials (do not commit)"],
            ["CAIR2_HL7v2.5.1DataExchangeSpecs.pdf", "Official CAIR spec"],
            ["cair emails.txt", "Endpoints, sample HL7, PID-13 rules"],
        ],
        [75, 105],
    )

    pdf.section("13. Blockers Before Go-Live")
    pdf.body(
        "1. Add CvxCode + MvxCode to ServiceCodes (CDC lookup tables)\n"
        "2. Collect patient email or cell phone (PID-13 required)\n"
        "3. Fill lot number + route on vaccine entry\n"
        "4. Create test data: EHRVaccines with IsVaccine=1 (QA has 0 today)\n"
        "5. Test on STAGE endpoint, email CAIR team for review\n"
        "6. Switch to PROD endpoint after approval"
    )

    pdf.section("14. Quick Test Commands")
    pdf.code(
        "pip install -r requirements.txt\n"
        "python demo_build_vxu.py          # print sample HL7\n"
        "python cair_service.py            # start background worker"
    )

    pdf.output(str(output))


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "CAIR_Quick_Reference.pdf"
    build_pdf(out)
    print(f"Created: {out}")
