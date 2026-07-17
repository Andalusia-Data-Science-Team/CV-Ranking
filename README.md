# CV Ranker

An AI-powered CV ranking application that analyzes candidate resumes against job descriptions and provides match scores with detailed reasoning.

## Features

- **Multi-format Support**: Accepts CVs and job descriptions in PDF, DOCX, and TXT formats
- **AI-Powered Analysis**: Uses DeepSeek model via OpenRouter for intelligent matching
- **Instant Scoring**: Provides 0-100 match scores with detailed reasoning
- **Modern UI**: Clean, responsive web interface with visual score indicators
- **Real-time Processing**: Fast text extraction and analysis

## Prerequisites

- Python 3.8 or higher
- pip package manager
- OpenRouter API key

## Installation

1. **Clone or navigate to the project directory**:
   ```bash
   cd "d:\Andalusia\CV-Ranker\latest version"
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   ```bash
   venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure API credentials**:
   Edit `config.py` and add your OpenRouter API key:
   ```python
   OPENROUTER_API_KEY = "your-api-key-here"
   OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
   OPENROUTER_MODEL = "deepseek/deepseek-chat"
   ```

## Usage

1. **Start the Flask application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and navigate to:
   ```
   http://localhost:8050
   ```

3. **Upload files**:
   - Select a CV file (PDF, DOCX, or TXT)
   - Select a job description file (PDF, DOCX, or TXT)
   - Click "Analyze CV"

4. **View results**:
   - Match score (0-100)
   - Visual score indicator with color coding
   - Detailed reasoning from the AI analysis

## Project Structure

```
.
├── app.py              # Flask web application and UI
├── ranker.py           # CV text extraction and ranking logic
├── config.py           # API configuration and credentials
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Configuration

### API Settings

The application uses OpenRouter's API with the DeepSeek model. Configure these settings in `config.py`:

- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `OPENROUTER_BASE_URL`: OpenRouter API endpoint
- `OPENROUTER_MODEL`: Model to use for analysis (default: deepseek/deepseek-chat)

### Scoring Thresholds

- **Match**: Score ≥ 60
- **No Match**: Score < 60

### Score Color Coding

- **Green (≥75)**: Strong match
- **Yellow (40-74)**: Moderate match
- **Red (<40)**: Weak match

## Dependencies

- **Flask**: Web framework
- **PyPDF2**: PDF text extraction
- **python-docx**: DOCX text extraction
- **requests**: HTTP client for API calls

## How It Works

1. **Text Extraction**: The `extract_text()` function extracts text from uploaded files (PDF, DOCX, or TXT)
2. **API Request**: The `rank_cv()` function sends the CV text and job description to the OpenRouter API
3. **AI Analysis**: The DeepSeek model analyzes the match and returns a JSON response with score and reasoning
4. **Result Display**: The web interface displays the score with visual indicators and detailed reasoning

## Troubleshooting

### API Errors

If you encounter API errors:
- Verify your OpenRouter API key is correct
- Check your API credits/balance
- Ensure the endpoint URL is correct

### File Upload Issues

If file uploads fail:
- Ensure files are in supported formats (PDF, DOCX, TXT)
- Check file sizes are reasonable
- Verify files are not corrupted

### Port Already in Use

If port 8050 is already in use, modify the port in `app.py`:
```python
app.run(debug=True, port=8051)  # Change to available port
```

## License

This project is part of the Andalusia Data Science Team's CV Ranking system.

## Support

For issues or questions, please contact the Andalusia Data Science Team.
