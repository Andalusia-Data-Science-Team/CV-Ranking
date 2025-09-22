import os
import json
import docx
import PyPDF2
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from openpyxl import Workbook
from openpyxl.styles import PatternFill

import src.config as config # uses GEMINI_API_KEY from config.py

# ----------------------------
# Gemini Setup
# ----------------------------
genai.configure(api_key=config.GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.0-flash-exp"

# ----------------------------
# CV Parsing (Moved to the top)
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
# Prompt Builder
# ----------------------------
def build_prompt(job_description, batch):
    return f"""You are an expert HR recruiter.
Analyze these CVs against the job description and provide accurate scoring.

⚠️ CRITICAL INSTRUCTIONS ⚠️
- Respond with ONLY valid JSON.
- Do not include explanations, markdown, or text outside JSON.
- JSON must be a valid array of objects.

Job Description:
{job_description[:1500]}

Scoring Criteria:
90-100 = Perfect match
80-89  = Strong match
60-79  = Good match
40-59  = Moderate match
20-39  = Weak match
0-19   = No match

CVs to analyze:
{json.dumps([{"filename": c["filename"], "text": c["text"][:1000]} for c in batch], indent=2)}

Expected JSON format:
[
  {{"filename": "cv1.pdf", "score": 85, "reasoning": "Matched required qualifications"}},
  {{"filename": "cv2.pdf", "score": 20, "reasoning": "Unrelated background"}}
]
"""

# ----------------------------
# Ranking Functions
# ----------------------------
def rank_with_gemini(cvs, job_description, api_key=None, batch_size=3):
    results = []
    if not api_key:
        print("⚠️ No Gemini API key found, using keyword-based scoring.")
        for c in cvs:
            score = 0
            reasoning = "Using fallback scoring due to missing API key."
            if "python" in c["text"].lower() and "data science" in c["text"].lower():
                score = 80
                reasoning = "Keyword match: Python and Data Science."
            results.append({
                "filename": c["filename"],
                "name": c["name"],
                "score": score,
                "reasoning": reasoning,
                "cv_link": c.get("cv_link", "")
            })
        return results

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    for i in range(0, len(cvs), batch_size):
        batch = cvs[i:i+batch_size]
        prompt = build_prompt(job_description, batch)

        try:
            response = model.generate_content(prompt)

            parsed = []
            try:
                import re
                raw_text = response.text.strip()
                match = re.search(r'\[.*\]', raw_text, re.S)
                if match:
                    raw_text = match.group(0)
                parsed = json.loads(raw_text)
            except Exception as e:
                print("⚠️ Gemini response was not valid JSON:", e)
                parsed = []

            for r in parsed:
                cand = next((c for c in batch if c["filename"] == r.get("filename")), None)
                results.append({
                    "filename": r.get("filename", "Unknown"),
                    "name": cand["name"] if cand else r.get("filename"),
                    "score": int(r.get("score", 0)),
                    "reasoning": r.get("reasoning", ""),
                    "cv_link": cand["cv_link"] if cand and "cv_link" in cand else ""
                })

            if not parsed:
                for c in batch:
                    results.append({
                        "filename": c["filename"],
                        "name": c["name"],
                        "score": 0,
                        "reasoning": "Gemini failed to return valid JSON",
                        "cv_link": c.get("cv_link", "")
                    })

        except Exception as e:
            for c in batch:
                results.append({
                    "filename": c["filename"],
                    "name": c["name"],
                    "score": 0,
                    "reasoning": f"Error during analysis: {e}",
                    "cv_link": c.get("cv_link", "")
                })

    return results



def save_results_to_excel(results_list, job_description=None, output_dir=".", output_path=None):
    df_out = pd.DataFrame(results_list)

    required_cols = ["name", "score", "status", "reasoning", "cv_link"]
    for col in required_cols:
        if col not in df_out.columns:
            df_out[col] = ""

    df_out["status"] = df_out["score"].apply(lambda x: "Match" if int(x) >= 60 else "Not Match")
    df_out = df_out[required_cols].sort_values(by="score", ascending=False)

    wb = Workbook()
    ws = wb.active
    ws.title = "Ranked Candidates"

    headers = list(df_out.columns)
    ws.append(headers)
    for _, row in df_out.iterrows():
        ws.append([row.get(h, "") for h in headers])

    # Apply coloring
    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)), start=2):
        status = ws[f"C{i}"].value
        try:
            score = int(ws[f"B{i}"].value)
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

        # Add CV hyperlink
        cv_link = ws[f"E{i}"].value
        if cv_link and str(cv_link).startswith("http"):
            ws[f"E{i}"].hyperlink = cv_link
            ws[f"E{i}"].style = "Hyperlink"

    # Summary
    ws_summary = wb.create_sheet("Summary")
    avg_score = df_out["score"].mean() if not df_out.empty else 0
    top_candidate = df_out.iloc[0] if not df_out.empty else None
    ws_summary["A1"], ws_summary["B1"] = "Average Score", avg_score
    if top_candidate is not None:
        ws_summary["A2"], ws_summary["B2"] = "Top Candidate", top_candidate.get("name", "Unknown")
        ws_summary["A3"], ws_summary["B3"] = "Top Score", top_candidate.get("score", 0)
        ws_summary["A4"], ws_summary["B4"] = "Top Candidate CV Link", top_candidate.get("cv_link", "")

    # Decide output filename
    if output_path:
        final_path = output_path
    else:
        safe_job_desc = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in (job_description or "Job"))
        output_filename = f"{safe_job_desc.strip().replace(' ', '_')}_Ranked_Candidates.xlsx"
        final_path = os.path.join(output_dir, output_filename)

    wb.save(final_path)
    print(f"✅ Results saved to {final_path}")
    return df_out, final_path
