"""Application configuration loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    master_db_connection: str
    cair_soap_url: str
    cair_soap_username: str
    cair_soap_password: str
    worker_batch_size: int
    worker_pool_size: int
    scheduler_interval_seconds: int
    max_retry_attempts: int
    sending_application: str
    sending_facility_id: str
    receiving_facility: str
    responsible_org_id: str
    processing_id: str


def get_settings() -> Settings:
    return Settings(
        master_db_connection=os.getenv("MASTER_DB_CONNECTION", ""),
        cair_soap_url=os.getenv("CAIR_SOAP_URL", ""),
        cair_soap_username=os.getenv("CAIR_SOAP_USERNAME", ""),
        cair_soap_password=os.getenv("CAIR_SOAP_PASSWORD", ""),
        worker_batch_size=int(os.getenv("WORKER_BATCH_SIZE", "100")),
        worker_pool_size=int(os.getenv("WORKER_POOL_SIZE", "3")),
        scheduler_interval_seconds=int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "300")),
        max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "5")),
        sending_application=os.getenv("SENDING_APPLICATION", "MyEMR"),
        sending_facility_id=os.getenv("SENDING_FACILITY_ID", "SF-012218"),
        receiving_facility=os.getenv("RECEIVING_FACILITY", "CAIRLO"),
        responsible_org_id=os.getenv("RESPONSIBLE_ORG_ID", "SF-012218"),
        processing_id=os.getenv("PROCESSING_ID", "P"),
    )
