#!/usr/bin/env python3
"""Build sample VXU messages matching CAIR email samples."""

from __future__ import annotations

from datetime import datetime, timezone

from cair_integration.hl7.vxu_builder import build_vxu_message
from cair_integration.models import ClinicConfig, PatientData, VaccinationData, VxuPayload


def build_cair_email_sample() -> str:
    """Reproduce the official CAIR sample from cair emails.txt."""
    clinic = ClinicConfig(
        clinic_id=1,
        clinic_name="Aeliusmd Clinic",
        db_connection_string="",
        sending_facility_id="CA0012345",
        responsible_org_id="CA0054321",
        receiving_facility="CAIR2",
    )

    patient = PatientData(
        acc_no="AC10293",
        last_name="Alvarez",
        first_name="Maria",
        date_of_birth=datetime(1988, 4, 12),
        sex="F",
        race_code="2106-3",
        address_line1="123 Main St",
        city="Sacramento",
        state="CA",
        zip_code="95814",
        cell_phone="9165550134",
        email="maria.alvarez@example.com",
        ethnic_code="2186-5",
        protection_indicator="N",
        protection_effective_date=datetime(2026, 8, 10),
    )

    vaccination = VaccinationData(
        vaccination_id=1,
        checkin_id="48213",
        administration_datetime=datetime(2026, 8, 10),
        ndc_number="00069-1000-03",
        dose_amount="0.3",
        lot_number="FA7205",
        manufacturer_code="PFR",
        vfc_eligibility_code="V01",
        vfc_eligibility_text="Not VFC eligible",
    )

    payload = VxuPayload(patient=patient, vaccination=vaccination, clinic=clinic)
    return build_vxu_message(
        payload,
        message_control_id="3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    )


def main() -> None:
    message = build_cair_email_sample()
    print(message.replace("\r", "\n"))


if __name__ == "__main__":
    main()
