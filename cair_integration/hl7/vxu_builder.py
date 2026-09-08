"""HL7 v2.5.1 VXU message builder for CAIR2.

Field mappings follow:
- CAIR2_HL7v2.5.1DataExchangeSpecs.pdf (v3.10)
- Required Fields mapping with DB 2-11-2021_Modified (2).xlsx
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from cair_integration.models import VxuPayload


FIELD_SEPARATOR = "|"
ENCODING_CHARS = "^~\\&"


def _hl7_datetime(dt: datetime) -> str:
    """Format datetime as HL7 TS: YYYYMMDDHHMMSS±ZZZZ."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y%m%d%H%M%S%z")


def _hl7_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _escape_component(value: str) -> str:
    """Escape HL7 special chars inside a component (free text)."""
    if not value:
        return ""
    value = value.replace("\\", "\\E\\")
    value = value.replace("|", "\\F\\")
    value = value.replace("^", "\\S\\")
    value = value.replace("&", "\\T\\")
    value = value.replace("~", "\\R\\")
    return value


def _escape_field(value: str) -> str:
    """Escape only field-level delimiters; preserve ^ component separators."""
    if not value:
        return ""
    value = value.replace("\\", "\\E\\")
    value = value.replace("|", "\\F\\")
    return value


def _join_fields(fields: List[Optional[str]]) -> str:
    return FIELD_SEPARATOR.join(_escape_field(f) if f is not None else "" for f in fields)


def _format_name(last: str, first: str, middle: str = "", suffix: str = "") -> str:
    return (
        f"{_escape_component(last)}^{_escape_component(first)}"
        f"^{_escape_component(middle)}^{_escape_component(suffix)}^^^^L"
    )


def _format_phone_entry(phone: str, phone_type: str = "PH") -> str:
    """Format one PID-13 repetition: ^PRN^PH^^^area^number or ^PRN^CP^^^area^number."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) >= 10:
        area = digits[-10:-7]
        local = digits[-7:]
        return "^PRN^" + phone_type + "^^^" + area + "^" + local
    return ""


def _format_email_entry(email: str) -> str:
    """Format PID-13 email repetition: ^NET^Internet^email@example.com."""
    if not email or "@" not in email:
        return ""
    return f"^NET^Internet^{_escape_component(email.strip())}"


def _format_pid13(home_phone: str, cell_phone: str, email: str) -> str:
    """Build PID-13 per CAIR email requirements."""
    parts: List[str] = []
    home = _format_phone_entry(home_phone, "PH")
    cell = _format_phone_entry(cell_phone, "CP")
    mail = _format_email_entry(email)

    if home:
        parts.append(home)
    if mail:
        parts.append(mail)
    if cell:
        parts.append(cell)

    return "~".join(parts)


def _sanitize_address_line(value: str) -> str:
    cleaned = re.sub(r"[*?<>]", "", (value or "").strip())
    if not cleaned or cleaned.upper().startswith("ADDRESS"):
        return ""
    return cleaned


def _format_ndc(ndc_number: str) -> str:
    digits = "".join(c for c in ndc_number if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:5]}-{digits[5:9]}-{digits[9:11]}"
    if len(digits) == 10:
        return f"{digits[:4]}-{digits[4:8]}-{digits[8:10]}"
    return ndc_number.strip()


def _format_dose_amount(value: str) -> str:
    text = (value or "").strip()
    if not text or text == "999":
        return "999"
    try:
        return format(float(text), "g")
    except ValueError:
        return text


def _format_provider(npi: str, last: str, first: str, degree: str = "") -> str:
    """Format XCN for ORC-12 / RXA-10.

    Components: 1=ID, 2=Family, 3=Given, 9=AssigningAuthority (HD), 13=ID type,
    21=Professional suffix (MD/NP/RN from Providers.Degree/Title).
    HD assigning authority: NPPES&2.16.840.1.113883.4.6&ISO
    (& are subcomponent separators — do not escape).
    """
    if not npi:
        return ""
    suffix = (degree or "").strip()
    components = [""] * (22 if suffix else 14)
    components[1] = _escape_component(npi)
    components[2] = _escape_component(last)
    components[3] = _escape_component(first)
    components[9] = "NPPES&2.16.840.1.113883.4.6&ISO"
    components[13] = "NPI"
    if suffix:
        components[21] = _escape_component(suffix)
    return "^".join(components[1:])


def _provider_org_id(payload: VxuPayload) -> str:
    return payload.clinic.provider_org_id or ""


def build_msh(payload: VxuPayload, message_control_id: str) -> str:
    clinic = payload.clinic
    now = _hl7_datetime(datetime.now(timezone.utc))
    fields = [
        clinic.sending_application,
        clinic.sending_facility_id,
        "",
        clinic.receiving_facility,
        now,
        "",
        "VXU^V04^VXU_V04",
        message_control_id,
        clinic.processing_id,
        "2.5.1",
        "",
        "",
        "AL",
        "AL",
        "",
        "",
        "",
        "",
        "Z22^CDCPHINVS",
        _provider_org_id(payload),
    ]
    return f"MSH|{ENCODING_CHARS}|{_join_fields(fields)}"


def build_pid(payload: VxuPayload) -> str:
    p = payload.patient
    clinic = payload.clinic
    patient_id = (
        _escape_component(p.acc_no)
        + "^^^"
        + _escape_component(clinic.sending_facility_id)
        + "^MR"
    )
    name = _format_name(p.last_name, p.first_name, p.middle_name, p.suffix)
    mothers_name = (
        f"{_escape_component(p.mothers_maiden_last)}^{_escape_component(p.mothers_maiden_first)}^^^^^M"
        if p.mothers_maiden_last
        else ""
    )
    race = f"{_escape_component(p.race_code)}^^CDCREC" if p.race_code else ""
    address_line = _sanitize_address_line(p.address_line1)
    address = ""
    if address_line and p.city and p.state and p.zip_code:
        address = (
            f"{_escape_component(address_line)}^^{_escape_component(p.city)}"
            f"^{_escape_component(p.state)}^{_escape_component(p.zip_code)}^^H"
        )
    phone = _format_pid13(p.phone, p.cell_phone, p.email)
    language = f"{p.language_code}^{p.language_text}^HL70296" if p.language_code else ""
    ethnic = f"{_escape_component(p.ethnic_code)}^^CDCREC" if p.ethnic_code else ""

    fields = [
        "PID",
        "1",
        "",
        patient_id,
        "",
        name,
        mothers_name,
        _hl7_date(p.date_of_birth),
        p.sex,
        "",
        race,
        address,
        "",
        phone,
        "",
        language,
        "",
        "",
        "",
        "",
        "",
        "",
        ethnic,
        "",
        p.multiple_birth or "N",
        p.birth_order,
        "",
        "",
        "",
        "",
        p.death_indicator,
    ]
    return _join_fields(fields)


def build_pd1(payload: VxuPayload) -> str:
    p = payload.patient
    protection_date = _hl7_date(p.protection_effective_date) if p.protection_effective_date else ""
    fields = [
        "PD1",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        p.protection_indicator or "N",
        protection_date,
        "",
        "",
        "",
        "",
    ]
    return _join_fields(fields)


def build_orc(payload: VxuPayload) -> str:
    v = payload.vaccination
    clinic = payload.clinic
    provider = _format_provider(
        v.ordering_provider_npi or v.administering_provider_npi,
        v.ordering_provider_last or v.administering_provider_last,
        v.ordering_provider_first or v.administering_provider_first,
        v.ordering_provider_degree or v.administering_provider_degree,
    )
    fields = [
        "ORC",
        "RE",
        "",
        f"{v.checkin_id}^{_escape_component(clinic.sending_facility_id)}",
        f"{v.checkin_id}^{_escape_component(clinic.sending_facility_id)}",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        provider,
        "",
        "",
        "",
        "",
        "",
    ]
    return _join_fields(fields)


def build_rxa(payload: VxuPayload) -> str:
    v = payload.vaccination
    clinic = payload.clinic

    if v.cvx_code:
        administered_code = (
            f"{_escape_component(v.cvx_code)}^{_escape_component(v.vaccine_description)}^CVX"
        )
    elif v.ndc_number:
        administered_code = f"{_escape_component(_format_ndc(v.ndc_number))}^^NDC"
    else:
        administered_code = ""

    dose_amount = _format_dose_amount(v.dose_amount)
    # CAIR PDF: if RXA-6 supplied, unit should be mL^mL^UCUM
    dose_unit = "mL^mL^UCUM" if dose_amount != "999" else ""
    admin_notes = "00^NEW IMMUNIZATION RECORD^NIP001"

    provider = _format_provider(
        v.administering_provider_npi or v.ordering_provider_npi,
        v.administering_provider_last or v.ordering_provider_last,
        v.administering_provider_first or v.ordering_provider_first,
        v.administering_provider_degree or v.ordering_provider_degree,
    )

    site_org = _provider_org_id(payload)
    location = f"^^^{site_org}" if site_org else ""
    expiration = _hl7_date(v.expiration_date) if v.expiration_date else ""
    manufacturer = (
        f"{_escape_component(v.manufacturer_code)}^^{_escape_component(v.manufacturer_name)}^MVX"
        if v.manufacturer_code
        else ""
    )
    system_entry = _hl7_datetime(datetime.now(timezone.utc))

    fields = [
        "RXA",
        "0",
        "1",
        _hl7_date(v.administration_datetime),
        "",
        administered_code,
        dose_amount,
        dose_unit,
        "",
        admin_notes,
        provider,
        location,
        "",
        "",
        "",
        v.lot_number,
        expiration,
        manufacturer,
        "",
        "",
        "CP",
        "A",
        system_entry,
    ]
    return _join_fields(fields)


def build_rxr(payload: VxuPayload) -> str:
    v = payload.vaccination
    if not v.route_code and not v.site_code:
        return ""
    route = f"{v.route_code}^{v.route_text}^NCIT" if v.route_code else ""
    site = f"{v.site_code}^{v.site_text}^HL70163" if v.site_code else ""
    return _join_fields(["RXR", route, site])


def build_obx_vfc(payload: VxuPayload) -> str:
    v = payload.vaccination
    obs_value = f"{v.vfc_eligibility_code}^{v.vfc_eligibility_text}^HL70064"
    obs_datetime = _hl7_date(v.administration_datetime)

    fields = [
        "OBX",
        "1",
        "CE",
        "64994-7^Vaccine funding program eligibility category^LN",
        "1",
        obs_value,
        "",
        "",
        "",
        "",
        "F",
        "",
        "",
        "",
        obs_datetime,
    ]
    return _join_fields(fields)


def build_obx_funding_source(payload: VxuPayload) -> str:
    v = payload.vaccination
    obs_value = f"{v.funding_source_code}^{v.funding_source_text}^CDCPHINVS"
    obs_datetime = _hl7_date(v.administration_datetime)

    fields = [
        "OBX",
        "2",
        "CE",
        "30963-3^Vaccine funding source^LN",
        "1",
        obs_value,
        "",
        "",
        "",
        "",
        "F",
        "",
        "",
        "",
        obs_datetime,
    ]
    return _join_fields(fields)


def build_vxu_message(payload: VxuPayload, message_control_id: Optional[str] = None) -> str:
    """Build a complete CAIR2 VXU HL7 v2.5.1 message."""
    control_id = message_control_id or str(uuid.uuid4())
    segments = [
        build_msh(payload, control_id),
        build_pid(payload),
        build_pd1(payload),
        build_orc(payload),
        build_rxa(payload),
    ]

    rxr = build_rxr(payload)
    if rxr:
        segments.append(rxr)

    segments.append(build_obx_vfc(payload))
    segments.append(build_obx_funding_source(payload))
    return "\r".join(segments) + "\r"
