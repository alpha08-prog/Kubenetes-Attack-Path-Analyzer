"""
narrator_service.py — Gemini API Narration  ★ KEY DIFFERENTIATOR ★
Uses Google Gemini 2.0 Flash (free tier) to generate structured,
human-readable security findings from algorithm results.

Free API key: https://aistudio.google.com → Get API Key (no card needed)
"""

import json
from tenacity import retry, stop_after_attempt, wait_exponential

import google.generativeai as genai

from app.config import settings
from app.services.analysis_service import get_full_analysis
from app.utils.logger import get_logger
from app.utils.helpers import utc_now
from app.utils.prompt_templates import (
    NARRATOR_SYSTEM_PROMPT,
    build_narrator_prompt,
    build_report_header,
    build_simulation_prompt,
    FALLBACK_FINDINGS,
)

logger = get_logger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set in .env\n"
                "Get a free key at: https://aistudio.google.com"
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name   = settings.GEMINI_MODEL,
            system_instruction = NARRATOR_SYSTEM_PROMPT,
        )
    return _model


# ─── Main report generator ────────────────────────────────────────────────────

def generate_report(cluster_name: str = "nokia-telecom-cluster") -> dict:
    """
    Run all algorithms, send results to Gemini, return structured report.
    Called by routes_report.py.
    """
    logger.info("Generating AI security report for cluster: %s", cluster_name)

    analysis = get_full_analysis()

    prompt = build_narrator_prompt(
        attack_path    = analysis.get("attack_path"),
        blast_radius   = analysis.get("blast_radius"),
        cycles         = analysis.get("cycles"),
        critical_nodes = analysis.get("critical_nodes"),
        cluster_name   = cluster_name,
    )

    findings  = _call_gemini(prompt)
    timestamp = utc_now()
    header    = build_report_header(cluster_name, len(findings), timestamp)

    logger.info("Report generated: %d findings", len(findings))
    return {**header, "findings": findings}


# ─── Simulation narrative ─────────────────────────────────────────────────────

def narrate_simulation(simulation_result: dict) -> str:
    """
    Ask Gemini to explain the impact of a node removal in 2-3 sentences.
    Called by simulator_service.py.
    """
    prompt = build_simulation_prompt(simulation_result)

    try:
        model    = _get_model()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error("Gemini simulation narrative failed: %s", e)
        return (
            f"Removing '{simulation_result.get('node_label')}' breaks "
            f"{simulation_result.get('paths_broken', 0)} of "
            f"{simulation_result.get('paths_before', 0)} attack paths. "
            "Check GEMINI_API_KEY in .env if you expected a detailed explanation."
        )


# ─── Gemini API call ──────────────────────────────────────────────────────────

@retry(
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=10),
    reraise = False,
)
def _call_gemini(user_prompt: str) -> list:
    """
    Call the Gemini API and parse the JSON findings array.
    Retries up to 3 times with exponential backoff on transient failures.
    Falls back to FALLBACK_FINDINGS if all retries fail.
    """
    try:
        model    = _get_model()
        response = model.generate_content(user_prompt)
        raw_text = response.text.strip()

        # Strip markdown code fences if Gemini wraps output in ```json ... ```
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        findings = json.loads(raw_text)

        if not isinstance(findings, list):
            raise ValueError("Gemini returned non-list JSON")

        logger.info("Gemini returned %d findings", len(findings))
        return findings

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini JSON response: %s", e)
        return FALLBACK_FINDINGS

    except Exception as e:
        logger.error("Gemini API call failed: %s", e)
        return FALLBACK_FINDINGS


def gemini_healthcheck() -> dict:
    """
    Minimal runtime check for Gemini configuration + auth.

    Note: This performs a tiny Gemini request when a key is present.
    Use this endpoint intentionally (e.g., /api/ai/health) rather than
    on every startup.
    """
    configured = bool(settings.GEMINI_API_KEY)
    base = {"provider": "gemini", "configured": configured, "model": settings.GEMINI_MODEL}

    if not configured:
        return {**base, "ok": False, "mode": "missing_key", "detail": "GEMINI_API_KEY not set"}

    try:
        model = _get_model()
        response = model.generate_content("Reply with: OK")
        text = (getattr(response, "text", "") or "").strip()
        return {**base, "ok": True, "mode": "live", "detail": text[:64]}
    except Exception as e:
        logger.error("Gemini healthcheck failed: %s", e)
        return {**base, "ok": False, "mode": "error", "detail": str(e)}
