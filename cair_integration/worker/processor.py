"""Process CAIR submissions from EHRVaccineThirdPartySubmissions."""

from __future__ import annotations

import logging

from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import Settings
from cair_integration.hl7.vxu_builder import build_vxu_message
from cair_integration.constants import FAILED, PENDING, PROCESSING, RETRY, SUCCESS
from cair_integration.models import CairSubmissionRecord, ClinicConfig
from cair_integration.repository.cair_submission_repository import CairSubmissionRepository
from cair_integration.submission_log import log_submission_event

logger = logging.getLogger(__name__)

_STATUS_NAME = {
    PENDING: "PENDING",
    PROCESSING: "PROCESSING",
    SUCCESS: "SUCCESS",
    FAILED: "FAILED",
    RETRY: "RETRY",
}


def _extract_message_control_id(hl7_message: str) -> str:
    for line in hl7_message.replace("\r", "\n").split("\n"):
        if line.startswith("MSH|"):
            fields = line.split("|")
            if len(fields) > 9:
                return fields[9]
    return ""


class SubmissionProcessor:
    def __init__(self, settings: Settings, cair_client: CairSoapClient, clinic: ClinicConfig):
        self._settings = settings
        self._cair = cair_client
        self._clinic = clinic

    def process_submission(self, repo: CairSubmissionRepository, record: CairSubmissionRecord) -> None:
        log_submission_event(
            "PROCESSING",
            submission_id=record.id,
            vaccine_id=record.ehr_vaccine_id,
            checkin_id=record.checkin_id,
            clinic_id=self._clinic.clinic_id,
            clinic_name=self._clinic.clinic_name,
            attempt=record.attempt_count,
            prior_status=_STATUS_NAME.get(record.submit_status, str(record.submit_status)),
        )
        try:
            payload = repo.load_vxu_payload(record.id)
            hl7_message = build_vxu_message(payload)
            result = self._cair.send_vxu(hl7_message)
            control_id = _extract_message_control_id(hl7_message)

            if result.success:
                repo.mark_success(
                    submission_id=record.id,
                    ehr_vaccine_id=record.ehr_vaccine_id,
                    hl7_message=hl7_message,
                    ack_response=result.raw_response,
                    external_reference_id=control_id or None,
                )
                log_submission_event(
                    "SUCCESS",
                    submission_id=record.id,
                    vaccine_id=record.ehr_vaccine_id,
                    checkin_id=record.checkin_id,
                    clinic_id=self._clinic.clinic_id,
                    clinic_name=self._clinic.clinic_name,
                    attempt=record.attempt_count,
                    ack_code=result.ack_code or "AA",
                    message_control_id=control_id or "",
                )
                logger.info(
                    "Submission %s sent for EHRVaccine %s (check-in %s)",
                    record.id,
                    record.ehr_vaccine_id,
                    record.checkin_id,
                )
                return

            error = result.error_details or f"ACK code: {result.ack_code}"
            if result.temporary_error and record.attempt_count + 1 < self._settings.max_retry_attempts:
                next_attempt = record.attempt_count + 1
                repo.mark_retry(
                    submission_id=record.id,
                    attempt_count=next_attempt,
                    error_message=error,
                    hl7_message=hl7_message,
                    ack_response=result.raw_response,
                )
                log_submission_event(
                    "RETRY",
                    submission_id=record.id,
                    vaccine_id=record.ehr_vaccine_id,
                    checkin_id=record.checkin_id,
                    clinic_id=self._clinic.clinic_id,
                    clinic_name=self._clinic.clinic_name,
                    attempt=next_attempt,
                    ack_code=result.ack_code,
                    error=error,
                )
                logger.warning("Submission %s scheduled for retry: %s", record.id, error)
                return

            repo.mark_failed(
                submission_id=record.id,
                error_message=error,
                hl7_message=hl7_message,
                ack_response=result.raw_response,
            )
            log_submission_event(
                "FAILED",
                submission_id=record.id,
                vaccine_id=record.ehr_vaccine_id,
                checkin_id=record.checkin_id,
                clinic_id=self._clinic.clinic_id,
                clinic_name=self._clinic.clinic_name,
                attempt=record.attempt_count,
                ack_code=result.ack_code,
                error=error,
            )
            logger.error("Submission %s failed permanently: %s", record.id, error)

        except Exception as exc:
            if record.attempt_count + 1 < self._settings.max_retry_attempts:
                next_attempt = record.attempt_count + 1
                repo.mark_retry(
                    submission_id=record.id,
                    attempt_count=next_attempt,
                    error_message=str(exc),
                )
                log_submission_event(
                    "RETRY",
                    submission_id=record.id,
                    vaccine_id=record.ehr_vaccine_id,
                    checkin_id=record.checkin_id,
                    clinic_id=self._clinic.clinic_id,
                    clinic_name=self._clinic.clinic_name,
                    attempt=next_attempt,
                    error=str(exc),
                )
            else:
                repo.mark_failed(submission_id=record.id, error_message=str(exc))
                log_submission_event(
                    "FAILED",
                    submission_id=record.id,
                    vaccine_id=record.ehr_vaccine_id,
                    checkin_id=record.checkin_id,
                    clinic_id=self._clinic.clinic_id,
                    clinic_name=self._clinic.clinic_name,
                    attempt=record.attempt_count,
                    error=str(exc),
                )
            logger.exception("Error processing submission %s", record.id)


def process_clinic_batch(clinic: ClinicConfig, settings: Settings, cair_client: CairSoapClient) -> int:
    repo = CairSubmissionRepository(clinic.db_connection_string, clinic)
    processor = SubmissionProcessor(settings, cair_client, clinic)

    records = repo.get_eligible_submissions(settings.worker_batch_size)
    if not records:
        return 0

    for record in records:
        log_submission_event(
            "QUEUED",
            submission_id=record.id,
            vaccine_id=record.ehr_vaccine_id,
            checkin_id=record.checkin_id,
            clinic_id=clinic.clinic_id,
            clinic_name=clinic.clinic_name,
            attempt=record.attempt_count,
            prior_status=_STATUS_NAME.get(record.submit_status, str(record.submit_status)),
        )

    repo.claim_submissions([r.id for r in records])

    for record in records:
        processor.process_submission(repo, record)

    return len(records)
