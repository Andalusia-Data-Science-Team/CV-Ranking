from flask import Flask, request, render_template_string
from ranker import extract_text, rank_cv

app = Flask(__name__)

PAGE = """
<!doctype html>
<html>
<head>
<title>CV Ranker</title>
<style>
  :root { --accent: #4f46e5; --bg: #f5f6fa; --card: #ffffff; --text: #1f2430; --muted: #6b7280; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 40px 20px;
  }
  .wrap { max-width: 640px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: var(--muted); margin-top: 0; margin-bottom: 24px; }
  .card {
    background: var(--card); border-radius: 14px; padding: 28px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06); margin-bottom: 24px;
  }
  label { display: block; font-weight: 600; margin-bottom: 6px; font-size: 0.9rem; }
  .hint { color: var(--muted); font-size: 0.8rem; margin: 0 0 6px; }
  .field { margin-bottom: 20px; }
  input[type=file] {
    width: 100%; padding: 10px; border: 1px dashed #c7cbe0; border-radius: 8px;
    background: #fafbff; cursor: pointer;
  }
  textarea {
    width: 100%; padding: 12px; border: 1px solid #dfe1ea; border-radius: 8px;
    font-family: inherit; font-size: 0.95rem; resize: vertical;
  }
  button {
    background: var(--accent); color: #fff; border: none; padding: 12px 24px;
    border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer;
    width: 100%; transition: background 0.15s;
  }
  button:hover { background: #4338ca; }

  .result-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
  .score-circle {
    width: 72px; height: 72px; border-radius: 50%; display: flex;
    align-items: center; justify-content: center; font-weight: 700; font-size: 1.2rem;
    color: #fff; flex-shrink: 0;
  }
  .badge {
    display: inline-block; padding: 4px 12px; border-radius: 999px;
    font-size: 0.8rem; font-weight: 700; letter-spacing: 0.02em;
  }
  .match { background: #dcfce7; color: #15803d; }
  .no-match { background: #fee2e2; color: #b91c1c; }
  .bar-track { background: #eef0f6; border-radius: 999px; height: 10px; overflow: hidden; margin: 14px 0; }
  .bar-fill { height: 100%; border-radius: 999px; transition: width 0.4s ease; }
  .reasoning { color: var(--text); line-height: 1.5; margin-top: 12px; }
  .reasoning-label { font-weight: 600; font-size: 0.85rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
</style>
</head>
<body>
<div class="wrap">
  <h1>📄 CV Ranker</h1>
  <p class="subtitle">Upload a CV and a job description to get an instant AI match score.</p>

  <div class="card">
    <form method=post enctype=multipart/form-data>
      <div class="field">
        <label>CV file</label>
        <p class="hint">PDF, DOCX or TXT</p>
        <input type=file name=cv accept=".pdf,.docx,.doc,.txt" required>
      </div>
      <div class="field">
        <label>Job Description file</label>
        <p class="hint">PDF, DOCX or TXT</p>
        <input type=file name=jd accept=".pdf,.docx,.doc,.txt" required>
      </div>
      <button type=submit>Analyze CV</button>
    </form>
  </div>

  {% if result %}
  {% set is_match = result.score >= 60 %}
  {% set color = '#16a34a' if result.score >= 75 else ('#f59e0b' if result.score >= 40 else '#dc2626') %}
  <div class="card">
    <div class="result-header">
      <div class="score-circle" style="background:{{ color }}">{{ result.score }}</div>
      <div>
        <span class="badge {{ 'match' if is_match else 'no-match' }}">
          {{ '✅ Match' if is_match else '❌ No Match' }}
        </span>
        <div class="hint" style="margin-top:6px;">Score out of 100</div>
      </div>
    </div>
    <div class="bar-track">
      <div class="bar-fill" style="width:{{ result.score }}%; background:{{ color }};"></div>
    </div>
    <div class="reasoning">
      <div class="reasoning-label">Reasoning</div>
      <p>{{ result.reasoning }}</p>
    </div>
  </div>
  {% endif %}
</div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        cv_file = request.files["cv"]
        jd_file = request.files["jd"]
        cv_text = extract_text(cv_file.filename, cv_file.read())
        jd_text = extract_text(jd_file.filename, jd_file.read())
        result = rank_cv(cv_text, jd_text)
    return render_template_string(PAGE, result=result)


if __name__ == "__main__":
    app.run(debug=True, port=8050)