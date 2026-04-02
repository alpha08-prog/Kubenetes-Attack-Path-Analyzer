"""
narrator_service.py - Groq API narration.
Uses Groq chat-completions API to generate structured, human-readable findings.
"""

import json
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.services.analysis_service import get_full_analysis
from app.services.history_service import record_analysis_run
from app.utils.helpers import utc_now
from app.utils.logger import get_logger
from app.utils.prompt_templates import (
    FALLBACK_FINDINGS,
    NARRATOR_SYSTEM_PROMPT,
    build_narrator_prompt,
    build_report_header,
    build_simulation_prompt,
)

logger = get_logger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"


def _sanitize_error_detail(message: str) -> str:
    if not message:
        return "unknown error"
    sanitized = re.sub(r"gsk_[A-Za-z0-9]+", "gsk_***", message)
    return sanitized.strip()


def _build_fallback_findings(error_detail: str | None = None) -> list:
    findings = [dict(item) for item in FALLBACK_FINDINGS]
    if error_detail:
        detail = _sanitize_error_detail(error_detail)
        findings[0]["description"] = (
            "The AI narration service could not be reached. "
            f"Provider detail: {detail}. Raw algorithm results are available in the analysis endpoints."
        )
    return findings


def _candidate_models() -> list[str]:
    ordered = [
        settings.GROQ_MODEL,
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ]
    seen = set()
    unique = []
    for name in ordered:
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return unique


def _extract_chat_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("Groq response missing choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Groq response missing message content")
    return content.strip()


def _request_groq(prompt: str, model_name: str) -> str:
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set in .env\n"
            "Get a key at: https://console.groq.com"
        )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=45.0) as client:
        response = client.post(GROQ_BASE_URL, headers=headers, json=payload)

    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            detail = (
                body.get("error", {}).get("message")
                or body.get("message")
                or response.text
            )
        except Exception:
            detail = response.text
        raise RuntimeError(f"{response.status_code} {detail}")

    return _extract_chat_content(response.json())


def _generate_content_with_fallback(prompt: str) -> tuple[str, str]:
    first_error = None
    last_error = None

    for model_name in _candidate_models():
        try:
            content = _request_groq(prompt, model_name)
            return content, model_name
        except Exception as e:
            detail = f"{model_name}: {_sanitize_error_detail(str(e))}"
            if first_error is None:
                first_error = detail
            last_error = detail
            logger.warning("Groq model '%s' failed: %s", model_name, e)

    raise RuntimeError(first_error or last_error or "All candidate Groq models failed")


def generate_report(cluster_name: str = "nokia-telecom-cluster") -> dict:
    """
    Run all algorithms, send results to Groq, return structured report.
    """
    logger.info("Generating AI security report for cluster: %s", cluster_name)

    analysis = get_full_analysis()
    prompt = build_narrator_prompt(
        attack_path=analysis.get("attack_path"),
        blast_radius=analysis.get("blast_radius"),
        cycles=analysis.get("cycles"),
        critical_nodes=analysis.get("critical_nodes"),
        cluster_name=cluster_name,
    )

    findings = _call_groq(prompt)
    record_analysis_run(
        cluster_name=cluster_name,
        source="mock" if settings.MOCK_MODE else "kubectl",
        has_ai_report=True,
        findings=findings,
        triggered_by="report",
    )
    timestamp = utc_now()
    header = build_report_header(cluster_name, len(findings), timestamp)

    logger.info("Report generated: %d findings", len(findings))
     
    from app.services.slack_service import send_critical_alert
    send_critical_alert(findings, cluster_name=cluster_name)
    return {**header, "findings": findings}


def narrate_simulation(simulation_result: dict) -> str:
    """
    Ask Groq to explain the impact of a node removal in 2-3 sentences.
    """
    prompt = build_simulation_prompt(simulation_result)

    try:
        content, _ = _generate_content_with_fallback(prompt)
        return content
    except Exception as e:
        logger.error("Groq simulation narrative failed: %s", e)
        return (
            f"Removing '{simulation_result.get('node_label')}' breaks "
            f"{simulation_result.get('paths_broken', 0)} of "
            f"{simulation_result.get('paths_before', 0)} attack paths. "
            "Check GROQ_API_KEY in .env if you expected a detailed explanation."
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=False,
)
def _call_groq(user_prompt: str) -> list:
    """
    Call the Groq API and parse the JSON findings array.
    Retries on transient failures and falls back when all retries fail.
    """
    try:
        raw_text, model_used = _generate_content_with_fallback(user_prompt)

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        findings = json.loads(raw_text)
        if not isinstance(findings, list):
            raise ValueError("Groq returned non-list JSON")

        logger.info("Groq returned %d findings using model %s", len(findings), model_used)
        return findings
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Groq JSON response: %s", e)
        return _build_fallback_findings("Groq returned invalid JSON")
    except Exception as e:
        logger.error("Groq API call failed: %s", e)
        return _build_fallback_findings(str(e))


def groq_healthcheck() -> dict:
    """
    Minimal runtime check for Groq configuration and auth.
    """
    configured = bool(settings.GROQ_API_KEY)
    base = {
        "provider": "groq",
        "configured": configured,
        "model": settings.GROQ_MODEL,
        "candidates": _candidate_models(),
    }

    if not configured:
        return {**base, "ok": False, "mode": "missing_key", "detail": "GROQ_API_KEY not set"}

    try:
        content, model_used = _generate_content_with_fallback("Reply with: OK")
        return {**base, "ok": True, "mode": "live", "model_used": model_used, "detail": content[:64]}
    except Exception as e:
        logger.error("Groq healthcheck failed: %s", e)
        return {**base, "ok": False, "mode": "error", "detail": _sanitize_error_detail(str(e))}
