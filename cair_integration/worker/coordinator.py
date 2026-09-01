"""Coordinator: discovers clinics with work and dispatches to worker pool."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import Settings, build_direct_clinic_config
from cair_integration.models import ClinicConfig
from cair_integration.repository.cair_submission_repository import (
    CairSubmissionRepository,
    MasterRepository,
)
from cair_integration.worker.processor import process_clinic_batch

logger = logging.getLogger(__name__)


class CairCoordinator:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._direct_clinic = build_direct_clinic_config(settings)
        self._master = (
            None
            if self._direct_clinic
            else MasterRepository(settings.master_db_connection, settings)
        )
        self._cair = CairSoapClient(
            settings.cair_soap_url,
            settings.cair_soap_username,
            settings.cair_soap_password,
            settings.sending_facility_id,
        )

    def run_once(self) -> None:
        clinics = self._get_clinics_with_work()
        if not clinics:
            logger.info("No eligible CAIR submissions found")
            return

        logger.info("Found %s clinic(s) with pending CAIR submissions", len(clinics))

        with ThreadPoolExecutor(max_workers=self._settings.worker_pool_size) as executor:
            futures = {
                executor.submit(process_clinic_batch, clinic, self._settings, self._cair): clinic
                for clinic in clinics
            }

            for future in as_completed(futures):
                clinic = futures[future]
                try:
                    processed = future.result()
                    logger.info(
                        "Clinic %s (%s): processed %s submission(s)",
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
        if self._direct_clinic:
            repo = CairSubmissionRepository(
                self._direct_clinic.db_connection_string,
                self._direct_clinic,
            )
            if repo.has_eligible_work():
                return [self._direct_clinic]
            return []

        active = self._master.get_active_clinics()
        clinics_with_work: List[ClinicConfig] = []

        for clinic in active:
            repo = CairSubmissionRepository(clinic.db_connection_string, clinic)
            if repo.has_eligible_work():
                clinics_with_work.append(clinic)

        return clinics_with_work
