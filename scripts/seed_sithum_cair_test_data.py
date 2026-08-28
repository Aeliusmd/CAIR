#!/usr/bin/env python3
"""Seed CAIR integration test data in the development clinic database.

Uses CLINIC_DB_* from .env (e.g. ClaudMD_Development_Sithum). Inserts the same
records the EMR would create before the CAIR worker runs:
  - EHRVaccines (vaccine clinical data on a published visit)
  - EHRVaccineThirdPartySubmissions (SubmitStatus = 0 PENDING)

Commands:
  list    Show published visits, vaccines, and pending submissions
  seed    Create/enrich vaccines and queue CAIR submissions
  verify  Confirm records are eligible for the CAIR worker
  reset   Reset test submissions back to PENDING (for re-testing)

Examples:
  python scripts/seed_sithum_cair_test_data.py list
  python scripts/seed_sithum_cair_test_data.py seed
  python scripts/seed_sithum_cair_test_data.py seed --count 2 --dry-run
  python scripts/seed_sithum_cair_test_data.py verify
  python scripts/seed_sithum_cair_test_data.py reset
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyodbc
from dotenv import load_dotenv

from cair_integration.config import build_clinic_db_connection_from_env, build_direct_clinic_config, get_settings
from cair_integration.constants import PENDING, SUCCESS, FAILED, PROCESSING
from cair_integration.repository.cair_submission_repository import CairSubmissionRepository

load_dotenv()

CREATED_USER_ID = 10068
RECORD_STATUS_ID = 1
TEST_LOT_PREFIX = "LOT-CAIR-TEST-"

DEFAULT_VACCINE = {
    "lot_number": f"{TEST_LOT_PREFIX}001",
    "vaccine_date": date(2026, 8, 16),
    "vaccine_time": time(10, 30),
    "expiration_date": date(2027, 6, 30),
    "manufacturer": "Merck Sharp & Dohme",
    "dosage": "0.5",
    "route": "Intramuscular",
    "body_site": "Left Deltoid",
    "vaccine_name": "CAIR Test Vaccine",
}


@dataclass(frozen=True)
class PublishedVisit:
    checkin_id: int
    patient_id: int
    first_name: str
    last_name: str
    email: str
    cell_phone: str
    home_phone: str
    vaccine_count: int

    @property
    def has_pid13_contact(self) -> bool:
        return bool(self.email or self.cell_phone or self.home_phone)

    @property
    def contact_summary(self) -> str:
        parts = []
        if self.email:
            parts.append("email")
        if self.cell_phone or self.home_phone:
            parts.append("phone")
        return "+".join(parts) or "none"


@dataclass(frozen=True)
class VaccineServiceCode:
    service_code_id: int
    code: str
    description: str
    ndc_number: str


@dataclass
class SeedResult:
    vaccine_id: int
    submission_id: int
    checkin_id: int
    action: str  # created | queued | skipped


class CairTestDataSeeder:
    def __init__(self, conn: pyodbc.Connection, *, dry_run: bool = False):
        self._conn = conn
        self._cur = conn.cursor()
        self._dry_run = dry_run

    def discover_published_visits(self, limit: int = 20) -> list[PublishedVisit]:
        self._cur.execute(
            f"""
            SELECT TOP ({limit})
                h.CheckinId,
                ci.PatientId,
                p.FirstName,
                p.LastName,
                COALESCE(p.Email, '') AS Email,
                COALESCE(p.CellPhone, '') AS CellPhone,
                COALESCE(p.HomePhone, '') AS HomePhone,
                (
                    SELECT COUNT(*)
                    FROM dbo.EHRVaccines v
                    WHERE v.CheckInId = h.CheckinId AND v.IsDeleted = 0
                ) AS VaccineCount
            FROM dbo.EHRHeaders h
            INNER JOIN dbo.CheckInsHeader ci
                ON ci.Id = h.CheckinId AND ci.IsDeleted = 0
            INNER JOIN dbo.Patients p
                ON p.Id = ci.PatientId AND p.IsDeleted = 0
            WHERE h.IsPublish = 1
              AND h.IsDeleted = 0
              AND (
                    NULLIF(LTRIM(RTRIM(p.Email)), '') IS NOT NULL
                 OR NULLIF(LTRIM(RTRIM(p.CellPhone)), '') IS NOT NULL
                 OR NULLIF(LTRIM(RTRIM(p.HomePhone)), '') IS NOT NULL
              )
            ORDER BY
                CASE
                    WHEN NULLIF(LTRIM(RTRIM(p.Email)), '') IS NOT NULL
                     AND (
                            NULLIF(LTRIM(RTRIM(p.CellPhone)), '') IS NOT NULL
                         OR NULLIF(LTRIM(RTRIM(p.HomePhone)), '') IS NOT NULL
                         )
                    THEN 0
                    ELSE 1
                END,
                h.CheckinId DESC
            """
        )
        return [
            PublishedVisit(
                checkin_id=row.CheckinId,
                patient_id=row.PatientId,
                first_name=row.FirstName or "",
                last_name=row.LastName or "",
                email=row.Email,
                cell_phone=row.CellPhone,
                home_phone=row.HomePhone,
                vaccine_count=row.VaccineCount,
            )
            for row in self._cur.fetchall()
        ]

    def find_vaccine_service_codes(self, limit: int = 5) -> list[VaccineServiceCode]:
        self._cur.execute(
            f"""
            SELECT TOP ({limit})
                sc.Id,
                sc.Code,
                sc.Description,
                sc.NDCNumber
            FROM dbo.ServiceCodes sc
            WHERE NULLIF(LTRIM(RTRIM(sc.NDCNumber)), '') IS NOT NULL
              AND (sc.IsDeleted = 0 OR sc.IsDeleted IS NULL)
              AND (
                    sc.Description LIKE '%Vaccine%'
                 OR sc.Description LIKE '%Vacc %'
                 OR sc.Description LIKE '%Tdap%'
                 OR sc.Description LIKE '%Hep%'
              )
            ORDER BY
                CASE WHEN sc.Description LIKE '%Hep%' THEN 0 ELSE 1 END,
                sc.Id
            """
        )
        return [
            VaccineServiceCode(
                service_code_id=row.Id,
                code=row.Code or "",
                description=row.Description or "",
                ndc_number=row.NDCNumber or "",
            )
            for row in self._cur.fetchall()
        ]

    def list_pending_submissions(self) -> list[dict]:
        self._cur.execute(
            """
            SELECT
                s.Id AS submission_id,
                s.EHRVaccineId AS vaccine_id,
                s.SubmitStatus,
                v.CheckInId,
                v.LotNumber,
                p.FirstName,
                p.LastName,
                p.Email,
                p.CellPhone,
                sc.NDCNumber,
                h.IsPublish
            FROM dbo.EHRVaccineThirdPartySubmissions s
            INNER JOIN dbo.EHRVaccines v
                ON v.Id = s.EHRVaccineId AND v.IsDeleted = 0
            INNER JOIN dbo.EHRHeaders h
                ON h.CheckinId = v.CheckInId AND h.IsDeleted = 0
            INNER JOIN dbo.CheckInsHeader ci
                ON ci.Id = v.CheckInId AND ci.IsDeleted = 0
            INNER JOIN dbo.Patients p
                ON p.Id = ci.PatientId AND p.IsDeleted = 0
            LEFT JOIN dbo.ServiceCodes sc
                ON sc.Id = v.ServiceCodeId
            WHERE s.IsDeleted = 0
            ORDER BY s.Id
            """
        )
        cols = [d[0] for d in self._cur.description]
        return [dict(zip(cols, row)) for row in self._cur.fetchall()]

    def _submission_exists(self, vaccine_id: int) -> bool:
        self._cur.execute(
            """
            SELECT 1
            FROM dbo.EHRVaccineThirdPartySubmissions
            WHERE EHRVaccineId = ? AND IsDeleted = 0
            """,
            vaccine_id,
        )
        return self._cur.fetchone() is not None

    def _find_reusable_vaccine(self, checkin_id: int) -> Optional[int]:
        self._cur.execute(
            """
            SELECT TOP 1 v.Id
            FROM dbo.EHRVaccines v
            LEFT JOIN dbo.EHRVaccineThirdPartySubmissions s
                ON s.EHRVaccineId = v.Id AND s.IsDeleted = 0
            WHERE v.CheckInId = ?
              AND v.IsDeleted = 0
              AND s.Id IS NULL
            ORDER BY v.Id DESC
            """,
            checkin_id,
        )
        row = self._cur.fetchone()
        return int(row[0]) if row else None

    def enrich_vaccine(
        self,
        vaccine_id: int,
        *,
        service_code: VaccineServiceCode,
        lot_number: str,
    ) -> None:
        if self._dry_run:
            return
        self._cur.execute(
            """
            UPDATE dbo.EHRVaccines
            SET ServiceCodeId = COALESCE(ServiceCodeId, ?),
                VaccineName = COALESCE(NULLIF(VaccineName, ''), ?),
                LotNumber = COALESCE(NULLIF(LotNumber, ''), ?),
                VaccineDate = COALESCE(VaccineDate, ?),
                VaccineTime = COALESCE(VaccineTime, ?),
                VaccineExpirationDate = COALESCE(VaccineExpirationDate, ?),
                Manufacturer = COALESCE(NULLIF(Manufacturer, ''), ?),
                Dosage = COALESCE(NULLIF(Dosage, ''), ?),
                Route = COALESCE(NULLIF(Route, ''), ?),
                BodySite = COALESCE(NULLIF(BodySite, ''), ?),
                IsVaccine = COALESCE(IsVaccine, 1),
                IsSubmitted = COALESCE(IsSubmitted, 0),
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id = ? AND IsDeleted = 0
            """,
            service_code.service_code_id,
            service_code.description or DEFAULT_VACCINE["vaccine_name"],
            lot_number,
            DEFAULT_VACCINE["vaccine_date"],
            DEFAULT_VACCINE["vaccine_time"],
            DEFAULT_VACCINE["expiration_date"],
            DEFAULT_VACCINE["manufacturer"],
            DEFAULT_VACCINE["dosage"],
            DEFAULT_VACCINE["route"],
            DEFAULT_VACCINE["body_site"],
            vaccine_id,
        )

    def insert_vaccine(self, checkin_id: int, service_code: VaccineServiceCode, lot_number: str) -> int:
        if self._dry_run:
            return -1
        self._cur.execute(
            """
            INSERT INTO dbo.EHRVaccines (
                CheckInId, ServiceCodeId, VaccineName, LotNumber, VaccineExpirationDate,
                Dosage, BodySite, VaccineTime, Manufacturer, Route, VaccineDate,
                IsVaccine, IsSubmitted, CreatedUserId, CreatedDateTime, RecordStatusId, IsDeleted
            )
            OUTPUT INSERTED.Id
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                1, 0, ?, SYSDATETIMEOFFSET(), ?, 0
            )
            """,
            checkin_id,
            service_code.service_code_id,
            service_code.description or DEFAULT_VACCINE["vaccine_name"],
            lot_number,
            DEFAULT_VACCINE["expiration_date"],
            DEFAULT_VACCINE["dosage"],
            DEFAULT_VACCINE["body_site"],
            DEFAULT_VACCINE["vaccine_time"],
            DEFAULT_VACCINE["manufacturer"],
            DEFAULT_VACCINE["route"],
            DEFAULT_VACCINE["vaccine_date"],
            CREATED_USER_ID,
            RECORD_STATUS_ID,
        )
        return int(self._cur.fetchone()[0])

    def insert_submission(self, vaccine_id: int) -> int:
        if self._dry_run:
            return -1
        self._cur.execute(
            """
            INSERT INTO dbo.EHRVaccineThirdPartySubmissions (
                EHRVaccineId, SubmitStatus, AttemptCount,
                CreatedUserId, CreatedDateTime, RecordStatusId, IsDeleted
            )
            OUTPUT INSERTED.Id
            VALUES (?, ?, 0, ?, SYSDATETIMEOFFSET(), ?, 0)
            """,
            vaccine_id,
            PENDING,
            CREATED_USER_ID,
            RECORD_STATUS_ID,
        )
        return int(self._cur.fetchone()[0])

    def seed(self, count: int = 3) -> list[SeedResult]:
        visits = self.discover_published_visits(limit=max(count * 3, 10))
        service_codes = self.find_vaccine_service_codes(limit=5)
        if not visits:
            raise RuntimeError("No published visits with patient phone/email found")
        if not service_codes:
            raise RuntimeError("No vaccine ServiceCodes with NDC found")

        results: list[SeedResult] = []
        used_checkins: set[int] = set()

        for index in range(count):
            visit = next((v for v in visits if v.checkin_id not in used_checkins), None)
            if visit is None:
                break

            service_code = service_codes[index % len(service_codes)]
            lot_number = f"{TEST_LOT_PREFIX}{index + 1:03d}"
            used_checkins.add(visit.checkin_id)

            vaccine_id = self._find_reusable_vaccine(visit.checkin_id)
            if vaccine_id is not None:
                self.enrich_vaccine(vaccine_id, service_code=service_code, lot_number=lot_number)
                action_prefix = "reuse"
            else:
                vaccine_id = self.insert_vaccine(visit.checkin_id, service_code, lot_number)
                action_prefix = "create"

            if self._submission_exists(vaccine_id):
                results.append(
                    SeedResult(
                        vaccine_id=vaccine_id,
                        submission_id=-1,
                        checkin_id=visit.checkin_id,
                        action="skipped (submission exists)",
                    )
                )
                continue

            submission_id = self.insert_submission(vaccine_id)
            results.append(
                SeedResult(
                    vaccine_id=vaccine_id,
                    submission_id=submission_id,
                    checkin_id=visit.checkin_id,
                    action=f"{action_prefix}+queued",
                )
            )

        if not self._dry_run:
            self._conn.commit()
        return results

    def reset_test_submissions(self) -> int:
        if self._dry_run:
            self._cur.execute(
                """
                SELECT COUNT(*)
                FROM dbo.EHRVaccineThirdPartySubmissions s
                INNER JOIN dbo.EHRVaccines v ON v.Id = s.EHRVaccineId
                WHERE s.IsDeleted = 0
                  AND v.LotNumber LIKE ?
                  AND s.SubmitStatus IN (?, ?, ?)
                """,
                f"{TEST_LOT_PREFIX}%",
                SUCCESS,
                FAILED,
                PROCESSING,
            )
            return int(self._cur.fetchone()[0])

        self._cur.execute(
            """
            UPDATE s
            SET s.SubmitStatus = ?,
                s.AttemptCount = 0,
                s.SubmittedDateTime = NULL,
                s.LastAttemptDateTime = NULL,
                s.ExternalReferenceId = NULL,
                s.ErrorMessage = NULL,
                s.RequestPayload = NULL,
                s.ResponsePayload = NULL,
                s.UpdatedDateTime = SYSDATETIMEOFFSET()
            FROM dbo.EHRVaccineThirdPartySubmissions s
            INNER JOIN dbo.EHRVaccines v ON v.Id = s.EHRVaccineId
            WHERE s.IsDeleted = 0
              AND v.LotNumber LIKE ?
              AND s.SubmitStatus IN (?, ?, ?)
            """,
            PENDING,
            f"{TEST_LOT_PREFIX}%",
            SUCCESS,
            FAILED,
            PROCESSING,
        )
        updated = self._cur.rowcount
        self._cur.execute(
            """
            UPDATE v
            SET v.IsSubmitted = 0,
                v.UpdatedDateTime = SYSDATETIMEOFFSET()
            FROM dbo.EHRVaccines v
            WHERE v.IsDeleted = 0
              AND v.LotNumber LIKE ?
            """,
            f"{TEST_LOT_PREFIX}%",
        )
        self._conn.commit()
        return updated


def connect() -> pyodbc.Connection:
    conn_str = build_clinic_db_connection_from_env()
    if not conn_str:
        raise RuntimeError("CLINIC_DB_* not configured in .env")
    return pyodbc.connect(conn_str, autocommit=False)


def cmd_list(seeder: CairTestDataSeeder) -> int:
    print("Published visits (phone/email, IsPublish=1):")
    for visit in seeder.discover_published_visits():
        print(
            f"  checkin {visit.checkin_id}: {visit.first_name} {visit.last_name} "
            f"[{visit.contact_summary}], vaccines={visit.vaccine_count}"
        )

    print("\nVaccine service codes with NDC:")
    for code in seeder.find_vaccine_service_codes():
        print(f"  {code.service_code_id}: {code.description} (NDC {code.ndc_number})")

    print("\nCAIR submissions:")
    rows = seeder.list_pending_submissions()
    if not rows:
        print("  (none)")
    for row in rows:
        print(
            f"  submission {row['submission_id']}: vaccine {row['vaccine_id']}, "
            f"checkin {row['CheckInId']}, status={row['SubmitStatus']}, "
            f"publish={row['IsPublish']}, patient={row['FirstName']} {row['LastName']}, "
            f"ndc={row['NDCNumber'] or '-'}, lot={row['LotNumber'] or '-'}"
        )
    return 0


def cmd_seed(seeder: CairTestDataSeeder, count: int) -> int:
    label = "DRY RUN — " if seeder._dry_run else ""
    print(f"{label}Seeding up to {count} CAIR test record(s)...")
    results = seeder.seed(count=count)
    for result in results:
        print(
            f"  checkin {result.checkin_id}: vaccine {result.vaccine_id}, "
            f"submission {result.submission_id}, action={result.action}"
        )
    if seeder._dry_run:
        print("\nNo changes written (dry run).")
    return 0


def cmd_verify() -> int:
    settings = get_settings()
    clinic = build_direct_clinic_config(settings)
    if not clinic:
        print("CLINIC_DB_* not configured in .env")
        return 1

    repo = CairSubmissionRepository(clinic.db_connection_string, clinic)
    pending = repo.get_eligible_submissions(20)
    print(f"Eligible for CAIR worker: {len(pending)} submission(s)")
    for row in pending:
        payload = repo.load_vxu_payload(row.id)
        patient = payload.patient
        vacc = payload.vaccination
        print(
            f"  submission {row.id}: checkin {row.checkin_id}, "
            f"patient={patient.first_name} {patient.last_name}, "
            f"email={'yes' if patient.email else 'no'}, "
            f"phone={'yes' if (patient.phone or patient.cell_phone) else 'no'}, "
            f"ndc={vacc.ndc_number or '-'}, lot={vacc.lot_number or '-'}"
        )

    if not pending:
        print("Run: python scripts/seed_sithum_cair_test_data.py seed")
        return 1
    print("\nReady. Run: python run_dry_once.py")
    return 0


def cmd_reset(seeder: CairTestDataSeeder) -> int:
    label = "DRY RUN — would reset" if seeder._dry_run else "Reset"
    count = seeder.reset_test_submissions()
    print(f"{label} {count} test submission(s) back to PENDING")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed CAIR test data in the development clinic database (CLINIC_DB_* in .env)."
    )
    parser.add_argument(
        "command",
        choices=["list", "seed", "verify", "reset"],
        help="list=show current state, seed=create test data, verify=check worker eligibility, reset=re-test",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of test vaccines/submissions to create (seed command only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing to the database",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    conn = connect()
    seeder = CairTestDataSeeder(conn, dry_run=args.dry_run)

    try:
        if args.command == "list":
            return cmd_list(seeder)
        if args.command == "seed":
            return cmd_seed(seeder, args.count)
        if args.command == "verify":
            conn.close()
            return cmd_verify()
        if args.command == "reset":
            return cmd_reset(seeder)
        return 1
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if not conn.closed:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
