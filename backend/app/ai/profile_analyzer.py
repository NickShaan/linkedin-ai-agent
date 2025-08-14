# app/ai/profile_analyzer.py
import os, json, re
import google.generativeai as genai
from typing import Optional

PROMPT = """You are a career analyst. Using the data below, produce:
1) background_summary: 4-6 sentences about the person's background.
2) tone: 3-5 adjectives that match their writing/brand tone.
3) keywords: 8-12 short keywords/phrases relevant to expertise.
Return strict JSON with keys: background_summary, tone (array), keywords (array).

LINKEDIN:
{linkedin}

RESUME:
{resume}
"""

def analyze_profile(linkedin: dict, resume_text: Optional[str], api_key: Optional[str] = None) -> dict:
    # prefer per-user key; fallback to process env
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        # safe fallback so UI gets something instead of a 500
        return {"background_summary": "", "tone": [], "keywords": []}

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    txt = PROMPT.format(linkedin=str(linkedin or {}), resume=resume_text or "")
    resp = model.generate_content(txt)
    out = (getattr(resp, "text", None) or "").strip()

    # robust JSON extraction
    m = re.search(r"\{[\s\S]*\}", out)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    # last resort: return raw text in background_summary
    return {"background_summary": out, "tone": [], "keywords": []}
