"""Coordinator: discovers clinics with work and dispatches to worker pool."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import Settings
from cair_integration.models import ClinicConfig
from cair_integration.outbox.repository import MasterRepository, OutboxRepository
from cair_integration.worker.processor import process_clinic_batch

logger = logging.getLogger(__name__)


class CairCoordinator:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._master = MasterRepository(settings.master_db_connection)
        self._cair = CairSoapClient(
            settings.cair_soap_url,
            settings.cair_soap_username,
            settings.cair_soap_password,
        )

    def run_once(self) -> None:
        clinics = self._get_clinics_with_work()
        if not clinics:
            logger.info("No eligible CAIR work found")
            return

        logger.info("Found %s clinic(s) with eligible work", len(clinics))

        with ThreadPoolExecutor(max_workers=self._settings.worker_pool_size) as executor:
            futures = {
                executor.submit(
                    process_clinic_batch,
                    clinic,
                    self._settings,
                    self._cair,
                ): clinic
                for clinic in clinics
            }

            for future in as_completed(futures):
                clinic = futures[future]
                try:
                    processed = future.result()
                    logger.info(
                        "Clinic %s (%s): processed %s record(s)",
                        clinic.clinic_id,
                        clinic.clinic_name,
                        processed,
                    )
                except Exception:
                    logger.exception(
                        "Clinic %s (%s) batch failed",
                        clinic.clinic_id,
                        clinic.clinic_name,
                    )

    def _get_clinics_with_work(self) -> List[ClinicConfig]:
        active = self._master.get_active_clinics()
        clinics_with_work: List[ClinicConfig] = []

        for clinic in active:
            repo = OutboxRepository(clinic.db_connection_string, clinic)
            if repo.has_eligible_work():
                clinics_with_work.append(clinic)

        return clinics_with_work
