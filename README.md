# CAIR2 HL7 VXU Integration

Python background service that submits vaccination records from **ClaudMD** clinic databases to **CAIR2** (California Immunization Registry) using HL7 v2.5.1 VXU messages over SOAP.

## ClaudMD tables used (no new tables required)

| Table | Role |
|---|---|
| `dbo.ClinicSetup` | Master DB — lists clinics and DB connections |
| `dbo.EHRHeaders` | Visit must have `IsPublish = 1` before CAIR submission |
| `dbo.EHRVaccines` | Vaccine clinical data (lot, dose, date, etc.) |
| `dbo.EHRVaccineThirdPartySubmissions` | Queue + status tracking after submission |

## Flow

```
ClaudMD publishes visit (EHRHeaders.IsPublish = 1)
        +
EMR creates EHRVaccineThirdPartySubmissions row (SubmitStatus = 0)
        ↓
cair_service.py (every 5 min)
        ↓
Read ClinicSetup from master DB → connect to each clinic DB
        ↓
Find submissions where IsPublish=1 and SubmitStatus pending/retry
        ↓
Build HL7 VXU → SOAP submitSingleMessage → CAIR2
        ↓
Update EHRVaccineThirdPartySubmissions (success/fail/retry)
        +
Set EHRVaccines.IsSubmitted = 1 on success
```

## SubmitStatus values

| Value | Constant | Meaning |
|---|---|---|
| 0 | PENDING | Ready for CAIR worker |
| 1 | SUCCESS | CAIR accepted (ACK = AA) |
| 2 | FAILED | Permanent error |
| 3 | RETRY | Temporary failure, will retry |
| 4 | PROCESSING | Worker claimed record |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # set DB + CAIR credentials
python scripts/seed_sithum_cair_test_data.py seed   # create test data (dev DB)
python scripts/seed_sithum_cair_test_data.py verify
python demo_build_vxu.py   # test HL7 output
python cair_service.py     # start worker
```

### Test data seeding (development)

```bash
python scripts/seed_sithum_cair_test_data.py list     # show visits + submissions
python scripts/seed_sithum_cair_test_data.py seed       # create 3 test vaccines + queue rows
python scripts/seed_sithum_cair_test_data.py verify   # confirm worker can pick them up
python scripts/seed_sithum_cair_test_data.py reset    # reset test lots back to PENDING
```

Requires `CLINIC_DB_*` in `.env` (e.g. `ClaudMD_Development_Sithum`). The script inserts into `EHRVaccines` and `EHRVaccineThirdPartySubmissions` only — the same tables the EMR would populate before the CAIR worker runs.

## Environment (.env)

**Development (Sithum clinic DB — direct connection):**

```env
APP_ENV=development
CLINIC_DB_SERVER=10.103.0.211
CLINIC_DB_NAME=ClaudMD_Development_Sithum
CLINIC_DB_USER=testuser
CLINIC_DB_PASSWORD=***
```

**QA (master DB + ClinicSetup lookup):**

```env
APP_ENV=qa
MASTER_DB_SERVER=10.103.0.201
MASTER_DB_NAME=ClaudMD_QA_Setup
MASTER_DB_USER=testuser
MASTER_DB_PASSWORD=***
DEFAULT_ACTIVATION_KEY=20000002
```

When `CLINIC_DB_*` is set, the worker connects directly to that clinic database and skips `ClinicSetup` lookup. Use this for development databases such as `ClaudMD_Development_Sithum` that are not registered in the master setup DB.

```env
SENDING_FACILITY_ID=SF-013259
CAIR_SOAP_URL=https://cdph-interop-stage.cdph.ca.gov/services/client_Service.client_ServiceHttpSoap12Endpoint
```

## Project structure

```
cair_service.py                          # Background worker
cair_integration/
  repository/cair_submission_repository.py # EHRHeaders + EHRVaccines + submissions
  hl7/vxu_builder.py                     # HL7 VXU builder
  cair/soap_client.py                    # CAIR SOAP client
  worker/coordinator.py                  # Multi-clinic dispatcher
  worker/processor.py                    # Per-submission processor
  constants.py                           # SubmitStatus values
```

## Key joins for HL7 data

```
EHRVaccineThirdPartySubmissions
  → EHRVaccines (vaccine data)
  → EHRHeaders (IsPublish = 1)
  → CheckInsHeader (visit date/time)
  → Patients (demographics, phone, email)
  → ServiceCodes (NDC, description)
```

## Documentation

- `CAIR_Project_Guide.pdf` — full technical guide
- `CAIR2_HL7v2.5.1DataExchangeSpecs.pdf` — official CAIR spec
- `cair emails.txt` — endpoints, sample HL7, PID-13 rules
