"""Database access for CAIR outbox and vaccination source data."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pyodbc

from cair_integration.models import (
    ClinicConfig,
    OutboxRecord,
    OutboxStatus,
    PatientData,
    VaccinationData,
    VxuPayload,
)


class OutboxRepository:
    def __init__(self, connection_string: str, clinic: ClinicConfig):
        self._conn_str = connection_string
        self._clinic = clinic

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self._conn_str, autocommit=False)

    def get_eligible_records(self, batch_size: int) -> List[OutboxRecord]:
        sql = """
            SELECT TOP (?)
                id, vaccination_id, status, attempt_count,
                next_retry_at, hl7_message, ack_response,
                error_message, created_at, updated_at
            FROM cair_outbox
            WHERE status = 'PENDING'
               OR (status = 'RETRY' AND next_retry_at <= SYSUTCDATETIME())
            ORDER BY
                CASE WHEN status = 'RETRY' THEN 0 ELSE 1 END,
                id
        """
        with self._connect() as conn:
            rows = conn.execute(sql, batch_size).fetchall()
            return [self._row_to_record(row) for row in rows]

    def claim_records(self, record_ids: List[int]) -> None:
        if not record_ids:
            return
        placeholders = ",".join("?" for _ in record_ids)
        sql = f"""
            UPDATE cair_outbox
            SET status = 'PROCESSING', updated_at = SYSUTCDATETIME()
            WHERE id IN ({placeholders})
              AND status IN ('PENDING', 'RETRY')
        """
        with self._connect() as conn:
            conn.execute(sql, record_ids)
            conn.commit()

    def load_vxu_payload(self, vaccination_id: int) -> VxuPayload:
        sql = """
            SELECT *
            FROM vw_cair_vxu_source
            WHERE vaccination_id = ?
        """
        with self._connect() as conn:
            row = conn.execute(sql, vaccination_id).fetchone()
            if row is None:
                raise ValueError(f"Vaccination {vaccination_id} not found in source view")

            columns = [col[0] for col in conn.cursor().description]
            data = dict(zip(columns, row))

        patient = PatientData(
            acc_no=str(data["patient_acc_no"]),
            last_name=data.get("patient_last_name") or "",
            first_name=data.get("patient_first_name") or "",
            middle_name=data.get("patient_middle_name") or "",
            date_of_birth=data["patient_dob"],
            sex=data.get("patient_sex") or "U",
            address_line1=data.get("patient_address") or "",
            city=data.get("patient_city") or "",
            state=data.get("patient_state") or "CA",
            zip_code=data.get("patient_zip") or "",
            phone=data.get("patient_phone") or "",
            cell_phone=data.get("patient_cell_phone") or "",
            email=data.get("patient_email") or "",
        )

        vaccination = VaccinationData(
            vaccination_id=int(data["vaccination_id"]),
            checkin_id=str(data["checkin_id"]),
            administration_datetime=data["administration_datetime"],
            cvx_code=str(data.get("cvx_code") or ""),
            ndc_number=str(data.get("ndc_number") or ""),
            dose_amount=str(data.get("dose_amount") or "999"),
            dose_unit=str(data.get("dose_unit") or ""),
            lot_number=str(data.get("lot_number") or ""),
            expiration_date=data.get("expiration_date"),
            manufacturer_code=str(data.get("manufacturer_code") or ""),
            manufacturer_name=str(data.get("manufacturer_name") or ""),
        )

        return VxuPayload(patient=patient, vaccination=vaccination, clinic=self._clinic)

    def mark_sent(self, outbox_id: int, hl7_message: str, ack_response: str) -> None:
        sql = """
            UPDATE cair_outbox
            SET status = 'SENT',
                hl7_message = ?,
                ack_response = ?,
                error_message = NULL,
                updated_at = SYSUTCDATETIME()
            WHERE id = ?
        """
        with self._connect() as conn:
            conn.execute(sql, hl7_message, ack_response, outbox_id)
            conn.commit()

    def mark_retry(
        self,
        outbox_id: int,
        attempt_count: int,
        next_retry_at: datetime,
        error_message: str,
        hl7_message: Optional[str] = None,
        ack_response: Optional[str] = None,
    ) -> None:
        sql = """
            UPDATE cair_outbox
            SET status = 'RETRY',
                attempt_count = ?,
                next_retry_at = ?,
                error_message = ?,
                hl7_message = COALESCE(?, hl7_message),
                ack_response = COALESCE(?, ack_response),
                updated_at = SYSUTCDATETIME()
            WHERE id = ?
        """
        with self._connect() as conn:
            conn.execute(
                sql,
                attempt_count,
                next_retry_at,
                error_message[:500],
                hl7_message,
                ack_response,
                outbox_id,
            )
            conn.commit()

    def mark_failed(
        self,
        outbox_id: int,
        error_message: str,
        hl7_message: Optional[str] = None,
        ack_response: Optional[str] = None,
    ) -> None:
        sql = """
            UPDATE cair_outbox
            SET status = 'FAILED',
                error_message = ?,
                hl7_message = COALESCE(?, hl7_message),
                ack_response = COALESCE(?, ack_response),
                updated_at = SYSUTCDATETIME()
            WHERE id = ?
        """
        with self._connect() as conn:
            conn.execute(sql, error_message[:500], hl7_message, ack_response, outbox_id)
            conn.commit()

    def create_outbox_for_vaccination(self, vaccination_id: int) -> int:
        """Call from vaccination save flow inside same transaction."""
        sql = """
            INSERT INTO cair_outbox (vaccination_id, status, attempt_count)
            OUTPUT INSERTED.id
            VALUES (?, 'PENDING', 0)
        """
        with self._connect() as conn:
            row = conn.execute(sql, vaccination_id).fetchone()
            conn.commit()
            return int(row[0])

    def has_eligible_work(self) -> bool:
        sql = """
            SELECT TOP 1 1
            FROM cair_outbox
            WHERE status = 'PENDING'
               OR (status = 'RETRY' AND next_retry_at <= SYSUTCDATETIME())
        """
        with self._connect() as conn:
            return conn.execute(sql).fetchone() is not None

    @staticmethod
    def _row_to_record(row) -> OutboxRecord:
        return OutboxRecord(
            id=row.id,
            vaccination_id=row.vaccination_id,
            clinic_id=row.clinic_id if hasattr(row, "clinic_id") else 0,
            status=OutboxStatus(row.status),
            attempt_count=row.attempt_count,
            next_retry_at=row.next_retry_at,
            hl7_message=row.hl7_message,
            ack_response=row.ack_response,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class MasterRepository:
    def __init__(self, connection_string: str):
        self._conn_str = connection_string

    def get_active_clinics(self) -> List[ClinicConfig]:
        sql = """
            SELECT clinic_id, clinic_name, db_connection_string,
                   sending_application, sending_facility_id,
                   responsible_org_id, receiving_facility, processing_id, is_active
            FROM clinic_registry
            WHERE is_active = 1
        """
        with pyodbc.connect(self._conn_str) as conn:
            rows = conn.execute(sql).fetchall()
            return [
                ClinicConfig(
                    clinic_id=row.clinic_id,
                    clinic_name=row.clinic_name,
                    db_connection_string=row.db_connection_string,
                    sending_application=row.sending_application or "",
                    sending_facility_id=row.sending_facility_id,
                    responsible_org_id=getattr(row, "responsible_org_id", None) or row.sending_facility_id,
                    receiving_facility=row.receiving_facility,
                    processing_id=row.processing_id,
                    is_active=bool(row.is_active),
                )
                for row in rows
            ]
