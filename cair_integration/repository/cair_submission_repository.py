"""Database access using ClaudMD tables for CAIR submission.

Tables used (no new tables required):
  - EHRHeaders              -> IsPublish = 1 means visit is ready
  - EHRVaccines             -> vaccine clinical data
  - EHRVaccineThirdPartySubmissions -> queue + status tracking
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import List, Optional, Union

import pyodbc

from cair_integration.config import Settings, build_clinic_db_connection
from cair_integration.constants import FAILED, PENDING, PROCESSING, RETRY, SUCCESS
from cair_integration.models import (
    CairSubmissionRecord,
    ClinicConfig,
    PatientData,
    VaccinationData,
    VxuPayload,
)

# ClaudMD GenderId -> HL7 PID-8 (confirm with EMR team if needed)
GENDER_MAP = {1: "M", 2: "F", 3: "U", 4: "X"}


def _combine_datetime(
    d: Optional[Union[date, datetime]],
    t: Optional[time],
    fallback: datetime,
) -> datetime:
    if d is None:
        return fallback
    if isinstance(d, datetime):
        d = d.date()
    if t is None:
        return datetime.combine(d, time(0, 0), tzinfo=timezone.utc)
    return datetime.combine(d, t, tzinfo=timezone.utc)


class CairSubmissionRepository:
    def __init__(self, connection_string: str, clinic: ClinicConfig):
        self._conn_str = connection_string
        self._clinic = clinic

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self._conn_str, autocommit=False)

    def get_eligible_submissions(self, batch_size: int) -> List[CairSubmissionRecord]:
        """Published visits with pending or due-retry CAIR submissions."""
        sql = """
            SELECT TOP (?)
                s.Id,
                s.EHRVaccineId,
                s.SubmitStatus,
                s.AttemptCount,
                v.CheckInId,
                s.ErrorMessage
            FROM dbo.EHRVaccineThirdPartySubmissions s
            INNER JOIN dbo.EHRVaccines v
                ON v.Id = s.EHRVaccineId AND v.IsDeleted = 0
            INNER JOIN dbo.EHRHeaders h
                ON h.CheckinId = v.CheckInId
               AND h.IsPublish = 1
               AND h.IsDeleted = 0
            WHERE s.IsDeleted = 0
              AND (
                    s.SubmitStatus = ?
                 OR (
                        s.SubmitStatus = ?
                    AND s.LastAttemptDateTime IS NOT NULL
                    AND s.LastAttemptDateTime <= DATEADD(MINUTE, -5, SYSDATETIMEOFFSET())
                 )
              )
            ORDER BY
                CASE WHEN s.SubmitStatus = ? THEN 0 ELSE 1 END,
                s.Id
        """
        with self._connect() as conn:
            rows = conn.execute(
                sql, batch_size, PENDING, RETRY, RETRY
            ).fetchall()
            return [
                CairSubmissionRecord(
                    id=row.Id,
                    ehr_vaccine_id=row.EHRVaccineId,
                    submit_status=row.SubmitStatus,
                    attempt_count=row.AttemptCount,
                    checkin_id=row.CheckInId,
                    error_message=row.ErrorMessage,
                )
                for row in rows
            ]

    def claim_submissions(self, submission_ids: List[int]) -> None:
        if not submission_ids:
            return
        placeholders = ",".join("?" for _ in submission_ids)
        sql = f"""
            UPDATE dbo.EHRVaccineThirdPartySubmissions
            SET SubmitStatus = ?,
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id IN ({placeholders})
              AND SubmitStatus IN (?, ?)
        """
        with self._connect() as conn:
            params: list = [PROCESSING, *submission_ids, PENDING, RETRY]
            conn.execute(sql, params)
            conn.commit()

    def load_vxu_payload(self, submission_id: int) -> VxuPayload:
        sql = """
            SELECT
                s.Id AS submission_id,
                v.Id AS vaccination_id,
                v.CheckInId AS checkin_id,
                ci.CheckInDate,
                ci.CheckInTime,
                p.AccountNumber AS patient_acc_no,
                p.LastName AS patient_last_name,
                p.FirstName AS patient_first_name,
                p.Initials AS patient_middle_name,
                p.DateOfBirth AS patient_dob,
                p.GenderId AS patient_gender_id,
                p.HomePhone AS patient_phone,
                p.CellPhone AS patient_cell_phone,
                p.Email AS patient_email,
                p.Address1 AS patient_address,
                p.City AS patient_city,
                p.State AS patient_state,
                p.ZipCode AS patient_zip,
                sc.NDCNumber AS ndc_number,
                sc.Description AS vaccine_description,
                v.LotNumber AS lot_number,
                v.VaccineExpirationDate AS expiration_date,
                v.Manufacturer AS manufacturer_name,
                v.Dosage AS dose_amount,
                v.Route AS route_text,
                v.BodySite AS site_text,
                v.VaccineDate AS vaccine_date,
                v.VaccineTime AS vaccine_time
            FROM dbo.EHRVaccineThirdPartySubmissions s
            INNER JOIN dbo.EHRVaccines v ON v.Id = s.EHRVaccineId
            INNER JOIN dbo.EHRHeaders h
                ON h.CheckinId = v.CheckInId AND h.IsPublish = 1 AND h.IsDeleted = 0
            INNER JOIN dbo.CheckInsHeader ci ON ci.Id = v.CheckInId AND ci.IsDeleted = 0
            INNER JOIN dbo.Patients p ON p.Id = ci.PatientId AND p.IsDeleted = 0
            LEFT JOIN dbo.ServiceCodes sc ON sc.Id = v.ServiceCodeId
            WHERE s.Id = ?
        """
        with self._connect() as conn:
            row = conn.execute(sql, submission_id).fetchone()
            if row is None:
                raise ValueError(f"Submission {submission_id} not found or visit not published")

        gender = GENDER_MAP.get(row.patient_gender_id, "U")
        admin_dt = _combine_datetime(
            row.vaccine_date.date() if row.vaccine_date else row.CheckInDate,
            row.vaccine_time,
            row.vaccine_date or datetime.now(timezone.utc),
        )

        patient = PatientData(
            acc_no=str(row.patient_acc_no),
            last_name=row.patient_last_name or "",
            first_name=row.patient_first_name or "",
            middle_name=row.patient_middle_name or "",
            date_of_birth=row.patient_dob,
            sex=gender,
            address_line1=row.patient_address or "",
            city=row.patient_city or "",
            state=row.patient_state or "CA",
            zip_code=row.patient_zip or "",
            phone=row.patient_phone or "",
            cell_phone=row.patient_cell_phone or "",
            email=row.patient_email or "",
        )

        vaccination = VaccinationData(
            vaccination_id=int(row.vaccination_id),
            checkin_id=str(row.checkin_id),
            administration_datetime=admin_dt,
            ndc_number=str(row.ndc_number or ""),
            vaccine_description=row.vaccine_description or row.manufacturer_name or "",
            dose_amount=str(row.dose_amount or "999"),
            lot_number=str(row.lot_number or ""),
            expiration_date=row.expiration_date,
            manufacturer_name=str(row.manufacturer_name or ""),
            route_text=str(row.route_text or ""),
            site_text=str(row.site_text or ""),
        )

        return VxuPayload(patient=patient, vaccination=vaccination, clinic=self._clinic)

    def mark_success(
        self,
        submission_id: int,
        ehr_vaccine_id: int,
        hl7_message: str,
        ack_response: str,
        external_reference_id: Optional[str] = None,
    ) -> None:
        sql_submission = """
            UPDATE dbo.EHRVaccineThirdPartySubmissions
            SET SubmitStatus = ?,
                SubmittedDateTime = SYSDATETIMEOFFSET(),
                LastAttemptDateTime = SYSDATETIMEOFFSET(),
                ExternalReferenceId = ?,
                ErrorMessage = NULL,
                RequestPayload = ?,
                ResponsePayload = ?,
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id = ?
        """
        sql_vaccine = """
            UPDATE dbo.EHRVaccines
            SET IsSubmitted = 1,
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id = ?
        """
        with self._connect() as conn:
            conn.execute(
                sql_submission,
                SUCCESS,
                external_reference_id,
                hl7_message,
                ack_response,
                submission_id,
            )
            conn.execute(sql_vaccine, ehr_vaccine_id)
            conn.commit()

    def mark_retry(
        self,
        submission_id: int,
        attempt_count: int,
        error_message: str,
        hl7_message: Optional[str] = None,
        ack_response: Optional[str] = None,
    ) -> None:
        sql = """
            UPDATE dbo.EHRVaccineThirdPartySubmissions
            SET SubmitStatus = ?,
                AttemptCount = ?,
                LastAttemptDateTime = SYSDATETIMEOFFSET(),
                ErrorMessage = ?,
                RequestPayload = COALESCE(?, RequestPayload),
                ResponsePayload = COALESCE(?, ResponsePayload),
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id = ?
        """
        with self._connect() as conn:
            conn.execute(
                sql,
                RETRY,
                attempt_count,
                error_message[:2000],
                hl7_message,
                ack_response,
                submission_id,
            )
            conn.commit()

    def mark_failed(
        self,
        submission_id: int,
        error_message: str,
        hl7_message: Optional[str] = None,
        ack_response: Optional[str] = None,
    ) -> None:
        sql = """
            UPDATE dbo.EHRVaccineThirdPartySubmissions
            SET SubmitStatus = ?,
                LastAttemptDateTime = SYSDATETIMEOFFSET(),
                ErrorMessage = ?,
                RequestPayload = COALESCE(?, RequestPayload),
                ResponsePayload = COALESCE(?, ResponsePayload),
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id = ?
        """
        with self._connect() as conn:
            conn.execute(
                sql,
                FAILED,
                error_message[:2000],
                hl7_message,
                ack_response,
                submission_id,
            )
            conn.commit()

    def has_eligible_work(self) -> bool:
        sql = """
            SELECT TOP 1 1
            FROM dbo.EHRVaccineThirdPartySubmissions s
            INNER JOIN dbo.EHRVaccines v ON v.Id = s.EHRVaccineId AND v.IsDeleted = 0
            INNER JOIN dbo.EHRHeaders h
                ON h.CheckinId = v.CheckInId AND h.IsPublish = 1 AND h.IsDeleted = 0
            WHERE s.IsDeleted = 0
              AND s.SubmitStatus IN (?, ?)
        """
        with self._connect() as conn:
            return conn.execute(sql, PENDING, RETRY).fetchone() is not None


class MasterRepository:
    """Reads active clinics from ClaudMD_QA_Setup.dbo.ClinicSetup."""

    def __init__(self, connection_string: str, settings: Settings):
        self._conn_str = connection_string
        self._settings = settings

    def get_active_clinics(self) -> List[ClinicConfig]:
        sql = """
            SELECT ClinicID, ClinicName, DatabaseServer, DatabaseUser,
                   DatabasePassword, DatabaseName, Active, ActivationKey
            FROM dbo.ClinicSetup
            WHERE Active = 1
        """
        with pyodbc.connect(self._conn_str) as conn:
            rows = conn.execute(sql).fetchall()

        clinics = []
        for row in rows:
            conn_str = build_clinic_db_connection(
                row.DatabaseServer,
                row.DatabaseName,
                row.DatabaseUser,
                row.DatabasePassword,
            )
            clinics.append(
                ClinicConfig(
                    clinic_id=row.ClinicID,
                    clinic_name=row.ClinicName,
                    db_connection_string=conn_str,
                    sending_facility_id=self._settings.sending_facility_id,
                    responsible_org_id=self._settings.responsible_org_id,
                    receiving_facility=self._settings.receiving_facility,
                    processing_id=self._settings.processing_id,
                )
            )
        return clinics
