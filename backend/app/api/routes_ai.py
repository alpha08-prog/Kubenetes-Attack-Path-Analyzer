"""
routes_ai.py - AI/LLM utility endpoints.
GET /api/ai/health -> checks Groq configuration/auth.
"""

from fastapi import APIRouter

from app.services.narrator_service import groq_healthcheck

router = APIRouter()


@router.get("/health")
def ai_health():
    return groq_healthcheck()
