# CV-Ranker

Project Overview

CV Ranker is an AI-powered web app designed to help recruiters quickly evaluate and rank candidates based on job descriptions.
It automates the manual screening process by analyzing resumes (CVs), extracting key information, and computing a match score and reasoning using a Generative AI model (Gemini API via Fireworks).

The system supports two workflows:

Bulk Ranking: Upload a candidate export sheet (with CV links) and a job description file. The system automatically downloads all CVs and ranks them.

Single CV Ranking: Upload a single CV and job description to get a quick evaluation.

Problem Definition

Recruiters often spend hours reviewing hundreds of CVs to find candidates who best match a role’s requirements.
This project aims to automate that process using NLP and LLMs to:

Extract key information from resumes

Compare candidates’ skills and experience to the job description

Generate an interpretable match score and reasoning

Technical Details

Frontend: Dash (Plotly) with Bootstrap Components

Backend: Python, Flask (via Dash server)

LLM Integration: Gemini API (via Fireworks)

Vector Database: Qdrant (for document embeddings and semantic similarity)

File Handling: Automatic download and text extraction from uploaded or linked CVs (PDF/DOCX)

Ranking Output: Match score, reasoning summary, and candidate status (Match / No Match)

Main Features

Bulk ranking from exported candidate sheets

Single CV ranking mode

Intelligent text extraction and matching

Visual dashboards with scores and reasoning

Seamless integration with Fireworks AI APIs

 Tools & Technologies

Python 3.10+

Dash & Plotly

Dash Bootstrap Components

Qdrant

Gemini API (Fireworks)

Requests, Pandas, Base64, OS


Then open:  http://10.24.105.221:8050

 What We Deliver

A fully functional AI CV Ranking dashboard

Two workflows (Bulk & Single CV analysis)

Downloadable ranked results with match scores and reasoning

Ready-to-deploy Docker setup for production

 Future Enhancements

Add authentication and user management

Support multiple job roles in bulk mode

Integration with HR systems (ATS)

Enhanced visualization and filtering options
