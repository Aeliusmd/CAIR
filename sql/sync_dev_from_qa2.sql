-- Sync ClaudMD_Development_Sithum from QA_2 (ClaudMD_VCOMC_QA_2) reference
-- CAIR app requirements only. Do not add objects that are not in QA_2.
-- Target: 10.103.0.211 / ClaudMD_Development_Sithum
-- Reference: 10.103.0.201 / ClaudMD_VCOMC_QA_2 (activation key 20000002)

-- =============================================================================
-- 1. EHRVaccineThirdPartySubmissions (missing table in Development)
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'EHRVaccineThirdPartySubmissions'
)
BEGIN
    CREATE TABLE [dbo].[EHRVaccineThirdPartySubmissions] (
        [Id]                    INT             IDENTITY(1,1) NOT NULL,
        [EHRVaccineId]          INT             NOT NULL,
        [SubmitStatus]          INT             NOT NULL,
        [SubmittedDateTime]     DATETIMEOFFSET(7) NULL,
        [LastAttemptDateTime]   DATETIMEOFFSET(7) NULL,
        [AttemptCount]          INT             NOT NULL CONSTRAINT [DF_EHRVaccineThirdPartySubmissions_AttemptCount] DEFAULT ((0)),
        [ExternalReferenceId]   NVARCHAR(100)   NULL,
        [ErrorMessage]          NVARCHAR(MAX)   NULL,
        [RequestPayload]        NVARCHAR(MAX)   NULL,
        [ResponsePayload]       NVARCHAR(MAX)   NULL,
        [CreatedUserId]         INT             NOT NULL,
        [CreatedDateTime]       DATETIMEOFFSET(7) NOT NULL,
        [UpdatedDateTime]       DATETIMEOFFSET(7) NULL,
        [UpdatedUserId]         INT             NULL,
        [RecordStatusId]        INT             NOT NULL,
        [IsDeleted]             BIT             NULL,
        [RowVersion]            ROWVERSION      NULL,
        CONSTRAINT [PK_EHRVaccineThirdPartySubmissions] PRIMARY KEY CLUSTERED ([Id] ASC)
    );

    ALTER TABLE [dbo].[EHRVaccineThirdPartySubmissions] WITH CHECK
    ADD CONSTRAINT [FK_EHRVaccineThirdPartySubmissions_EHRVaccines_EHRVaccineId]
        FOREIGN KEY ([EHRVaccineId]) REFERENCES [dbo].[EHRVaccines] ([Id]);

    CREATE NONCLUSTERED INDEX [IX_EHRVaccineThirdPartySubmissions_SubmitStatus_LastAttempt]
        ON [dbo].[EHRVaccineThirdPartySubmissions] ([SubmitStatus] ASC, [LastAttemptDateTime] ASC)
        INCLUDE ([EHRVaccineId], [AttemptCount]);

    PRINT 'Created table EHRVaccineThirdPartySubmissions';
END
ELSE
    PRINT 'Table EHRVaccineThirdPartySubmissions already exists — skipped';
GO

-- =============================================================================
-- 2. EHRVaccines.IsSubmitted (column exists in QA_2, missing in Development)
-- =============================================================================
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'EHRVaccines' AND COLUMN_NAME = 'IsSubmitted'
)
BEGIN
    ALTER TABLE [dbo].[EHRVaccines] ADD [IsSubmitted] BIT NULL;
    PRINT 'Added column EHRVaccines.IsSubmitted';
END
ELSE
    PRINT 'Column EHRVaccines.IsSubmitted already exists — skipped';
GO
