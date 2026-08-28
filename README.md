# CAIR2 HL7 VXU Integration

Python service to send vaccination records from your EHR to **CAIR2** (California Immunization Registry) using **HL7 v2.5.1 VXU** messages over SOAP.

Based on:
- `CAIR2_HL7v2.5.1DataExchangeSpecs.pdf` (v3.10)
- `Required Fields mapping with DB 2-11-2021_Modified (2).xlsx`

## Architecture

```
Nurse saves vaccination
        ↓
INSERT vaccination + INSERT cair_outbox (PENDING)  [same transaction]
        ↓
cair_service.py (every 5 min)
        ↓
Coordinator → finds clinics with eligible work
        ↓
Worker pool (3 threads) → one batch per clinic
        ↓
Build HL7 VXU → SOAP to CAIR2 → parse ACK
        ↓
Update outbox: SENT / RETRY / FAILED
```

## Project structure

```
CAIR/
├── cair_service.py              # Background worker (run continuously)
├── demo_build_vxu.py            # Generate sample HL7 without DB
├── cair_integration/
│   ├── config.py                # Environment settings
│   ├── models.py                # Data classes
│   ├── vaccination_service.py   # Outbox creation on vaccination save
│   ├── hl7/vxu_builder.py       # HL7 VXU message builder
│   ├── outbox/repository.py     # Outbox + master DB access
│   ├── cair/soap_client.py      # CAIR SOAP submission
│   ├── cair/ack_parser.py       # ACK response parser
│   └── worker/
│       ├── coordinator.py       # Multi-clinic dispatcher
│       ├── processor.py         # Per-record processing
│       └── retry.py             # Exponential backoff
└── sql/schema.sql               # Outbox table + source view
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and set:

- `MASTER_DB_CONNECTION` — master DB listing all clinics
- `CAIR_SOAP_URL` — CAIR2 SOAP endpoint from onboarding
- `SENDING_FACILITY_ID` — CAIR-assigned site ID (MSH-4, RXA-11.4, MSH-22)

### 3. Run database scripts

On **each clinic database**, run `sql/schema.sql` to create:
- `cair_outbox` table
- `vw_cair_vxu_source` view (adjust table/column names to your schema)

On the **master database**, create `clinic_registry` and register each clinic.

### 4. Wire vaccination save

When a nurse saves a vaccination, create an outbox row in the **same transaction**:

```python
from cair_integration.vaccination_service import save_vaccination_with_outbox

vaccination_id, outbox_id = save_vaccination_with_outbox(
    connection,
    "INSERT INTO vaccination (...) VALUES (...)",
    params,
)
```

### 5. Start the worker

```bash
python cair_service.py
```

### 6. Test HL7 generation (no DB needed)

```bash
python demo_build_vxu.py
```

## Excel field mapping implemented

| HL7 Field | Source | Notes |
|-----------|--------|-------|
| MSH-1/2 | Hardcoded | `\|` and `^~\&` |
| MSH-4/22 | Config | CAIR facility ID |
| MSH-6 | Config | `CAIRLO` |
| MSH-9 | Hardcoded | `VXU^V04^VXU_V04` |
| MSH-10 | GUID | Message control ID |
| MSH-11 | Config | `P` or `T` |
| MSH-15/16 | Hardcoded | `ER` / `AL` |
| PID-3 | `Patient.Acc_no` | MR number |
| ORC-2/3 | `checked_In.checkin_id` | Order numbers |
| RXA-5 | CVX or NDC | Prefers CVX |
| RXA-6/7 | `Charge_rec_detail.qty` | Use `999` if unknown |
| RXA-9.1 | Hardcoded `00` | Given shot (not historical) |
| RXA-15 | Lot number | Required for inventory decrement |
| RXA-20/21 | `CP` / `A` | Complete / Add |
| OBX-5 | VFC eligibility | HL70064 code |

## Items to confirm with your EHR team

1. **CVX vs NDC** — `RXA-5` needs one; add `cvx_code` column or lookup table if NDC is empty
2. **Lot number column** — map to `RXA-15`
3. **VFC eligibility** — confirm correct `OBX-5.1` code per patient
4. **Protection indicator** — `PD1-12`: does EHR store data-sharing consent?
5. **SOAP WSDL** — replace placeholder envelope in `soap_client.py` with CAIR's actual contract
6. **View columns** — adjust `vw_cair_vxu_source` to match your real table names

## Outbox status flow

| Status | Meaning |
|--------|---------|
| PENDING | New, waiting for worker |
| PROCESSING | Worker claimed it |
| SENT | CAIR accepted (ACK = AA) |
| RETRY | Temporary failure, will retry |
| FAILED | Permanent error or max retries exceeded |

## Multi-clinic behavior

- One shared worker pool (default 3 workers)
- Each worker processes **one batch** for **one clinic**, then releases
- Clinics with remaining work are picked up on the next scheduler run
- Retries mix with new PENDING records automatically
