import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:14b"
SUMMARIZE_TIMEOUT = 120
COMPANY_TIMEOUT = 60

def _call_ollama(prompt: str, system_prompt: str, timeout: int = 30, max_tokens: int = 4096) -> Optional[str]:
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.1},
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
        "You are audAInsights, a supply-chain AI analyst. Produce a comprehensive "
        "narrative that tells the complete story of this purchase order or document "
        "from the first communication to the last. You MUST include:\n"
        "- ALL company names, contacts, and logistics partners mentioned\n"
        "- ALL locations (origin, destination, ports, warehouses)\n"
        "- ALL key dates (order dates, pickup dates, delays, revised dates)\n"
        "- ALL charges, costs, and financial details\n"
        "- ALL decisions, action items, and status changes\n"
        "- ALL document references (PO numbers, invoice numbers, document IDs)\n"
        "Do NOT omit any entity, location, or party. Write in plain text paragraphs "
        "with no markdown. Be thorough — prioritize completeness over brevity."
    )
    text = thread_text.strip()
    if len(text) > 20000:
        text = text[:20000] + "\n\n[...truncated]"
    prompt = f"Content:\n\n{text}\n\nFull story:"
    return _call_ollama(prompt, system_prompt, timeout=SUMMARIZE_TIMEOUT, max_tokens=4096)

def update_summary(context: str) -> Optional[str]:
    """Incremental summarization: merge new information into the existing story
    without dropping any previously mentioned entity or detail."""
    if not context or not context.strip():
        return None
    system_prompt = (
        "You are audAInsights, a supply-chain AI analyst. You are given a previous "
        "story along with new messages and/or document data. Merge the new information "
        "into the existing story to produce a single updated comprehensive narrative.\n"
        "You MUST:\n"
        "- Retain ALL entities, parties, and locations from the previous story\n"
        "- Incorporate ALL new parties, dates, charges, and events from the new content\n"
        "- NOT drop or omit anything previously mentioned\n"
        "- Write a flowing plain-text narrative with no markdown\n"
        "Prioritize completeness over brevity."
    )
    text = context.strip()
    if len(text) > 20000:
        text = text[:20000] + "\n\n[...truncated]"
    prompt = f"Context:\n\n{text}\n\nUpdated full story:"
    return _call_ollama(prompt, system_prompt, timeout=SUMMARIZE_TIMEOUT, max_tokens=4096)


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
