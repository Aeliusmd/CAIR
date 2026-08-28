"""Process one outbox record: build HL7, send to CAIR, update status."""

from __future__ import annotations

import logging

from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import Settings
from cair_integration.hl7.vxu_builder import build_vxu_message
from cair_integration.models import ClinicConfig, OutboxRecord
from cair_integration.outbox.repository import OutboxRepository
from cair_integration.worker.retry import calculate_next_retry

logger = logging.getLogger(__name__)


class RecordProcessor:
    def __init__(self, settings: Settings, cair_client: CairSoapClient):
        self._settings = settings
        self._cair = cair_client

    def process_record(self, repo: OutboxRepository, record: OutboxRecord) -> None:
        try:
            payload = repo.load_vxu_payload(record.vaccination_id)
            hl7_message = build_vxu_message(payload)
            result = self._cair.send_vxu(hl7_message)

            if result.success:
                repo.mark_sent(record.id, hl7_message, result.raw_response)
                logger.info("Outbox %s sent for vaccination %s", record.id, record.vaccination_id)
                return

            if result.temporary_error and record.attempt_count + 1 < self._settings.max_retry_attempts:
                next_retry = calculate_next_retry(record.attempt_count + 1)
                repo.mark_retry(
                    outbox_id=record.id,
                    attempt_count=record.attempt_count + 1,
                    next_retry_at=next_retry,
                    error_message=result.error_details or f"ACK code: {result.ack_code}",
                    hl7_message=hl7_message,
                    ack_response=result.raw_response,
                )
                logger.warning(
                    "Outbox %s scheduled for retry at %s",
                    record.id,
                    next_retry.isoformat(),
                )
                return

            repo.mark_failed(
                outbox_id=record.id,
                error_message=result.error_details or f"ACK code: {result.ack_code}",
                hl7_message=hl7_message,
                ack_response=result.raw_response,
            )
            logger.error("Outbox %s failed permanently", record.id)

        except Exception as exc:
            if record.attempt_count + 1 < self._settings.max_retry_attempts:
                next_retry = calculate_next_retry(record.attempt_count + 1)
                repo.mark_retry(
                    outbox_id=record.id,
                    attempt_count=record.attempt_count + 1,
                    next_retry_at=next_retry,
                    error_message=str(exc),
                )
            else:
                repo.mark_failed(record.id, str(exc))
            logger.exception("Error processing outbox %s", record.id)


def process_clinic_batch(clinic: ClinicConfig, settings: Settings, cair_client: CairSoapClient) -> int:
    """Process one batch (max N records) for a single clinic. Returns count processed."""
    repo = OutboxRepository(clinic.db_connection_string, clinic)
    processor = RecordProcessor(settings, cair_client)

    records = repo.get_eligible_records(settings.worker_batch_size)
    if not records:
        return 0

    record_ids = [r.id for r in records]
    repo.claim_records(record_ids)

    for record in records:
        processor.process_record(repo, record)

    return len(records)
