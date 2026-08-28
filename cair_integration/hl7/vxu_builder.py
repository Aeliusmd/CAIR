"""HL7 v2.5.1 VXU message builder for CAIR2.

Field mappings follow:
- CAIR2_HL7v2.5.1DataExchangeSpecs.pdf (v3.10)
- Required Fields mapping with DB 2-11-2021_Modified (2).xlsx
"""

from __future__ import annotations

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
    """Build PID-13 per CAIR email requirements.

    CAIR requires at least one of home phone, cell phone, or email.
    Multiple values are joined with ~ (repetition separator).
    """
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
        clinic.responsible_org_id or clinic.sending_facility_id,
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
    race = f"{_escape_component(p.race_code)}^{_escape_component(p.race_text)}^CDCREC" if p.race_code else ""
    address = (
        f"{_escape_component(p.address_line1)}^^{_escape_component(p.city)}"
        f"^{_escape_component(p.state)}^{_escape_component(p.zip_code)}^^H"
    )
    phone = _format_pid13(p.phone, p.cell_phone, p.email)
    language = f"{p.language_code}^{p.language_text}^HL70296" if p.language_code else ""
    ethnic = f"{p.ethnic_code}^{p.ethnic_text}^CDCREC" if p.ethnic_code else ""

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
        p.protection_indicator or "Y",
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
        "",
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

    # CAIR accepts CVX or NDC, not both. Prefer CVX when available.
    if v.cvx_code:
        administered_code = (
            f"{_escape_component(v.cvx_code)}^{_escape_component(v.vaccine_description)}^CVX"
        )
    elif v.ndc_number:
        # CAIR sample uses dashed NDC with empty description: 00069-1000-03^^NDC
        administered_code = f"{_escape_component(v.ndc_number)}^^NDC"
    else:
        administered_code = ""

    if v.dose_amount and v.dose_amount != "999":
        dose_unit = "mL^^UCUM"
    else:
        dose_unit = ""
    admin_notes = "00^NEW IMMUNIZATION RECORD^NIP001"

    provider = ""
    if v.administering_provider_npi:
        provider = (
            f"{v.administering_provider_npi}^{v.administering_provider_last}^"
            f"{v.administering_provider_first}^^^^^^NPPES^^^^NPI^^^^^^^^"
        )

    location = f"^^^{clinic.responsible_org_id or clinic.sending_facility_id}"
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
        v.dose_amount or "999",
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


def build_obx(payload: VxuPayload) -> str:
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

    segments.append(build_obx(payload))
    return "\r".join(segments) + "\r"
