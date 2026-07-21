import ftplib
import io
import logging
import posixpath

from app.config import Settings

logger = logging.getLogger(__name__)


class FtpClient:
    """Thin wrapper around ftplib for uploading attachments under a date/category path."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._ftp: ftplib.FTP | None = None

    def __enter__(self) -> "FtpClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def connect(self) -> None:
        s = self._settings
        ftp_cls = ftplib.FTP_TLS if s.ftp_tls else ftplib.FTP
        ftp = ftp_cls()
        ftp.connect(host=s.ftp_host, port=s.ftp_port, timeout=30)
        ftp.login(user=s.ftp_username, passwd=s.ftp_password)
        if s.ftp_tls:
            ftp.prot_p()
        ftp.set_pasv(s.ftp_passive)
        self._ftp = ftp

    def close(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.quit()
            except Exception:
                try:
                    self._ftp.close()
                except Exception:
                    pass
            self._ftp = None

    def _ensure_dir(self, remote_dir: str) -> None:
        assert self._ftp is not None
        parts = [p for p in remote_dir.split("/") if p]
        self._ftp.cwd("/")
        for part in parts:
            try:
                self._ftp.cwd(part)
            except ftplib.error_perm:
                self._ftp.mkd(part)
                self._ftp.cwd(part)

    def upload(self, remote_dir: str, filename: str, data: bytes) -> str:
        """Uploads bytes to remote_dir/filename, creating remote_dir if needed. Returns the full remote path."""
        assert self._ftp is not None
        self._ensure_dir(remote_dir)
        self._ftp.storbinary(f"STOR {filename}", io.BytesIO(data))
        return posixpath.join(remote_dir, filename)

    def _cwd_to(self, remote_dir: str) -> None:
        assert self._ftp is not None
        self._ftp.cwd("/")
        for part in (p for p in remote_dir.split("/") if p):
            self._ftp.cwd(part)

    def _is_dir(self, name: str) -> bool:
        assert self._ftp is not None
        current = self._ftp.pwd()
        try:
            self._ftp.cwd(name)
            self._ftp.cwd(current)
            return True
        except ftplib.error_perm:
            return False

    def list_dir(self, remote_dir: str) -> list[dict]:
        """Lists the immediate contents of remote_dir. Each entry: name, is_dir, size, modified."""
        assert self._ftp is not None
        self._cwd_to(remote_dir)

        entries: list[dict] = []
        try:
            for name, facts in self._ftp.mlsd():
                if name in (".", ".."):
                    continue
                size = facts.get("size")
                entries.append(
                    {
                        "name": name,
                        "is_dir": facts.get("type") == "dir",
                        "size": int(size) if size else None,
                        "modified": facts.get("modify"),
                    }
                )
        except Exception:
            logger.info("MLSD unsupported/failed for %s, falling back to NLST", remote_dir)
            for raw_name in self._ftp.nlst():
                name = raw_name.rsplit("/", 1)[-1]
                if name in (".", ".."):
                    continue
                entries.append({"name": name, "is_dir": self._is_dir(name), "size": None, "modified": None})

        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries

    def ensure_dir(self, remote_dir: str) -> None:
        self._ensure_dir(remote_dir)

    def move(self, src_path: str, dst_path: str) -> None:
        """Rename (move) a file on the FTP server."""
        assert self._ftp is not None
        self._ftp.rename(src_path, dst_path)

    def download(self, remote_path: str) -> bytes:
        """Downloads a single file's bytes given its full remote path."""
        assert self._ftp is not None
        parts = [p for p in remote_path.split("/") if p]
        if not parts:
            raise ValueError("remote_path must include a filename")
        filename = parts.pop()
        self._cwd_to("/" + "/".join(parts))

        buf = io.BytesIO()
        self._ftp.retrbinary(f"RETR {filename}", buf.write)
        return buf.getvalue()
