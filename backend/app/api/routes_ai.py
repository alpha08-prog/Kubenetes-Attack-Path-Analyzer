"""
routes_ai.py — AI / LLM utility endpoints
GET /api/ai/health → checks Gemini configuration/auth
"""

from fastapi import APIRouter

from app.services.narrator_service import gemini_healthcheck

router = APIRouter()


@router.get("/health")
def ai_health():
    return gemini_healthcheck()

