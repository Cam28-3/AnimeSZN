import anthropic

from app.config import settings

AGENT_MODEL = "claude-sonnet-5"
SUMMARIZATION_MODEL = "claude-haiku-4-5-20251001"

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
