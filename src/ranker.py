import os
import json
import docx
import PyPDF2
import pandas as pd
from datetime import datetime
from fireworks.client import Fireworks
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np
import src.config as config

# ----------------------------
# Fireworks Setup - USING LLAMA FOR RELIABILITY
# ----------------------------
fw = Fireworks(api_key=config.FIREWORKS_API_KEY)

# Use Llama 3.3 70B - Much better for structured output than Qwen thinking model
LLM_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"

EMBED_MODEL = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
sbert_model = SentenceTransformer(EMBED_MODEL)

# Qdrant client
qdrant = QdrantClient("http://localhost:6333")
COLLECTION_NAME = "cv_ranking"

# ----------------------------
# CV Parsing Functions (unchanged)
# ----------------------------
def extract_text_from_pdf(file_path):
    try:
        text = ""
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print(f"❌ PDF parse error {file_path}: {e}")
        return ""

def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        print(f"❌ DOCX parse error {file_path}: {e}")
        return ""

def extract_text(file_path):
    if not file_path or not os.path.exists(file_path):
        return ""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    return ""

def load_cvs_from_dataframe(df):
    candidates = []
    if isinstance(df, list):
        df = pd.DataFrame(df)

    for idx, row in df.iterrows():
        cv_path = row.get("local_cv_path")
        cv_link = row.get("CV", "")
        name = row.get("Full Name") or row.get("full name") or row.get("fullname") or f"Candidate {idx+1}"

        text = ""
        if cv_path and os.path.exists(cv_path):
            try:
                text = extract_text(cv_path)
            except Exception:
                text = ""

        candidates.append({
            "filename": os.path.basename(cv_path) if cv_path else f"candidate_{idx+1}.pdf",
            "text": text,
            "name": name,
            "cv_link": cv_link
        })

    return candidates

# ----------------------------
# Ranking with Fireworks (Llama 3.3)
# ----------------------------
def rank_with_gemini(cvs, job_description, api_key=None, batch_size=1):
    """
    Rank CVs using Fireworks AI API with Llama 3.3 70B.
    Optimized for medical/healthcare recruitment.
    """
    results = []
    
    if not api_key:
        print("⚠️ No Fireworks API key found.")
        for c in cvs:
            results.append({
                "filename": c["filename"],
                "name": c["name"],
                "score": 0,
                "reasoning": "API key missing - cannot analyze",
                "cv_link": c.get("cv_link", "")
            })
        return results

    # Process CVs one at a time
    for i, cv in enumerate(cvs):
        try:
            print(f"🔥 Analyzing CV {i+1}/{len(cvs)}: {cv['name']}")
            
            # Medical-specific prompt
            prompt = f"""You are an expert medical recruiter specializing in healthcare hiring. Analyze this doctor's CV against the job requirements.

JOB REQUIREMENTS:
{job_description[:1500]}

CANDIDATE CV:
Name: {cv['name']}
{cv['text'][:2000]}

EVALUATION CRITERIA for Medical Professionals:
- Medical qualifications, degrees, and certifications
- Specialization match (e.g., Cardiology, Pediatrics, Surgery, etc.)
- Years of clinical experience and practice settings
- Specific procedures, treatments, or techniques mentioned
- Hospital affiliations and training programs
- Languages spoken (important for patient communication)
- Publications, research, or academic contributions
- Board certifications and licenses

SCORING SCALE:
- 90-100: Excellent match - specialization perfect, extensive relevant experience
- 75-89: Strong match - right specialization, good experience level
- 60-74: Good match - relevant medical background, some experience
- 40-59: Moderate match - general medical background, limited specialty match
- 20-39: Weak match - different specialization or insufficient experience
- 0-19: Poor match - unrelated medical field or entry-level when senior needed

Analyze the medical qualifications and specialization match carefully.

Respond with ONLY this JSON format:
{{"score": 85, "reasoning": "Brief explanation focusing on medical qualifications and specialty match"}}

JSON only:"""

            response = fw.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert medical recruiter with deep knowledge of healthcare qualifications and specializations. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=400
            )

            raw_text = response.choices[0].message.content.strip()
            
            # Parse JSON
            parsed = None
            try:
                import re
                # Clean markdown if present
                clean_text = re.sub(r'```(?:json)?\s*', '', raw_text)
                clean_text = re.sub(r'```', '', clean_text).strip()
                
                # Try direct parse first
                parsed = json.loads(clean_text)
                
            except json.JSONDecodeError:
                # Extract JSON with regex
                import re
                json_match = re.search(r'\{[^{}]*"score"\s*:\s*\d+[^{}]*"reasoning"\s*:[^{}]*\}', raw_text, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                    except:
                        pass
            
            # Process result
            if parsed and "score" in parsed and "reasoning" in parsed:
                score = int(parsed["score"])
                reasoning = parsed["reasoning"].strip()
                
                # Validate score
                score = max(0, min(100, score))
                
                results.append({
                    "filename": cv["filename"],
                    "name": cv["name"],
                    "score": score,
                    "reasoning": reasoning,
                    "cv_link": cv.get("cv_link", "")
                })
                print(f"   ✅ Score: {score}/100")
                print(f"   📋 {reasoning[:80]}...")
                
            else:
                # If parsing completely fails
                print(f"   ⚠️ JSON parsing failed")
                print(f"   Raw response: {raw_text[:200]}")
                results.append({
                    "filename": cv["filename"],
                    "name": cv["name"],
                    "score": 0,
                    "reasoning": "Unable to analyze CV - please review manually",
                    "cv_link": cv.get("cv_link", "")
                })

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            results.append({
                "filename": cv["filename"],
                "name": cv["name"],
                "score": 0,
                "reasoning": f"Processing error: {str(e)[:80]}",
                "cv_link": cv.get("cv_link", "")
            })

    return results

def analyze_with_keywords(cv_text, job_description):
    """
    REMOVED - No keyword fallback for medical CVs.
    Medical qualifications require proper AI analysis, not keyword matching.
    """
    return 0

# ----------------------------
# Embedding-based ranking (unchanged)
# ----------------------------
def rank_with_embeddings(cvs, job_description, top_k=5):
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )

    qdrant.delete_collection(COLLECTION_NAME)
    qdrant.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )

    vectors = []
    for idx, c in enumerate(cvs):
        emb = sbert_model.encode(c["text"] or "")
        vectors.append(models.PointStruct(
            id=idx,
            vector=emb.tolist(),
            payload={"filename": c["filename"], "name": c["name"], "cv_link": c["cv_link"], "text": c["text"]}
        ))
    qdrant.upsert(collection_name=COLLECTION_NAME, points=vectors)

    job_emb = sbert_model.encode(job_description).tolist()
    search_results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=job_emb,
        limit=top_k
    )

    results = []
    for r in search_results:
        payload = r.payload
        score = round(r.score * 100, 2)
        results.append({
            "filename": payload.get("filename", "Unknown"),
            "name": payload.get("name", "Unknown"),
            "score": score,
            "reasoning": f"Semantic similarity: {score}%",
            "cv_link": payload.get("cv_link", "")
        })

    return results

# ----------------------------
# Save to Excel (unchanged)
# ----------------------------
def save_results_to_excel(results_list, job_description=None, output_dir=".", output_path=None):
    df_out = pd.DataFrame(results_list)

    required_cols = ["name", "score", "status", "reasoning", "cv_link"]
    for col in required_cols:
        if col not in df_out.columns:
            df_out[col] = ""

    df_out["status"] = df_out["score"].apply(lambda x: "Match" if float(x) >= 60 else "Not Match")
    df_out = df_out[required_cols].sort_values(by="score", ascending=False)

    wb = Workbook()
    ws = wb.active
    ws.title = "Ranked Candidates"

    headers = list(df_out.columns)
    ws.append(headers)
    for _, row in df_out.iterrows():
        ws.append([row.get(h, "") for h in headers])

    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)), start=2):
        status = ws[f"C{i}"].value
        try:
            score = float(ws[f"B{i}"].value)
        except:
            score = 0

        if status == "Match":
            fill = PatternFill(start_color="C6EFCE", fill_type="solid")
        elif score >= 40:
            fill = PatternFill(start_color="FFEB9C", fill_type="solid")
        else:
            fill = PatternFill(start_color="F2DCDB", fill_type="solid")

        for cell in row:
            cell.fill = fill

        cv_link = ws[f"E{i}"].value
        if cv_link and str(cv_link).startswith("http"):
            ws[f"E{i}"].hyperlink = cv_link
            ws[f"E{i}"].style = "Hyperlink"

    ws_summary = wb.create_sheet("Summary")
    avg_score = df_out["score"].astype(float).mean() if not df_out.empty else 0
    top_candidate = df_out.iloc[0] if not df_out.empty else None
    ws_summary["A1"], ws_summary["B1"] = "Average Score", avg_score
    if top_candidate is not None:
        ws_summary["A2"], ws_summary["B2"] = "Top Candidate", top_candidate.get("name", "Unknown")
        ws_summary["A3"], ws_summary["B3"] = "Top Score", top_candidate.get("score", 0)
        ws_summary["A4"], ws_summary["B4"] = "Top CV Link", top_candidate.get("cv_link", "")

    if output_path:
        final_path = output_path
    else:
        safe_job_desc = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in (job_description or "Job"))
        output_filename = f"{safe_job_desc.strip().replace(' ', '_')}_Ranked_Candidates.xlsx"
        final_path = os.path.join(output_dir, output_filename)

    wb.save(final_path)
    print(f"✅ Results saved to {final_path}")
    return df_out, final_path