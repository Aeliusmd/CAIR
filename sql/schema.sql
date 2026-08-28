-- Per-clinic database: run this on each clinic database
-- Creates outbox table for CAIR VXU submissions

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'cair_outbox')
BEGIN
    CREATE TABLE cair_outbox (
        id                  BIGINT IDENTITY(1,1) PRIMARY KEY,
        vaccination_id      BIGINT NOT NULL,
        status              VARCHAR(20) NOT NULL DEFAULT 'PENDING',
        attempt_count       INT NOT NULL DEFAULT 0,
        next_retry_at       DATETIME2 NULL,
        hl7_message         NVARCHAR(MAX) NULL,
        ack_response        NVARCHAR(MAX) NULL,
        error_message       NVARCHAR(500) NULL,
        created_at          DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at          DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_cair_outbox_status CHECK (
            status IN ('PENDING', 'PROCESSING', 'SENT', 'RETRY', 'FAILED')
        )
    );

    CREATE INDEX IX_cair_outbox_eligible
        ON cair_outbox (status, next_retry_at)
        INCLUDE (vaccination_id, attempt_count);

    CREATE INDEX IX_cair_outbox_vaccination
        ON cair_outbox (vaccination_id);
END
GO

-- Master database: clinic registry
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'clinic_registry')
BEGIN
    CREATE TABLE clinic_registry (
        clinic_id               INT IDENTITY(1,1) PRIMARY KEY,
        clinic_name             NVARCHAR(200) NOT NULL,
        db_connection_string    NVARCHAR(500) NOT NULL,
        sending_application     NVARCHAR(100) NOT NULL DEFAULT 'MyEMR',
        sending_facility_id     NVARCHAR(50) NOT NULL,
        responsible_org_id      NVARCHAR(50) NULL,
        receiving_facility      NVARCHAR(50) NOT NULL DEFAULT 'CAIR2',
        processing_id           CHAR(1) NOT NULL DEFAULT 'P',
        is_active               BIT NOT NULL DEFAULT 1,
        created_at              DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
GO

-- View to load vaccination + patient data for HL7 builder
-- Adjust table/column names to match your EHR schema
CREATE OR ALTER VIEW vw_cair_vxu_source AS
SELECT
    v.id                          AS vaccination_id,
    ci.checkin_id                 AS checkin_id,
    ci.checkin_datetime           AS administration_datetime,
    p.acc_no                      AS patient_acc_no,
    p.last_name                   AS patient_last_name,
    p.first_name                  AS patient_first_name,
    p.middle_name                 AS patient_middle_name,
    p.date_of_birth               AS patient_dob,
    p.sex                         AS patient_sex,
    p.address1                    AS patient_address,
    p.city                        AS patient_city,
    p.state                       AS patient_state,
    p.zip                         AS patient_zip,
    p.phone                       AS patient_phone,
    p.cell_phone                  AS patient_cell_phone,
    p.email                       AS patient_email,
    crd.ndc_number                AS ndc_number,
    crd.qty                       AS dose_amount,
    crd.qty_unit                  AS dose_unit,
    crd.lot_number                AS lot_number,
    crd.expiration_date           AS expiration_date,
    crd.cvx_code                  AS cvx_code,
    crd.manufacturer_code         AS manufacturer_code,
    crd.manufacturer_name         AS manufacturer_name
FROM vaccination v
INNER JOIN checked_in ci ON ci.id = v.checkin_id
INNER JOIN patient p ON p.id = v.patient_id
LEFT JOIN charge_rec_detail crd ON crd.id = v.charge_detail_id;
GO
