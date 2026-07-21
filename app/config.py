from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # IMAP source mailbox
    email_user: str = ""
    email_pass: str = ""
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    mailbox: str = "INBOX"

    # FTP attachment storage
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_username: str = ""
    ftp_password: str = ""
    ftp_directory: str = "/"
    ftp_poll_interval: int = 30
    ftp_tls: bool = False
    ftp_passive: bool = True

    # MS SQL Server
    mssql_host: str = ""
    mssql_port: int = 1433
    mssql_database: str = "TMS_importExport"
    mssql_username: str = ""
    mssql_password: str = ""
    mssql_driver: str = "ODBC Driver 17 for SQL Server"

    # OCR endpoint for matched emails
    ocr_endpoint_url: str = ""

    # Service tuning
    idle_renew_seconds: int = 1200
    imap_socket_timeout_seconds: int = 60
    imap_reconnect_base_seconds: int = 5
    imap_reconnect_max_seconds: int = 300
    graphql_max_page_size: int = 200
    log_level: str = "INFO"

    @property
    def mssql_connection_string(self) -> str:
        driver = self.mssql_driver.replace(" ", "+")
        return (
            f"mssql+pyodbc://{self.mssql_username}:{self.mssql_password}"
            f"@{self.mssql_host}:{self.mssql_port}/{self.mssql_database}"
            f"?driver={driver}&TrustServerCertificate=yes"
        )


settings = Settings()
