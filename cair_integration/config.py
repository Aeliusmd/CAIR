"""Application configuration loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from cair_integration.models import ClinicConfig

load_dotenv()


def build_master_db_connection() -> str:
    explicit = os.getenv("MASTER_DB_CONNECTION", "").strip()
    if explicit:
        return explicit
    server = os.getenv("MASTER_DB_SERVER", "")
    database = os.getenv("MASTER_DB_NAME", "")
    user = os.getenv("MASTER_DB_USER", "")
    password = os.getenv("MASTER_DB_PASSWORD", "")
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    if not all([server, database, user, password]):
        return ""
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;"
    )


def build_clinic_db_connection(server: str, database: str, user: str, password: str) -> str:
    driver = os.getenv("MASTER_DB_DRIVER", "ODBC Driver 17 for SQL Server")
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;"
    )


def build_clinic_db_connection_from_env() -> str:
    """Build clinic DB connection from CLINIC_DB_* or CLINIC_DB_CONNECTION."""
    explicit = os.getenv("CLINIC_DB_CONNECTION", "").strip()
    if explicit:
        return explicit
    server = os.getenv("CLINIC_DB_SERVER", "")
    database = os.getenv("CLINIC_DB_NAME", "")
    user = os.getenv("CLINIC_DB_USER", "")
    password = os.getenv("CLINIC_DB_PASSWORD", "")
    if not all([server, database, user, password]):
        return ""
    return build_clinic_db_connection(server, database, user, password)


def build_direct_clinic_config(settings: "Settings") -> Optional[ClinicConfig]:
    """Direct clinic connection for dev DBs not listed in ClinicSetup."""
    conn = settings.clinic_db_connection
    if not conn:
        return None
    return ClinicConfig(
        clinic_id=settings.clinic_id,
        clinic_name=settings.clinic_name,
        db_connection_string=conn,
        sending_application=settings.sending_application,
        sending_facility_id=settings.sending_facility_id,
        provider_org_id=settings.provider_org_id,
        responsible_org_id=settings.provider_org_id,
        receiving_facility=settings.receiving_facility,
        processing_id=settings.processing_id,
    )


@dataclass(frozen=True)
class Settings:
    app_env: str
    master_db_connection: str
    clinic_db_connection: str
    clinic_id: int
    clinic_name: str
    cair_soap_url: str
    cair_soap_username: str
    cair_soap_password: str
    worker_batch_size: int
    worker_pool_size: int
    scheduler_interval_seconds: int
    max_retry_attempts: int
    sending_application: str
    sending_facility_id: str
    provider_org_id: str
    receiving_facility: str
    responsible_org_id: str
    processing_id: str
    default_activation_key: str
    log_dir: str


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "qa").lower(),
        master_db_connection=build_master_db_connection(),
        clinic_db_connection=build_clinic_db_connection_from_env(),
        clinic_id=int(os.getenv("CLINIC_ID", "0")),
        clinic_name=os.getenv("CLINIC_NAME", "Direct Clinic"),
        cair_soap_url=os.getenv("CAIR_SOAP_URL", ""),
        cair_soap_username=os.getenv("CAIR_SOAP_USERNAME", ""),
        cair_soap_password=os.getenv("CAIR_SOAP_PASSWORD", ""),
        worker_batch_size=int(os.getenv("WORKER_BATCH_SIZE", "100")),
        worker_pool_size=int(os.getenv("WORKER_POOL_SIZE", "3")),
        scheduler_interval_seconds=int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "300")),
        max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "5")),
        sending_application=os.getenv("SENDING_APPLICATION", "ClaudMD"),
        sending_facility_id=os.getenv("SENDING_FACILITY_ID", "SF-013259"),
        provider_org_id=os.getenv("PROVIDER_ORG_ID", ""),
        receiving_facility=os.getenv("RECEIVING_FACILITY", "CAIR2"),
        responsible_org_id=os.getenv("PROVIDER_ORG_ID", ""),
        processing_id=os.getenv("PROCESSING_ID", "P"),
        default_activation_key=os.getenv("DEFAULT_ACTIVATION_KEY", ""),
        log_dir=os.getenv("LOG_DIR", "logs"),
    )
