# app.py
import streamlit as st
import io
import time
import pandas as pd
import os
import importlib

from src.downloader import download_cvs_from_leads
from src.ranker import *
import src.config as config

st.set_page_config(page_title="Recruiter CV Matcher", layout="wide")
st.title("Recruiter CV Matcher")

tab1, tab2 = st.tabs(["📊 Bulk Ranking (Excel Leads)", "📄 Single CV Ranking"])

# ===========================
# TAB 1 — BULK RANKING
# ===========================
with tab1:
    st.markdown("Upload the leads Excel file and a job description `.txt`")

    uploaded_leads = st.file_uploader("Upload leads (.xlsx or .csv)", type=["xlsx", "csv"])
    uploaded_jd = st.file_uploader("Upload job description (.txt)", type=["txt"], key="jd_bulk")

    if uploaded_leads:
        st.info("Leads file uploaded. Previewing first rows...")
        try:
            uploaded_leads.seek(0)
            file_extension = os.path.splitext(uploaded_leads.name)[1].lower()
            if file_extension == ".xlsx":
                tmp_df = pd.read_excel(uploaded_leads)
            elif file_extension == ".csv":
                tmp_df = pd.read_csv(uploaded_leads)
            else:
                st.error("Unsupported file format!")
                st.stop()
            st.dataframe(tmp_df.head(5))
        except Exception as e:
            st.error("Failed to read uploaded leads file: " + str(e))
            st.stop()

    if uploaded_jd:
        try:
            jd_text = uploaded_jd.read().decode("utf-8")
            st.text_area("Job description preview", jd_text[:4000], height=200)
        except Exception as e:
            st.error("Failed to read job description: " + str(e))
            jd_text = None
    else:
        jd_text = None

    if st.button("Process leads and rank"):
        if not uploaded_leads or not uploaded_jd:
            st.warning("Please upload both a leads file and a job description file.")
            st.stop()

        t0 = time.time()
        st.info("Step 1 — Downloading CVs from links (this may take a while)")

        ts = int(time.time())
        dl_folder = f"downloaded_CVs_{ts}"
        try:
            uploaded_leads.seek(0)
            leads_df = download_cvs_from_leads(uploaded_leads, output_dir=dl_folder)
        except Exception as e:
            st.error(f"Failed during download step: {e}")
            st.stop()

        st.success("CV download finished.")
        st.write(leads_df[["cv_url", "local_cv_path"]].head(10))

        st.info("Step 2 — Building CV objects and running ranking")
        cvs = load_cvs_from_dataframe(leads_df)
        st.write(f"Prepared {len(cvs)} CVs for ranking (skipping rows without downloaded CV).")

        # Always try to get API key from config
        gem_key = None
        try:
            importlib.reload(config)
            gem_key = getattr(config, "GEMINI_API_KEY", None)
            if not gem_key or "YOUR_API_KEY_HERE" in gem_key:
                st.warning("GEMINI_API_KEY not found or is a placeholder in config.py - will use fallback keyword scoring.")
                gem_key = None
        except Exception:
            st.warning("config.py not found or invalid - will use fallback keyword scoring.")
            gem_key = None

        with st.spinner("Running ranking..."):
            results = rank_with_gemini(cvs, jd_text, api_key=gem_key)

        st.success("Ranking completed.")
        st.write("Sample top results (unsorted):")
        st.dataframe(pd.DataFrame(results).head(10))

        st.info("Step 3 — Creating results Excel")
        jd_base = os.path.splitext(uploaded_jd.name)[0]
        out_filename = f"matched_results_{jd_base}.xlsx"

        results_df, _ = save_results_to_excel(results, job_description=jd_text, output_path=out_filename)

        st.success(f"Results saved: {out_filename} (download below)")
        st.dataframe(results_df.head(20))

        with open(out_filename, "rb") as f:
            st.download_button("⬇️ Download results Excel", data=f.read(), file_name=out_filename,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.write(f"Total time: {time.time() - t0:.1f}s")

# ===========================
# TAB 2 — SINGLE CV RANKING
# ===========================
with tab2:
    st.markdown("Upload a **single CV (PDF/DOCX)** and a **job description (.txt)** to get an immediate score.")

    uploaded_cv = st.file_uploader("Upload CV (.pdf or .docx)", type=["pdf", "docx"])
    uploaded_jd_single = st.file_uploader("Upload job description (.txt)", type=["txt"], key="jd_single")

    if uploaded_jd_single:
        try:
            jd_single_text = uploaded_jd_single.read().decode("utf-8")
            st.text_area("Job description preview", jd_single_text[:4000], height=200, key="jd_single_area")
        except Exception as e:
            st.error("Failed to read job description: " + str(e))
            jd_single_text = None
    else:
        jd_single_text = None

    if st.button("Rank this CV"):
        if not uploaded_cv or not uploaded_jd_single:
            st.warning("Please upload both a CV and a job description file.")
            st.stop()

        # Save CV temporarily
        tmp_cv_path = f"temp_{uploaded_cv.name}"
        with open(tmp_cv_path, "wb") as f:
            f.write(uploaded_cv.read())

        cv_text = extract_text(tmp_cv_path)
        candidate = {"filename": uploaded_cv.name, "text": cv_text, "name": uploaded_cv.name, "cv_link": ""}

        # Always try to get API key
        gem_key = None
        try:
            importlib.reload(config)
            gem_key = getattr(config, "GEMINI_API_KEY", None)
            if not gem_key or "YOUR_API_KEY_HERE" in gem_key:
                st.warning("GEMINI_API_KEY not found or is a placeholder - fallback keyword scoring.")
                gem_key = None
        except Exception:
            st.warning("config.py not found or invalid - fallback keyword scoring.")
            gem_key = None

        with st.spinner("Analyzing CV..."):
            results = rank_with_gemini([candidate], jd_single_text, api_key=gem_key)

        if results:
            result = results[0]
            score = result["score"]
            status = "Match" if score >= 60 else "Not Match"
            reasoning = result["reasoning"]

            st.subheader("Result")
            st.write(f"**Score:** {score}")
            st.write(f"**Status:** {'✅ Match' if status == 'Match' else '❌ Not Match'}")
            st.write(f"**Reasoning:** {reasoning}")
        else:
            st.error("No result returned for this CV.")
