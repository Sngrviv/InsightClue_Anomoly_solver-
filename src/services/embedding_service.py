"""
Unified Embedding Service for InsightClue.
Supports Google Gemini Embedding 2 (with 768 output dimensions) with an automatic
local FastEmbed ONNX fallback for fast, offline, zero-quota bulk operations.
"""

import os
import sys
from typing import Sequence
import numpy as np
from src.config.settings import get_settings
from src.models.dispute_tickets import EMBEDDING_DIMENSION

settings = get_settings()

# Lazy-loaded clients
_gemini_client = None
_local_embedding_model = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            try:
                from google import genai
                _gemini_client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"[Embedding] Failed to initialize Gemini Client: {e}. Falling back to FastEmbed.")
                _gemini_client = False
        else:
            _gemini_client = False
    return _gemini_client


def _get_local_model():
    global _local_embedding_model
    if _local_embedding_model is None:
        from fastembed import TextEmbedding
        # Default local model: BAAI/bge-small-en-v1.5 (runs fast on CPU with ONNX)
        _local_embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _local_embedding_model


def _pad_or_truncate_vector(vec: list[float] | np.ndarray, target_dim: int = EMBEDDING_DIMENSION) -> list[float]:
    """Ensures embedding vector precisely matches the database target dimension (768)."""
    arr = np.array(vec, dtype=np.float32)
    current_dim = len(arr)
    if current_dim == target_dim:
        return arr.tolist()
    elif current_dim < target_dim:
        padded = np.pad(arr, (0, target_dim - current_dim), mode="constant")
        norm = np.linalg.norm(padded)
        if norm > 0:
            padded = padded / norm
        return padded.tolist()
    else:
        truncated = arr[:target_dim]
        norm = np.linalg.norm(truncated)
        if norm > 0:
            truncated = truncated / norm
        return truncated.tolist()


def generate_embedding(text: str, prefer_gemini: bool = True) -> list[float]:
    """Generates a 768-dimensional embedding for a single text string."""
    return generate_embeddings_batch([text], prefer_gemini=prefer_gemini)[0]


def generate_embeddings_batch(
    texts: Sequence[str],
    prefer_gemini: bool = False,
) -> list[list[float]]:
    """
    Generates 768-dimensional embeddings for a batch of text strings.
    - Uses local FastEmbed for bulk operations (>5 items or prefer_gemini=False) for instant CPU speed with 0 API quota consumption.
    - Uses Google Gemini Embedding 2 for single queries / small batches when prefer_gemini=True.
    """
    if not texts:
        return []

    if prefer_gemini and len(texts) <= 5:
        client = _get_gemini_client()
        if client:
            try:
                embeddings = []
                for t in texts:
                    resp = client.models.embed_content(
                        model="gemini-embedding-2",
                        contents=t,
                        config={"output_dimensionality": EMBEDDING_DIMENSION},
                    )
                    if resp.embeddings and resp.embeddings[0].values is not None:
                        embeddings.append(_pad_or_truncate_vector(resp.embeddings[0].values, EMBEDDING_DIMENSION))
                    else:
                        raise ValueError("Gemini API returned empty embedding response.")
                return embeddings
            except Exception as e:
                print(f"[Embedding] Gemini Embedding API error ({e}). Using local FastEmbed.")

    # High-speed local FastEmbed batch execution
    local_model = _get_local_model()
    raw_embeddings = list(local_model.embed(texts))
    return [_pad_or_truncate_vector(emb, EMBEDDING_DIMENSION) for emb in raw_embeddings]
