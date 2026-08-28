"""Data models for CAIR VXU integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    RETRY = "RETRY"
    FAILED = "FAILED"


@dataclass
class ClinicConfig:
    clinic_id: int
    clinic_name: str
    db_connection_string: str
    sending_application: str = ""
    sending_facility_id: str = ""  # MSH-4, PID-3.4 — CAIR org code e.g. SF-013259
    responsible_org_id: str = ""  # MSH-22, RXA-11.4 — site where vaccine was given
    receiving_facility: str = "CAIR2"
    processing_id: str = "P"  # P=production, T=training (ONB for onboarding)
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.responsible_org_id:
            self.responsible_org_id = self.sending_facility_id


@dataclass
class PatientData:
    acc_no: str
    last_name: str
    first_name: str
    middle_name: str = ""
    suffix: str = ""
    mothers_maiden_last: str = ""
    mothers_maiden_first: str = ""
    date_of_birth: datetime = field(default_factory=datetime.now)
    sex: str = "U"  # M, F, X, U
    race_code: str = ""
    race_text: str = ""
    address_line1: str = ""
    city: str = ""
    state: str = "CA"
    zip_code: str = ""
    phone: str = ""
    cell_phone: str = ""
    email: str = ""
    language_code: str = "ENG"
    language_text: str = "English"
    ethnic_code: str = ""
    ethnic_text: str = ""
    multiple_birth: str = "N"
    birth_order: str = ""
    death_indicator: str = ""
    protection_indicator: str = "Y"
    protection_effective_date: Optional[datetime] = None


@dataclass
class VaccinationData:
    vaccination_id: int
    checkin_id: str
    administration_datetime: datetime
    cvx_code: str = ""
    ndc_number: str = ""
    vaccine_description: str = ""
    dose_amount: str = "999"
    dose_unit: str = ""
    lot_number: str = ""
    expiration_date: Optional[datetime] = None
    manufacturer_code: str = ""
    manufacturer_name: str = ""
    route_code: str = ""
    route_text: str = ""
    site_code: str = ""
    site_text: str = ""
    vfc_eligibility_code: str = "V01"
    vfc_eligibility_text: str = "Not VFC eligible"
    ordering_provider_npi: str = ""
    ordering_provider_last: str = ""
    ordering_provider_first: str = ""
    administering_provider_npi: str = ""
    administering_provider_last: str = ""
    administering_provider_first: str = ""


@dataclass
class VxuPayload:
    """All data needed to build one VXU message."""

    patient: PatientData
    vaccination: VaccinationData
    clinic: ClinicConfig


@dataclass
class OutboxRecord:
    id: int
    vaccination_id: int
    clinic_id: int
    status: OutboxStatus
    attempt_count: int
    next_retry_at: Optional[datetime]
    hl7_message: Optional[str]
    ack_response: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class CairSendResult:
    success: bool
    temporary_error: bool
    ack_code: str = ""
    error_details: str = ""
    raw_response: str = ""
