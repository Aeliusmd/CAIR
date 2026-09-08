"""Reset and resend a single CAIR submission by ID."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyodbc
from dotenv import load_dotenv

from cair_integration.cair.soap_client import CairSoapClient
from cair_integration.config import build_direct_clinic_config, get_settings
from cair_integration.constants import PENDING, PROCESSING
from cair_integration.repository.cair_submission_repository import CairSubmissionRepository
from cair_integration.worker.processor import SubmissionProcessor

load_dotenv()


def main() -> int:
    submission_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    settings = get_settings()
    clinic = build_direct_clinic_config(settings)
    if not clinic:
        print("Clinic DB not configured in .env")
        return 1

    if not settings.cair_soap_username or not settings.cair_soap_password:
        print("CAIR_SOAP_USERNAME and CAIR_SOAP_PASSWORD must be set in .env")
        return 1

    repo = CairSubmissionRepository(clinic.db_connection_string, clinic)

    with repo._connect() as conn:
        row = conn.execute(
            """
            SELECT Id, SubmitStatus, AttemptCount, EHRVaccineId
            FROM dbo.EHRVaccineThirdPartySubmissions
            WHERE Id = ? AND IsDeleted = 0
            """,
            submission_id,
        ).fetchone()
        if not row:
            print(f"Submission {submission_id} not found")
            return 1

        print(
            f"Before: submission {row.Id}, status={row.SubmitStatus}, "
            f"attempts={row.AttemptCount}, vaccine={row.EHRVaccineId}"
        )

        conn.execute(
            """
            UPDATE dbo.EHRVaccineThirdPartySubmissions
            SET SubmitStatus = ?,
                AttemptCount = 0,
                ErrorMessage = NULL,
                ResponsePayload = NULL,
                SubmittedDateTime = NULL,
                LastAttemptDateTime = NULL,
                ExternalReferenceId = NULL,
                UpdatedDateTime = SYSDATETIMEOFFSET()
            WHERE Id = ?
            """,
            PENDING,
            submission_id,
        )
        conn.commit()
        print(f"Reset submission {submission_id} to PENDING")

    records = repo.get_eligible_submissions(100)
    record = next((r for r in records if r.id == submission_id), None)
    if not record:
        print(f"Submission {submission_id} is not eligible (check IsPublish=1 and joins)")
        return 1

    repo.claim_submissions([submission_id])
    client = CairSoapClient(
        settings.cair_soap_url,
        settings.cair_soap_username,
        settings.cair_soap_password,
        settings.sending_facility_id,
    )
    processor = SubmissionProcessor(settings, client, clinic)
    processor.process_submission(repo, record)

    with repo._connect() as conn:
        after = conn.execute(
            """
            SELECT SubmitStatus, AttemptCount,
                   LEFT(ErrorMessage, 500) AS ErrorMessage,
                   LEFT(ResponsePayload, 1500) AS ResponsePayload
            FROM dbo.EHRVaccineThirdPartySubmissions
            WHERE Id = ?
            """,
            submission_id,
        ).fetchone()

    print(f"\nAfter: status={after.SubmitStatus}, attempts={after.AttemptCount}")
    print(f"Error: {after.ErrorMessage or '(none)'}")
    print(f"\nCAIR response:\n{after.ResponsePayload or '(empty)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
