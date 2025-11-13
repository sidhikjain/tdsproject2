
# app.py
import os
import time
import base64
import asyncio
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import httpx
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

APP_SECRET = os.getenv("APP_SECRET")  # example single static secret
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "your-gemini-model")

app = FastAPI()

class QuizPayload(BaseModel):
    email: str
    secret: str
    url: str
    # ... accept other fields but ignore unknown
    class Config:
        extra = "allow"

async def call_gemini(prompt: str, model: str = GEMINI_MODEL) -> str:
    """
    For demo/testing, return a static answer or echo the prompt.
    """
    # Return a dummy JSON string as answer
    return '{"answer": "demo"}'

async def fetch_quiz_page_and_extract(url: str, timeout_s: int = 60) -> Dict[str, Any]:
    """
    Use Playwright to render JS and extract page content.
    Returns a dictionary with extracted 'submit_url', 'question', and any other fields.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"], headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout_s * 1000)
        # Generic extraction strategies:
        # 1) Look for a JSON in <pre> or a visible element
        # 2) Evaluate window variables
        # Example: read innerText of <pre> or #result
        result = {}
        try:
            pre = await page.query_selector("pre")
            if pre:
                txt = await pre.inner_text()
                result["raw_pre"] = txt
            # attempt to find a submit URL in the DOM
            # many pages include a JSON with "url" or "submit"
            # we also try to run page.evaluate to access JS variables if present
            # e.g. window.__QUIZ_DATA__ or similar:
            try:
                js_data = await page.evaluate("""() => {
                    // return any obvious global quiz data object if present
                    return window.__QUIZ_DATA__ || null;
                }""")
                result["window_quiz_data"] = js_data
            except Exception:
                pass
            # gather visible text
            result["body_text"] = await page.content()
        finally:
            await context.close()
            await browser.close()
        return result

async def parse_and_solve(extracted: Dict[str, Any], payload: QuizPayload, time_remaining_s: int) -> Dict[str, Any]:
    """
    Implement your solving logic here.
    This might use Gemini to produce an answer, or process files, etc.
    Return a dict to POST to the submit URL (e.g. {"answer": 123})
    """
    # Simple example: if extracted contains JSON in raw_pre that is base64,
    # decode and parse JSON, otherwise call Gemini with page content.
    if "raw_pre" in extracted:
        raw = extracted["raw_pre"].strip()
        try:
            # Some quizzes embed base64-encoded data
            decoded = base64.b64decode(raw).decode("utf-8")
            # try parse JSON inside
            import json
            candidate = json.loads(decoded)
            # If "answer" can be derived, return it
            # For now return candidate as 'answer' placeholder
            return {"answer": candidate}
        except Exception:
            pass

    # fallback: ask Gemini to read the HTML and propose an answer payload
    prompt = f"""You are given this HTML/text (truncated if large). Identify the quiz submit JSON payload needed based on page instructions. Page content:\n\n{extracted.get('body_text','')[:4000]}"""
    gemini_out = await call_gemini(prompt)
    # parse gemini_out if it's JSON
    try:
        import json
        parsed = json.loads(gemini_out)
        return parsed
    except Exception:
        # if Gemini returns plain text, encapsulate it:
        return {"answer_text": gemini_out}

@app.post("/endpoint")
async def quiz_endpoint(request: Request):
    start = time.time()
    try:
        payload_json = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        payload = QuizPayload(**payload_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    # verify secret (example: simple equality to env secret)
    if APP_SECRET is None:
        raise HTTPException(status_code=500, detail="Server misconfigured: APP_SECRET not set")
    if payload.secret != APP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    # overall deadline enforcement
    MAX_TOTAL_S = 170.0  # leave margin vs 180s
    elapsed = time.time() - start
    time_remaining = int(max(5, MAX_TOTAL_S - elapsed))

    # fetch and extract
    extracted = await fetch_quiz_page_and_extract(payload.url, timeout_s=min(60, time_remaining))
    elapsed = time.time() - start
    time_remaining = int(max(5, MAX_TOTAL_S - elapsed))

    # solve
    answer_payload = await parse_and_solve(extracted, payload, time_remaining)

    # find submit URL inside extracted content (best-effort)
    submit_url = None
    # attempt: look for "https://.../submit" pattern in raw text
    import re
    body = extracted.get("body_text","")
    m = re.search(r"https?://[^\s'\"<>]+/submit[^\s'\"<>]*", body)
    if m:
        submit_url = m.group(0)

    if not submit_url:
        # if page provided explicit url in JSON
        wdata = extracted.get("window_quiz_data") or {}
        submit_url = wdata.get("submit_url") or wdata.get("url") or payload.url

    # post answer
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(submit_url, json={**payload_json, **answer_payload}, headers=headers)
        resp.raise_for_status()
        result_json = resp.json()

    return {"ok": True, "submitted_to": submit_url, "result": result_json}

# uvicorn command to run:
# uvicorn app:app --host 0.0.0.0 --port 8000
