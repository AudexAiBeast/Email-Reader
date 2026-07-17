import logging
import re
from email.utils import parsedate_to_datetime
from typing import Optional

logger = logging.getLogger(__name__)

FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "outlook.com",
    "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "protonmail.com", "proton.me", "zoho.com", "yandex.com",
    "mail.com", "inbox.com", "fastmail.com", "gmx.com", "rediffmail.com",
    "rediff.co.in", "rocketmail.com", "ymail.com", "att.net", "verizon.net",
    "comcast.net", "sbcglobal.net", "bellsouth.net", "earthlink.net",
    "tutanota.com", "t-online.de", "web.de", "gmx.net", "libero.it",
    "tin.it", "alice.it", "virgilio.it", "163.com", "126.com", "qq.com",
    "sina.com", "sohu.com", "naver.com", "daum.net", "hanmail.net",
    "btinternet.com", "ntlworld.com", "sky.com", "talktalk.net",
    "virginmedia.com", "orange.fr", "free.fr", "wanadoo.fr", "club-internet.fr",
    "laposte.net", "telefonica.net", "ono.com", "terra.es", "uol.com.br",
    "bol.com.br", "ig.com.br", "r7.com", "bigpond.com", "optusnet.com.au",
    "xtra.co.nz", "paradise.net.nz", "mail.ru", "bk.ru", "inbox.ru", "list.ru",
})

SIGNATURE_DELIMITERS = re.compile(
    r'^\s*(--\s*|__+\s*|\*\*+\s*|~{2,}\s*|——|——–|—|–|─+)',
    re.MULTILINE,
)

COMPANY_INDICATORS = re.compile(
    r'(?i)\b(inc\.?|ltd\.?|limited|corp\.?|corporation|llc|llp|pvt\.?|'
    r'private\s+limited|gmbh|ag\s*&?\s*co\.?\s*kg|kg|s\.?a\.?|'
    r's\.?p\.?a\.?|n\.?v\.?|pty\.?\s+ltd\.?|sdn\.?\s+bhd\.?|'
    r'co\.?\s*ltd\.?|group|holdings|enterprises|technologies|consulting|'
    r'solutions|services|associates|partners|industries)\b',
)

ROLE_TITLES = re.compile(
    r'(?i)\b(ceo|cfo|cto|coo|vp\b|director|manager|lead\b|head\b|'
    r'founder|owner|president|partner|consultant|engineer|developer|'
    r'chief|executive|principal|analyst|specialist|representative)\b',
)

def extract_domain(from_address: str) -> Optional[str]:
    match = re.search(r'@([\w.-]+)', from_address)
    if not match:
        return None
    domain = match.group(1).strip().lower()
    if domain in FREE_EMAIL_DOMAINS:
        return None
    return domain

_TLD_OR_KNOWN = frozenset({
    'com', 'org', 'net', 'ac', 'gov', 'edu', 'co', 'in', 'uk', 'de', 'fr', 'es',
    'it', 'nl', 'au', 'ca', 'jp', 'cn', 'br', 'sg', 'hk', 'ae', 'sa', 'my', 'th',
    'vn', 'ph', 'id', 'eu', 'ch', 'se', 'no', 'dk', 'fi', 'pl', 'cz', 'at', 'be',
    'nz', 'za', 'mx', 'ar', 'cl', 'co', 'kr', 'tw', 'hk', 'ru', 'za',
    'www', 'mail', 'smtp', 'imap', 'pop', 'email',
})


def domain_to_company_name(domain: str) -> str:
    parts = domain.split('.')
    while parts and parts[0] in _TLD_OR_KNOWN:
        parts.pop(0)
    name = parts[0] if parts else domain
    name = re.sub(r'[^a-zA-Z0-9]', ' ', name)
    name = name.strip()
    name = name.title() if name else domain
    return _normalize_company_name(name)

def extract_signature_body(body_text: Optional[str]) -> Optional[str]:
    if not body_text or not body_text.strip():
        return None
    lines = body_text.splitlines()
    delim_indices = []
    for i, line in enumerate(lines):
        if SIGNATURE_DELIMITERS.match(line):
            delim_indices.append(i)
    if delim_indices:
        start = delim_indices[-1] + 1
    else:
        sig_indicators = ['regards', 'best regards', 'thanks', 'thank you',
                          'sincerely', 'cheers', 'warmly', 'best', 'yours',
                          'cordially', 'respectfully', 'with gratitude',
                          'thank', 'thx', 'rgds', 'br', 'thnks']
        found = None
        for i, line in enumerate(lines):
            stripped = line.strip().lower().rstrip(',.')
            if stripped in sig_indicators:
                found = i
            elif stripped.startswith('regards') or stripped.startswith('best regards'):
                found = i
        if found is not None:
            start = found + 1
        else:
            return None
    sig_lines = lines[start:]
    sig_lines = [l for l in sig_lines if l.strip()]
    if not sig_lines:
        return None
    sig_text = '\n'.join(sig_lines).strip()
    if len(sig_text) > 1000:
        sig_text = sig_text[:1000]
    return sig_text if sig_text else None

_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)
_FORWARD_HEADER = re.compile(r'^(from|sent|to|cc|bcc|date|subject|reply-to|message-id)[:\s]', re.IGNORECASE)
_PERSON_NAME = re.compile(r"^[A-Z][a-zà-ü]+(?:\s+[A-Z][a-zà-ü]+\.?){1,3}$")
_SINGLE_WORD = re.compile(r'^[A-Z][a-z]+$')

def _clean_company_name(raw: str) -> str:
    cleaned = re.sub(r'<[^>]+>', '', raw)
    cleaned = re.sub(r'^[\s•·  *\-–—]+', '', cleaned)
    cleaned = re.sub(r'[\s•·  *\-–—]+$', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if 2 <= len(cleaned) <= 120 else raw

def _looks_like_person(line: str) -> bool:
    if _SINGLE_WORD.match(line):
        return False
    if COMPANY_INDICATORS.search(line):
        return False
    return bool(_PERSON_NAME.match(line))

def extract_company_from_signature_text(sig_text: str) -> Optional[str]:
    lines = [l.strip() for l in sig_text.splitlines() if l.strip()]
    for line in lines:
        if _URL_RE.search(line) or _FORWARD_HEADER.match(line):
            continue
        if COMPANY_INDICATORS.search(line):
            cleaned = _clean_company_name(line)
            if 2 <= len(cleaned) <= 120:
                return cleaned
    for line in lines:
        if _URL_RE.search(line) or _FORWARD_HEADER.match(line):
            continue
        if ROLE_TITLES.search(line) or _looks_like_person(line):
            continue
        cleaned = line.strip()
        if 3 <= len(cleaned) <= 100 and not re.match(r'^[\d\s\+\-\(\)\.]+$', cleaned):
            if not re.match(r'^[\w\s\.\-]+@[\w\.\-]+$', cleaned):
                if not re.match(r'^\+?\d[\d\s\-\(\)\.]+$', cleaned):
                    if cleaned[0].isupper():
                        return _clean_company_name(cleaned)
    return None

_BOUNCE_SENDERS = re.compile(r'(?i)(mailer-daemon|postmaster|mail delivery subsystem|noreply|no-reply|notification)')


def _core_name(name: str) -> str:
    n = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    n = re.sub(r'(?i)\b(pvt\.?\s*ltd\.?|private\s+limited|ltd\.?|limited|llc|inc\.?|corporation|corp\.?|gmbh|llp)\s*', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n.lower()


def _normalize_company_name(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    if name.isupper() and len(name) <= 5:
        return name
    name = re.sub(r'\bPvt\b(?!\.)', 'Pvt.', name, flags=re.IGNORECASE)
    name = re.sub(r'\bLtd\b(?!\.)', 'Ltd.', name, flags=re.IGNORECASE)
    name = re.sub(r'\bPrivate Limited\b', 'Pvt. Ltd.', name, flags=re.IGNORECASE)
    name = re.sub(r'\s{2,}', ' ', name).strip()
    return name


def _choose_canonical(domain_name: Optional[str], sig_name: Optional[str]) -> str:
    if not sig_name:
        return domain_name or "Uncategorized"
    if not domain_name:
        return sig_name
    dc = _core_name(domain_name)
    sc = _core_name(sig_name)
    if dc == sc:
        return sig_name
    if len(dc) >= 3 and (dc in sc or sc in dc):
        return sig_name if len(sig_name) >= len(domain_name) else domain_name
    common = set(dc.split()) & set(sc.split())
    if common:
        return sig_name if len(sig_name) >= len(domain_name) else domain_name
    return sig_name


def extract_company_name(from_address: str, body_text: Optional[str]) -> dict:
    result = {
        "company_name": None,
        "domain_source": None,
        "signature_source": None,
        "domain_free": False,
    }

    if _BOUNCE_SENDERS.search(from_address):
        result["company_name"] = "System Notifications"
        return result

    if body_text:
        body_text = re.sub(r'(?i)<br\s*/?>', '\n', body_text)
        body_text = re.sub(r'(?i)</p>', '\n\n', body_text)
        body_text = re.sub(r'(?i)</div>', '\n', body_text)
        body_text = re.sub(r'<[^>]+>', '', body_text)
        body_text = re.sub(r'&nbsp;', ' ', body_text)
        body_text = re.sub(r'&amp;', '&', body_text)
        body_text = re.sub(r'&lt;', '<', body_text)
        body_text = re.sub(r'&gt;', '>', body_text)

    domain = extract_domain(from_address)
    if domain:
        result["domain_source"] = domain_to_company_name(domain)
        result["domain_free"] = False
    else:
        result["domain_free"] = True

    sig_company = None
    if body_text:
        body_lines = [l.strip() for l in body_text.splitlines() if l.strip()]
        for i, line in enumerate(body_lines):
            stripped = line.lower().rstrip(',.')
            if stripped in ('regards', 'best regards', 'thanks', 'sincerely', 'cheers', 'best'):
                before_sig_lines = body_lines[max(0, i-8):i]
                for sl in reversed(before_sig_lines):
                    if COMPANY_INDICATORS.search(sl):
                        sig_company = _clean_company_name(sl)
                        break
                break

    if not sig_company:
        sig_text = extract_signature_body(body_text)
        if sig_text:
            sig_company = extract_company_from_signature_text(sig_text)

    if sig_company:
        result["signature_source"] = sig_company

    if result["signature_source"]:
        result["company_name"] = _choose_canonical(
            result["domain_source"], result["signature_source"]
        )
    else:
        result["company_name"] = result["domain_source"]

    if result["company_name"]:
        result["company_name"] = _normalize_company_name(result["company_name"])
    return result

def extract_thread_text_from_body(body_text: Optional[str]) -> Optional[str]:
    if not body_text:
        return None
    parts = re.split(r'\n\s*[-]+\s*Original Message\s*[-]+\s*\n', body_text, flags=re.IGNORECASE)
    parts = re.split(r'\n\s*On\s+.+\s+<\s?[^>]+\s?>\s? wrote:\s*\n', parts[0])
    parts = re.split(r'\n\s*[>]+\s', parts[0])
    return parts[0].strip()
