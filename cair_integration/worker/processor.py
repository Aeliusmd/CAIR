"""Process CAIR submissions from EHRVaccineThirdPartySubmissions."""

from __future__ import annotations

import logging

from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import Settings
from cair_integration.hl7.vxu_builder import build_vxu_message
from cair_integration.models import CairSubmissionRecord, ClinicConfig
from cair_integration.repository.cair_submission_repository import CairSubmissionRepository
from cair_integration.worker.retry import calculate_next_retry

logger = logging.getLogger(__name__)


def _extract_message_control_id(hl7_message: str) -> str:
    for line in hl7_message.replace("\r", "\n").split("\n"):
        if line.startswith("MSH|"):
            fields = line.split("|")
            if len(fields) > 9:
                return fields[9]
    return ""


class SubmissionProcessor:
    def __init__(self, settings: Settings, cair_client: CairSoapClient):
        self._settings = settings
        self._cair = cair_client

    def process_submission(self, repo: CairSubmissionRepository, record: CairSubmissionRecord) -> None:
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
                logger.info(
                    "Submission %s sent for EHRVaccine %s (check-in %s)",
                    record.id,
                    record.ehr_vaccine_id,
                    record.checkin_id,
                )
                return

            error = result.error_details or f"ACK code: {result.ack_code}"
            if result.temporary_error and record.attempt_count + 1 < self._settings.max_retry_attempts:
                repo.mark_retry(
                    submission_id=record.id,
                    attempt_count=record.attempt_count + 1,
                    error_message=error,
                    hl7_message=hl7_message,
                    ack_response=result.raw_response,
                )
                logger.warning("Submission %s scheduled for retry: %s", record.id, error)
                return

            repo.mark_failed(
                submission_id=record.id,
                error_message=error,
                hl7_message=hl7_message,
                ack_response=result.raw_response,
            )
            logger.error("Submission %s failed permanently: %s", record.id, error)

        except Exception as exc:
            if record.attempt_count + 1 < self._settings.max_retry_attempts:
                repo.mark_retry(
                    submission_id=record.id,
                    attempt_count=record.attempt_count + 1,
                    error_message=str(exc),
                )
            else:
                repo.mark_failed(submission_id=record.id, error_message=str(exc))
            logger.exception("Error processing submission %s", record.id)


def process_clinic_batch(clinic: ClinicConfig, settings: Settings, cair_client: CairSoapClient) -> int:
    repo = CairSubmissionRepository(clinic.db_connection_string, clinic)
    processor = SubmissionProcessor(settings, cair_client)

    records = repo.get_eligible_submissions(settings.worker_batch_size)
    if not records:
        return 0

    repo.claim_submissions([r.id for r in records])

    for record in records:
        processor.process_submission(repo, record)

    return len(records)
