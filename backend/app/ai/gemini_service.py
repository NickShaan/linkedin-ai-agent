# app/ai/gemini_service.py
import os, time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, DeadlineExceeded, ServiceUnavailable

DEFAULT_MODEL = "gemini-1.5-flash"

def _configure(api_key: str | None):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    genai.configure(api_key=key)

def generate_post(api_key: str | None, prompt: str, model: str = DEFAULT_MODEL, retries: int = 3) -> str:
    """
    Generate text with Gemini. Handles transient errors and rate limits with basic backoff.
    Raises ResourceExhausted if the caller should throttle.
    """
    _configure(api_key)
    model_obj = genai.GenerativeModel(model)

    for attempt in range(retries):
        try:
            resp = model_obj.generate_content(prompt)
            return (resp.text or "").strip()
        except ResourceExhausted as e:
            # Free-tier 15 req/min → return/raise so route can map to HTTP 429
            if attempt >= retries - 1:
                raise
            # Optional: honor server-provided delay; fallback to simple backoff
            wait = getattr(getattr(e, "retry_delay", None), "seconds", None)
            time.sleep(wait if wait is not None else 5 * (attempt + 1))
        except (DeadlineExceeded, ServiceUnavailable):
            if attempt >= retries - 1:
                raise
            time.sleep(2 * (attempt + 1))

    return ""
