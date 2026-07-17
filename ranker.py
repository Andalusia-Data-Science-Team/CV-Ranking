import os, re, json, tempfile
import docx
import PyPDF2
import requests
import config


def extract_text(filename: str, data: bytes) -> str:
    """Extract text from pdf/docx/txt bytes."""
    ext = os.path.splitext(filename)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        if ext == ".pdf":
            text = ""
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                    return ""
                for page in reader.pages:
                    text += page.extract_text() or ""
            return text.strip()
        elif ext in (".docx", ".doc"):
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext == ".txt":
            return data.decode("utf-8", errors="ignore").strip()
        return ""
    finally:
        os.remove(path)


def rank_cv(cv_text: str, jd_text: str) -> dict:
    """Send CV + job description to OpenRouter LLM and return {score, reasoning}."""
    if not cv_text.strip():
        return {"score": 0, "reasoning": "Could not extract text from CV."}

    prompt = f"""You are an expert recruiter. Score this candidate against the job requirements.

JOB REQUIREMENTS:
{jd_text[:1500]}

CANDIDATE CV:
{cv_text[:2000]}

Score 0-100 based on qualifications, experience, and skills match.
Respond with ONLY this JSON: {{"score": 85, "reasoning": "short explanation"}}"""

    response = requests.post(
        config.OPENROUTER_BASE_URL,
        headers={
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": "You are an expert recruiter. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 300,
        },
    )

    if response.status_code != 200:
        return {"score": 0, "reasoning": f"API error: {response.status_code} - {response.text}"}

    try:
        raw = response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        return {"score": 0, "reasoning": f"API response error: {e} - {response.text}"}
    raw = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*"score"\s*:\s*\d+.*\}', raw, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else None

    if not parsed or "score" not in parsed:
        return {"score": 0, "reasoning": "Could not parse model response."}

    score = max(0, min(100, int(parsed["score"])))
    return {"score": score, "reasoning": parsed.get("reasoning", "").strip()}
