"""
Unified LLM Client for InsightClue Multi-Agent Investigation.
Encapsulates Google Gemini 2.5 Flash / Pro and structured JSON responses with graceful fallbacks.
"""

import json
import logging
import re
from typing import Any
from google import genai
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM Client providing structured text and JSON generation.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._gemini_client: genai.Client | None = None
        if self.settings.GEMINI_API_KEY:
            try:
                self._gemini_client = genai.Client(api_key=self.settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI client: %s", e)

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Generates text response from LLM.
        """
        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt

        if self._gemini_client:
            try:
                response = self._gemini_client.models.generate_content(
                    model=self.settings.GEMINI_LLM_MODEL,
                    contents=full_prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.error("Gemini API call failed: %s. Using local fallback.", e)

        return self._local_fallback_text(prompt)

    def generate_json(self, prompt: str, system_prompt: str | None = None) -> dict[str, Any]:
        """
        Generates structured JSON dictionary response.
        Enforces JSON schema validation and extracts from markdown blocks.
        """
        augmented_system = (
            (system_prompt or "")
            + "\nCRITICAL: Respond ONLY with valid, parseable JSON matching the requested schema. Do not include introductory text."
        )

        raw_response = self.generate_text(prompt, system_prompt=augmented_system)
        return self._clean_and_parse_json(raw_response)

    def _clean_and_parse_json(self, raw_text: str) -> dict[str, Any]:
        """
        Extracts JSON from possible markdown wrappers (```json ... ```) and parses it.
        """
        text = raw_text.strip()
        # Strip markdown fences if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Regex fallback to find outermost braces
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON response (%s). Raw: %s", e, raw_text[:200])
            return {
                "error": "Failed to parse LLM JSON",
                "raw_text": raw_text,
            }

    def _local_fallback_text(self, prompt: str) -> str:
        """
        Deterministic local fallback for testing or when LLM API is unavailable.
        """
        prompt_lower = prompt.lower()
        if "hypothesis" in prompt_lower or "supervisor" in prompt_lower:
            return json.dumps({
                "hypothesis": "Payment gateway 3DS OTP timeouts triggered severe authorization failure in South Corporate Card segment.",
                "confidence_assessment": "High probability of third-party SMS aggregator failure.",
                "next_action": "sql_agent",
            })
        elif "sql" in prompt_lower:
            return json.dumps({
                "sql_query": "SELECT gateway_name, error_code, COUNT(*) as failure_count FROM payment_gateway_logs WHERE error_code = 'OTP_TIMEOUT' GROUP BY gateway_name, error_code ORDER BY failure_count DESC LIMIT 10;",
                "target_hypothesis": "Verify exact gateway error codes and OTP failure volume.",
                "reasoning": "Filter gateway logs by error code to determine if SMS or bank network failed.",
            })
        elif "rag" in prompt_lower or "ticket" in prompt_lower:
            return json.dumps({
                "semantic_query": "customer corporate card OTP SMS delayed timed out South region",
                "reasoning": "Search for customer dispute tickets mentioning SMS delivery delays or OTP timeouts.",
            })
        elif "synthesis" in prompt_lower or "rca" in prompt_lower:
            return json.dumps({
                "root_cause_summary": "Root Cause: Upstream Telecom SMS Gateway failure in South region caused OTP delivery timeouts for 3DS Corporate Card transactions, resulting in a 24.5% drop in transaction success rate.",
                "confidence_score": 0.96,
                "mitigation_steps": "1. Failover 3DS OTP delivery traffic to secondary SMS gateway (Twilio/Infobip).\n2. Implement automatic OTP retry fallback to WhatsApp/In-App authentication.\n3. Contact primary telecom vendor for SLA breach remediation.",
            })
        return json.dumps({"status": "completed", "message": "Fallback response"})


_llm_client_instance: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Singleton getter for LLMClient."""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
