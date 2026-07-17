-- ============================================================================
-- Script: sp_InsertEmailStore
-- Purpose: Insert a new row into the EmailStore table, replacing the former
--          ORM-based INSERT (session.add / session.commit).
--
-- Behavior:
--   • Checks for duplicate message_id before inserting.
--   • Uses TRY / CATCH to handle unique-constraint race conditions.
--   • Looks up JOB_ORDERSNO and WoExecutionDocSno by matching subject/body
--     against JOB_ORDER.PurchaseOrderNo and WoExecutionDoc.DocumentNo.
--   • Returns a two-column result set (result, reason) so the caller can
--     distinguish success from duplicate without relying on exceptions.
--
-- Result set:
--   result  BIGINT  – SCOPE_IDENTITY() on success, 0 on duplicate.
--   reason  VARCHAR – 'OK' on success, 'DUPLICATE' on duplicate.
--
-- Errors other than duplicate key violations are re-raised via RAISERROR
-- so they become Python exceptions on the client side.
-- ============================================================================

CREATE OR ALTER PROCEDURE [dbo].[sp_InsertEmailStore]
    @message_id             NVARCHAR(400),
    @message_id_raw         NVARCHAR(MAX),
    @from_address           NVARCHAR(998)  = NULL,
    @to_address             NVARCHAR(MAX)  = NULL,
    @cc_address             NVARCHAR(MAX)  = NULL,
    @bcc_address            NVARCHAR(MAX)  = NULL,
    @reply_to               NVARCHAR(998)  = NULL,
    @in_reply_to            NVARCHAR(998)  = NULL,
    @references_header      NVARCHAR(MAX)  = NULL,
    @subject                NVARCHAR(998)  = NULL,
    @date_raw               NVARCHAR(255)  = NULL,
    @email_date_utc         DATETIME2(3),
    @mail_date              DATE,
    @body_text              NVARCHAR(MAX)  = NULL,
    @body_html              NVARCHAR(MAX)  = NULL,
    @raw_headers            NVARCHAR(MAX)  = NULL,
    @attachments            NVARCHAR(MAX)  = NULL,
    @has_attachments        BIT            = 0,
    @attachment_count       INT            = 0,
    @company_name           NVARCHAR(255)  = NULL,
    @company_domain_source  NVARCHAR(255)  = NULL,
    @company_signature_source NVARCHAR(255) = NULL,
    @ocr_markdown_paths     NVARCHAR(MAX)  = NULL,
    @mailbox                NVARCHAR(255)  = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- ------------------------------------------------------------------
    -- Early exit if the message_id is already present (idempotency guard).
    -- ------------------------------------------------------------------
    IF EXISTS (SELECT 1 FROM dbo.EmailStore WHERE message_id = @message_id)
    BEGIN
        SELECT
            CAST(0 AS BIGINT) AS result,
            CAST('DUPLICATE' AS VARCHAR(20)) AS reason;
        RETURN;
    END

    BEGIN TRY
        DECLARE @JOB_ORDERSNO INT = NULL
        DECLARE @WO_EX_DOCSNO INT = NULL

        SELECT @WO_EX_DOCSNO = TOP 1 WoExecutionDocSno
        FROM WoExecutionDoc
        WHERE (@subject   IS NOT NULL AND @subject   LIKE '%' + DocumentNo + '%')
           OR (@body_text IS NOT NULL AND @body_text LIKE '%' + DocumentNo + '%')

        SELECT @JOB_ORDERSNO = TOP 1 JobOrderSno
        FROM JOB_ORDER
        WHERE (@subject   IS NOT NULL AND @subject   LIKE '%' + PurchaseOrderNo + '%')
           OR (@body_text IS NOT NULL AND @body_text LIKE '%' + PurchaseOrderNo + '%')

        INSERT INTO dbo.EmailStore (
            message_id,
            message_id_raw,
            from_address,
            to_address,
            cc_address,
            bcc_address,
            reply_to,
            in_reply_to,
            references_header,
            subject,
            date_raw,
            email_date_utc,
            mail_date,
            body_text,
            body_html,
            raw_headers,
            attachments,
            has_attachments,
            attachment_count,
            company_name,
            company_domain_source,
            company_signature_source,
            ocr_markdown_paths,
            mailbox,
            created_at,
            JOB_ORDERSNO,
            WoExecutionDocSno
        ) VALUES (
            @message_id,
            @message_id_raw,
            @from_address,
            @to_address,
            @cc_address,
            @bcc_address,
            @reply_to,
            @in_reply_to,
            @references_header,
            @subject,
            @date_raw,
            @email_date_utc,
            @mail_date,
            @body_text,
            @body_html,
            @raw_headers,
            @attachments,
            @has_attachments,
            @attachment_count,
            @company_name,
            @company_domain_source,
            @company_signature_source,
            @ocr_markdown_paths,
            @mailbox,
            GETUTCDATE(),
            @JOB_ORDERSNO,
            @WO_EX_DOCSNO
        );

        SELECT
            SCOPE_IDENTITY() AS result,
            CAST('OK' AS VARCHAR(20)) AS reason;
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() IN (2627, 2601)
        BEGIN
            SELECT
                CAST(0 AS BIGINT) AS result,
                CAST('DUPLICATE' AS VARCHAR(20)) AS reason;
        END
        ELSE
        BEGIN
            DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
            RAISERROR(@ErrorMessage, 16, 1);
        END
    END CATCH
END;
GO
