# TMS_ImportExport Mail Ingestion Service

A FastAPI service that runs 24/7 watching a Gmail mailbox via IMAP IDLE. For every
new email it stores the full headers/body/thread content in MS SQL Server
(`TMS_importExport.dbo.EmailStore`) and uploads attachments to an FTP server,
organized as `<FTP_DIRECTORY>/<mail date>/<images|excel|word|pdf|others>/<file>`.
A read-only GraphQL API exposes the stored data for retrieval — there are no
mutations, so the API can never edit or delete what's been ingested.

`mail_reader.py` is the original one-shot CLI script and is left untouched for
ad-hoc manual inspection of the mailbox; it is not used by the service.

## Setup

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. Fill in `.env` (never commit real credentials). See `.env.example` for the
   full list of variables. In addition to the existing `EMAIL_*`/`IMAP_*`/`MAILBOX`
   vars, you need to fill in:
   - `FTP_HOST`, `FTP_USERNAME`, `FTP_PASSWORD` (and optionally `FTP_PORT`,
     `FTP_DIRECTORY`, `FTP_TLS`, `FTP_PASSIVE`)
   - `MSSQL_HOST`, `MSSQL_USERNAME`, `MSSQL_PASSWORD` (database defaults to
     `TMS_importExport`; requires the "ODBC Driver 17 for SQL Server" — or
     whatever driver you set `MSSQL_DRIVER` to — installed on the machine)
3. Run the service:
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   On startup it creates `EmailStore` / `email_sync_state` in `TMS_importExport`
   if they don't exist yet, then connects to the mailbox and starts listening.
   The very first run only ingests mail arriving from that point forward (no
   historical backfill); every run after that resumes from the last processed
   message.

## GraphQL API

Browse to `http://localhost:8000/graphql` for the interactive GraphiQL explorer.

```graphql
query {
  emails(dateFrom: "2026-07-01", dateTo: "2026-07-09", hasAttachments: true, limit: 20) {
    totalCount
    hasMore
    items {
      id
      messageId
      fromAddress
      subject
      emailDate
      attachments { category index filename ftpPath }
    }
  }
}

query {
  email(messageId: "<abc123@mail.example.com>") {
    subject
    bodyText
    attachments { category ftpPath }
  }
}
```

The schema is query-only — no `Mutation` type is defined, so nothing in this
API can create, update, or delete stored mail.

## Attachment storage layout

```
<FTP_DIRECTORY>/<YYYY-MM-DD>/images/<timestamp>_<index>_<name>
<FTP_DIRECTORY>/<YYYY-MM-DD>/excel/...
<FTP_DIRECTORY>/<YYYY-MM-DD>/word/...
<FTP_DIRECTORY>/<YYYY-MM-DD>/pdf/...
<FTP_DIRECTORY>/<YYYY-MM-DD>/others/...
```

The `<timestamp>_<index>_` prefix (seconds precision plus a per-category index)
guarantees two attachments from the same email never collide, even if they
share the exact same original filename.

## Security

Store credentials securely. Avoid committing real credentials to git. Consider
using a secrets manager. `.env` is only ever appended to by tooling in this
repo, never read back out.
