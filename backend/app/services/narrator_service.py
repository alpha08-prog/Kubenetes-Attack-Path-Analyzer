"""
narrator_service.py — Claude API Narration  ★ KEY DIFFERENTIATOR ★
Sends algorithm results to Claude and gets back structured,
human-readable security findings with kill chains and fixes.
"""

import json
from tenacity import retry, stop_after_attempt, wait_exponential

import anthropic

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

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ─── Main report generator ────────────────────────────────────────────────────

def generate_report(cluster_name: str = "nokia-telecom-cluster") -> dict:
    """
    Run all algorithms, send results to Claude, return structured report.
    Called by routes_report.py.

    Returns:
        Full ReportResponse-shaped dict with findings list.
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

    findings = _call_claude(prompt)
    timestamp = utc_now()
    header = build_report_header(cluster_name, len(findings), timestamp)

    logger.info("Report generated: %d findings", len(findings))

    return {**header, "findings": findings}


# ─── Simulation narrative ─────────────────────────────────────────────────────

def narrate_simulation(simulation_result: dict) -> str:
    """
    Ask Claude to explain the impact of a node removal simulation in 2-3 sentences.
    Called by simulator_service.py after running the what-if analysis.
    """
    prompt = build_simulation_prompt(simulation_result)

    try:
        client = _get_client()
        message = client.messages.create(
            model      = settings.CLAUDE_MODEL,
            max_tokens = 300,
            messages   = [{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error("Claude simulation narrative failed: %s", e)
        return (
            f"Removing '{simulation_result.get('node_label')}' breaks "
            f"{simulation_result.get('paths_broken', 0)} of "
            f"{simulation_result.get('paths_before', 0)} attack paths. "
            "Check the Claude API key if you expected a detailed explanation."
        )


# ─── Claude API call ──────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=False,
)
def _call_claude(user_prompt: str) -> list:
    """
    Call the Claude API and parse the JSON findings array.
    Retries up to 3 times with exponential backoff on transient failures.
    Falls back to FALLBACK_FINDINGS if all retries fail.
    """
    try:
        client = _get_client()

        message = client.messages.create(
            model      = settings.CLAUDE_MODEL,
            max_tokens = 1500,
            system     = NARRATOR_SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": user_prompt}],
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps in ```json ... ```
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        findings = json.loads(raw_text)

        if not isinstance(findings, list):
            raise ValueError("Claude returned non-list JSON")

        logger.info("Claude returned %d findings", len(findings))
        return findings

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude JSON response: %s", e)
        return FALLBACK_FINDINGS

    except anthropic.AuthenticationError:
        logger.error("Invalid ANTHROPIC_API_KEY — check your .env file")
        return FALLBACK_FINDINGS

    except anthropic.RateLimitError:
        logger.warning("Claude rate limit hit — retrying...")
        raise  # let tenacity retry

    except Exception as e:
        logger.error("Claude API call failed: %s", e)
        return FALLBACK_FINDINGS