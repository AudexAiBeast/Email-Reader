import logging
import re
from email.utils import parsedate_to_datetime
from typing import Optional

logger = logging.getLogger(__name__)

FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com",
    "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
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

def domain_to_company_name(domain: str) -> str:
    parts = domain.split('.')
    if parts[0] == 'www':
        parts = parts[1:]
    name = parts[0] if parts else domain
    name = re.sub(r'[^a-zA-Z0-9]', ' ', name)
    name = name.strip()
    return name.title() if name else domain

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

def extract_company_from_signature_text(sig_text: str) -> Optional[str]:
    lines = [l.strip() for l in sig_text.splitlines() if l.strip()]
    for line in lines:
        if COMPANY_INDICATORS.search(line):
            cleaned = re.sub(r'^[\s•·  *\-–—]+', '', line)
            cleaned = re.sub(r'[\s•·  *\-–—]+$', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            if 2 <= len(cleaned) <= 120:
                return cleaned
    for line in lines:
        if ROLE_TITLES.search(line):
            continue
        cleaned = line.strip()
        if 3 <= len(cleaned) <= 100 and not re.match(r'^[\d\s\+\-\(\)\.]+$', cleaned):
            if not re.match(r'^[\w\s\.\-]+@[\w\.\-]+$', cleaned):
                if not re.match(r'^\+?\d[\d\s\-\(\)\.]+$', cleaned):
                    if cleaned[0].isupper():
                        return cleaned
    return None

def extract_company_name(from_address: str, body_text: Optional[str]) -> dict:
    result = {
        "company_name": None,
        "domain_source": None,
        "signature_source": None,
        "domain_free": False,
    }
    domain = extract_domain(from_address)
    if domain:
        result["domain_source"] = domain_to_company_name(domain)
        result["domain_free"] = False
    else:
        result["domain_free"] = True
    sig_text = extract_signature_body(body_text)
    if sig_text:
        sig_company = extract_company_from_signature_text(sig_text)
        if sig_company:
            result["signature_source"] = sig_company
    if result["signature_source"]:
        result["company_name"] = result["signature_source"]
    else:
        result["company_name"] = result["domain_source"]
    return result

def extract_thread_text_from_body(body_text: Optional[str]) -> Optional[str]:
    if not body_text:
        return None
    parts = re.split(r'\n\s*[-]+\s*Original Message\s*[-]+\s*\n', body_text, flags=re.IGNORECASE)
    parts = re.split(r'\n\s*On\s+.+\s+<\s?[^>]+\s?>\s? wrote:\s*\n', parts[0])
    parts = re.split(r'\n\s*[>]+\s', parts[0])
    return parts[0].strip()
