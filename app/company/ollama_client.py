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
        "You are audAInsights, a supply-chain AI analyst. Build a structured "
        "summary of this purchase order/document timeline using bullet points "
        "and conversation-style notes (who said what).\n\n"
        "Structure your output as:\n"
        "**Parties Involved:** bullet list of all companies, contacts, roles\n"
        "**Timeline:** chronological bullet points showing what happened, when, "
        "and who said/did what (use \"Person → Person: message\" format)\n"
        "**Key Details:** bullet list of locations, dates, costs, documents, "
        "action items, decisions\n\n"
        "You MUST capture:\n"
        "- ALL company names, contacts, and logistics partners\n"
        "- ALL locations (origin, destination, ports, warehouses)\n"
        "- ALL key dates and timeline events\n"
        "- ALL charges, costs, and financial figures\n"
        "- ALL decisions, action items, status changes\n"
        "- ALL document references (PO numbers, invoice numbers, document IDs)\n"
        "Do NOT omit any entity, location, or detail. Be precise and complete."
    )
    text = thread_text.strip()
    if len(text) > 20000:
        text = text[:20000] + "\n\n[...truncated]"
    prompt = f"Content:\n\n{text}\n\nStructured summary:"
    return _call_ollama(prompt, system_prompt, timeout=SUMMARIZE_TIMEOUT, max_tokens=4096)

def update_summary(context: str) -> Optional[str]:
    """Incremental summarization: merge new information into the existing
    structured summary without dropping any entity or detail."""
    if not context or not context.strip():
        return None
    system_prompt = (
        "You are audAInsights, a supply-chain AI analyst. You are given a previous "
        "structured summary along with new messages and/or document data. Merge the "
        "new information into the existing structured summary.\n\n"
        "Maintain the same structured format:\n"
        "**Parties Involved:**\n"
        "**Timeline:**\n"
        "**Key Details:**\n\n"
        "You MUST:\n"
        "- Retain ALL entities, parties, locations, and events from the previous summary\n"
        "- Incorporate ALL new parties, dates, charges, events from the new content\n"
        "- NOT drop or omit anything previously mentioned\n"
        "- Use conversation-style \"Who → Who: what was said\" format in Timeline\n"
        "Be precise and complete."
    )
    text = context.strip()
    if len(text) > 20000:
        text = text[:20000] + "\n\n[...truncated]"
    prompt = f"Context:\n\n{text}\n\nUpdated structured summary:"
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
