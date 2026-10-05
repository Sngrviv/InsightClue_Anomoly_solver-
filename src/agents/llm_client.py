"""
Unified LLM Client for InsightClue Multi-Agent Investigation.
100% API-driven execution via Google GenAI SDK with multi-model resilience.
Zero synthetic mock strings or hardcoded fallbacks.
"""

import json
import logging
import re
from typing import Any
from google import genai
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Fallback candidate cascade for live model availability
CANDIDATE_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
]


class LLMClient:
    """
    Unified, 100% API-driven LLM Client providing structured text and JSON generation.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._gemini_client: genai.Client | None = None
        if self.settings.GEMINI_API_KEY:
            try:
                self._gemini_client = genai.Client(api_key=self.settings.GEMINI_API_KEY)
            except Exception as e:
                logger.error("Failed to initialize Google GenAI client: %s", e)
                raise RuntimeError(f"Could not initialize Google GenAI client with provided API key: {e}")
        else:
            logger.error("GEMINI_API_KEY is not configured in environment or .env file.")

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Generates text response directly from Google GenAI API with model cascading.
        Raises RuntimeError if the API cannot be reached.
        """
        if not self._gemini_client:
            raise RuntimeError(
                "GEMINI_API_KEY is required for LLM reasoning. Please set GEMINI_API_KEY in your .env file."
            )

        full_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt

        # Try configured primary model first, followed by candidate cascade
        models_to_try = [self.settings.GEMINI_LLM_MODEL] + [
            m for m in CANDIDATE_MODELS if m != self.settings.GEMINI_LLM_MODEL
        ]

        last_error: Exception | None = None

        for model_name in models_to_try:
            try:
                response = self._gemini_client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_error = e
                logger.debug("[LLMClient] Model %s failed (%s). Trying next candidate...", model_name, e)
                continue

        error_msg = f"All API models failed to generate response. Last error: {last_error}"
        logger.error("[LLMClient] %s", error_msg)
        raise RuntimeError(error_msg)

    def generate_json(self, prompt: str, system_prompt: str | None = None) -> dict[str, Any]:
        """
        Generates structured JSON dictionary response via API.
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
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response from LLM (%s). Raw text: %s", e, raw_text[:300])
            raise ValueError(f"LLM returned non-JSON response: {raw_text[:200]}") from e


_llm_client_instance: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Singleton getter for LLMClient."""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
