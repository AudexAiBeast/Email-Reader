import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"
SUMMARIZE_TIMEOUT = 60
COMPANY_TIMEOUT = 30

def _call_ollama(prompt: str, system_prompt: str, timeout: int = 30) -> Optional[str]:
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"num_predict": 2048, "temperature": 0.1},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except httpx.ConnectError:
        logger.warning("Ollama not reachable at %s", OLLAMA_BASE_URL)
        return None
    except Exception as exc:
        logger.error("Ollama call failed: %s", exc)
        return None

def summarize_thread(thread_text: str) -> Optional[str]:
    if not thread_text or not thread_text.strip():
        return None
    system_prompt = (
        "You are audAInsights, an AI email analyst. Summarize the following email thread "
        "concisely: who said what, what decisions were made, what action items exist. "
        "Keep the summary under 150 words. Use plain text, no markdown."
    )
    text = thread_text.strip()
    if len(text) > 15000:
        text = text[:15000] + "\n\n[...truncated]"
    prompt = f"Email thread:\n\n{text}\n\nSummary:"
    return _call_ollama(prompt, system_prompt, timeout=SUMMARIZE_TIMEOUT)

def extract_company_from_signature(sig_text: str) -> Optional[str]:
    if not sig_text or not sig_text.strip():
        return None
    system_prompt = (
        "You are a company name extractor. From the email signature below, extract "
        "only the company/organization name. Reply with just the company name, nothing else. "
        "If no company is found, reply with \"NONE\"."
    )
    text = sig_text.strip()
    if len(text) > 2000:
        text = text[:2000]
    prompt = f"Email signature:\n\n{text}\n\nCompany name:"
    result = _call_ollama(prompt, system_prompt, timeout=COMPANY_TIMEOUT)
    if result and result.upper() != "NONE" and result != "":
        return result
    return None
