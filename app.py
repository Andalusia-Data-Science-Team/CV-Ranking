# app.py
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import io
import time
import pandas as pd
import os
import importlib
import base64
from datetime import datetime

from src.downloader import download_cvs_from_leads
from src.ranker import load_cvs_from_dataframe, rank_with_gemini, save_results_to_excel
from src.jd_extractor import extract_jd_from_bytes  # NEW IMPORT
import src.config as config

# Initialize Dash app with modern Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME], suppress_callback_exceptions=True)
app.title = "CV Matcher Pro"

# Custom CSS for modern styling
custom_styles = {
    'header': {
        'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'color': 'white',
        'padding': '2rem',
        'marginBottom': '2rem',
        'borderRadius': '0 0 20px 20px',
        'boxShadow': '0 4px 20px rgba(0,0,0,0.1)'
    },
    'card': {
        'borderRadius': '15px',
        'boxShadow': '0 8px 30px rgba(0,0,0,0.1)',
        'border': 'none',
        'background': 'white'
    },
    'upload_area': {
        'border': '2px dashed #dee2e6',
        'borderRadius': '15px',
        'textAlign': 'center',
        'padding': '2rem',
        'margin': '1rem 0',
        'transition': 'all 0.3s ease',
        'cursor': 'pointer'
    },
    'upload_area_hover': {
        'border': '2px dashed #667eea',
        'backgroundColor': '#f8f9ff'
    },
    'metric_card': {
        'textAlign': 'center',
        'padding': '1.5rem',
        'borderRadius': '15px',
        'background': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        'color': 'white',
        'marginBottom': '1rem'
    }
}

# Header Component
def create_header():
    return dbc.Container([
        html.Div([
            html.H1([
                html.I(className="fas fa-search me-3"),
                "CV Matcher"
            ], className="display-4 fw-bold mb-0", 
               style={"color": "#B68648"}),
            html.P("Alandalusia Health Egypt",
                   className="lead mb-0 opacity-75",
                   style={"color": "#B68648"})
        ], style={
            "backgroundColor": "#F2F2F2",
            "backgroundImage": "url('/assets/paper-texture.png')",
            "backgroundSize": "cover",
            "backgroundRepeat": "repeat",
            "padding": "20px",
            "textAlign": "center"
        })
    ], fluid=True, className="p-0 mb-4")


# File Upload Component
def create_upload_component(id_suffix, label, accepted_files, icon):
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className=f"fas {icon} fa-3x mb-3 text-muted"),
                html.H5(label, className="card-title"),
                html.P(f"Drag & drop or click to select {accepted_files}", 
                    className="text-muted small"),
                dcc.Upload(
                    id=f'upload-{id_suffix}',
                    children=html.Div([
                        html.A("Select File", className="btn btn-outline-primary")
                    ]),
                    style={'width': '100%', 'height': '100%', 'position': 'absolute', 'top': 0, 'left': 0, 'opacity': 0},
                    multiple=False
                )
            ], style={**custom_styles['upload_area'], 'position': 'relative'})
        ])
    ], style=custom_styles['card'], className="h-100")

# Progress Component
def create_progress_card():
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-tasks me-2"),
            "Processing Status"
        ], className="bg-light"),
        dbc.CardBody([
            html.Div(id="progress-content", children=[
                html.P("Ready to process files", className="text-muted text-center py-4")
            ])
        ])
    ], style=custom_styles['card'], id="progress-card", className="mb-4")

# Results Component
def create_results_section():
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-chart-bar me-2"),
            "Analysis Results"
        ], className="bg-light"),
        dbc.CardBody([
            dcc.Loading([
                html.Div(id="results-content")
            ], type="cube", color="#667eea")
        ])
    ], style=custom_styles['card'], id="results-section", className="mt-4")

# Main Layout
app.layout = dbc.Container([
    create_header(),
    
    # Main Content
    dbc.Tabs([
        # Tab 1: Bulk Processing
        dbc.Tab(label="📊 Bulk CV Analysis", tab_id="bulk", active_tab_style={"backgroundColor": "#667eea", "color": "white"}),
        # Tab 2: Single CV
        dbc.Tab(label="📄 Single CV Analysis", tab_id="single", active_tab_style={"backgroundColor": "#667eea", "color": "white"})
    ], id="main-tabs", active_tab="bulk", className="mb-4"),
    
    # Tab Content
    html.Div(id="tab-content"),
    
    # Hidden components for data storage
    dcc.Store(id='leads-data'),
    dcc.Store(id='jd-text'),
    dcc.Store(id='processing-results'),
    dcc.Store(id='excel-file-path'),
    dcc.Download(id='download-excel'),
    
], fluid=True, className="px-4")

# Tab Content Callback
@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "active_tab")
)
def render_tab_content(active_tab):
    if active_tab == "bulk":
        return create_bulk_tab()
    else:
        return create_single_tab()

def create_bulk_tab():
    return [
        # First row: Upload components for leads and job description
        dbc.Row([
            dbc.Col([
                create_upload_component("leads", "Upload Leads File", "(.xlsx, .csv)", "fa-file-excel"),
                html.Div(id="leads-preview", className="mt-3")
            ], md=6),
            dbc.Col([
                create_upload_component("jd-bulk", "Upload Job Description", "(.txt, .pdf, .docx)", "fa-file-text"),
                html.Div(id="jd-preview", className="mt-3")
            ], md=6)
        ], className="mb-4"),

        # Second row: The progress status card
        dbc.Row([
            dbc.Col([
                create_progress_card()
            ], md=12)
        ], className="mb-4"),
        
        # Third row: Processing controls (Start Processing Button)
        dbc.Row([
            dbc.Col([
                dbc.Button([
                    html.I(className="fas fa-rocket me-2"),
                    "Start Processing"
                ], id="process-btn", color="primary", size="lg", 
                className="w-100", style={'borderRadius': '15px'})
            ], md=6, className="mx-auto")
        ], className="mb-4"),
        
        # Fourth row: The results section
        dbc.Row([
            dbc.Col([
                create_results_section()
            ], md=12)
        ])
    ]

def create_single_tab():
    return [
        dbc.Row([
            dbc.Col([
                create_upload_component("cv-single", "Upload CV", "(.pdf, .docx)", "fa-file-pdf"),
                html.Div(id="cv-preview")
            ], md=6),
            dbc.Col([
                create_upload_component("jd-single", "Upload Job Description", "(.txt, .pdf, .docx)", "fa-file-text"),
                html.Div(id="jd-single-preview")
            ], md=6)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Button([
                    html.I(className="fas fa-search me-2"),
                    "Analyze CV"
                ], id="analyze-btn", color="success", size="lg", 
                className="w-100", style={'borderRadius': '15px'})
            ], md=6, className="mx-auto")
        ], className="mb-4"),
        
        html.Div(id="single-results")
    ]

# File Upload Callbacks
@app.callback(
    [Output('leads-preview', 'children'),
     Output('leads-data', 'data')],
    Input('upload-leads', 'contents'),
    State('upload-leads', 'filename')
)
def update_leads_preview(contents, filename):
    if contents is None:
        return "", None
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        if filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return dbc.Alert("Unsupported file format!", color="danger"), None
        
        preview = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✓ {filename} uploaded successfully ({len(df)} rows)"
        ], color="success", className="mt-3")
        
        return preview, df.to_dict('records')
        
    except Exception as e:
        return dbc.Alert(f"Error reading file: {str(e)}", color="danger"), None

# UPDATED: Job Description Upload for Bulk Tab
@app.callback(
    [Output('jd-preview', 'children'),
     Output('jd-text', 'data')],
    Input('upload-jd-bulk', 'contents'),
    State('upload-jd-bulk', 'filename')
)
def update_jd_preview(contents, filename):
    if contents is None:
        return "", None
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Extract text based on file type
        jd_text = extract_jd_from_bytes(decoded, filename)
        
        if not jd_text:
            return dbc.Alert(f"Failed to extract text from {filename}", color="danger"), None
        
        preview = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✓ {filename} uploaded successfully ({len(jd_text)} characters)"
        ], color="success", className="mt-3")
        
        return preview, jd_text
        
    except Exception as e:
        return dbc.Alert(f"Error reading job description: {str(e)}", color="danger"), None

# Process Button Callback
@app.callback(
    [Output('progress-content', 'children'),
     Output('results-content', 'children'),
     Output('processing-results', 'data'),
     Output('excel-file-path', 'data')],
    Input('process-btn', 'n_clicks'),
    [State('leads-data', 'data'),
     State('jd-text', 'data')]
)
def process_bulk_analysis(n_clicks, leads_data, jd_text):
    if n_clicks is None or leads_data is None or jd_text is None:
        return "Ready to process files", "", None, None
    
    try:
        # Convert back to DataFrame
        leads_df = pd.DataFrame(leads_data)
        
        # Create output directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"downloaded_CVs_{timestamp}"
        
        # Save DataFrame temporarily as CSV for the downloader function
        temp_csv_path = f"temp_leads_{timestamp}.csv"
        leads_df.to_csv(temp_csv_path, index=False)
        
        # REAL DOWNLOAD: Download CVs using downloader.py
        print("Starting CV download...")
        leads_df = download_cvs_from_leads(
            temp_csv_path, 
            output_dir=output_dir,
            show_progress=True
        )
        print(f"Downloaded CVs to {output_dir}")
        
        # Clean up temp file
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        
        # REAL PARSING: Load and parse CVs
        print("Loading CVs from dataframe...")
        cvs = load_cvs_from_dataframe(leads_df)
        print(f"Loaded {len(cvs)} CVs")
        
        # REAL RANKING: Use Gemini to rank CVs
        print("Starting ranking with Gemini...")
        results = rank_with_gemini(
            cvs=cvs,
            job_description=jd_text,
            api_key=config.FIREWORKS_API_KEY,
            batch_size=3
        )
        
        print(f"Ranking complete: {len(results)} results")
        
        # Save results to Excel
        results_output_dir = "results"
        os.makedirs(results_output_dir, exist_ok=True)
        
        safe_filename = f"CV_Ranking_Results_{timestamp}.xlsx"
        output_path = os.path.join(results_output_dir, safe_filename)
        
        results_df, excel_path = save_results_to_excel(
            results_list=results,
            job_description=jd_text,
            output_dir=results_output_dir,
            output_path=output_path
        )
        print(f"Results saved to {excel_path}")
        
        if len(results_df) == 0:
            error_msg = dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "No results generated. Please check your files and try again."
            ], color="warning")
            return error_msg, "", None, None
        
        # Metrics
        results_content = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3(f"{len(results_df)}", className="text-white mb-1"),
                        html.P("Total CVs Processed", className="mb-0 opacity-75")
                    ])
                ], style={**custom_styles['metric_card'], 
                          'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'})
            ], md=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3(f"{len(results_df[results_df['status']=='Match'])}", className="text-white mb-1"),
                        html.P("Matches Found", className="mb-0 opacity-75")
                    ])
                ], style={**custom_styles['metric_card'], 
                          'background': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'})
            ], md=6),
        ], className="mb-4")
        
        # Download button
        download_button = html.Div([
            dbc.Button(
                [html.I(className="fas fa-download me-2"), "Download Results"],
                id="download-results-btn",
                color="success",
                className="me-2",
                href=excel_path,
                download=os.path.basename(excel_path),
                target="_blank"
            )
        ], className="mb-3")
        
        # Results table
        results_table = dash_table.DataTable(
            id="results-table",
            columns=[{"name": col, "id": col} for col in results_df.columns],
            data=results_df.to_dict('records'),
            page_size=10,
            style_table={'overflowX': 'auto'},
            style_cell={
                'minWidth': '120px', 'maxWidth': '250px',
                'whiteSpace': 'normal',
                'textAlign': 'left'
            },
            style_header={
                'backgroundColor': '#f8f9fa',
                'fontWeight': 'bold'
            },
            style_data={
                'backgroundColor': '#ffffff'
            },
            filter_action="native",
            sort_action="native"
        )
        
        final_layout = html.Div([
            results_content,
            download_button,
            results_table
        ])
        
        progress_complete = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✅ Processing completed successfully! Results saved to {excel_path}"
        ], color="success")
        
        return progress_complete, final_layout, results_df.to_dict('records'), excel_path
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error during processing: {error_details}")
        
        error_msg = dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            html.Div([
                html.H5("Error during processing:"),
                html.P(str(e)),
                html.Hr(),
                html.Details([
                    html.Summary("Show detailed error"),
                    html.Pre(error_details, style={'fontSize': '12px', 'maxHeight': '200px', 'overflow': 'auto'})
                ])
            ])
        ], color="danger")
        return error_msg, "", None, None


# Download Excel Callback
@app.callback(
    Output('download-excel', 'data'),
    Input('download-results-btn', 'n_clicks'),
    State('excel-file-path', 'data'),
    prevent_initial_call=True
)
def download_excel_file(n_clicks, excel_path):
    if n_clicks and excel_path and os.path.exists(excel_path):
        return dcc.send_file(excel_path)
    return None

# Single CV Analysis Callbacks
@app.callback(
    Output('cv-preview', 'children'),
    Input('upload-cv-single', 'contents'),
    State('upload-cv-single', 'filename')
)
def update_cv_preview(contents, filename):
    if contents is None:
        return ""
    
    preview = dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        f"✓ {filename} uploaded"
    ], color="success", className="py-1 mb-0", style={'fontSize': '14px'})
    
    return preview

# UPDATED: Job Description Upload for Single CV Tab
@app.callback(
    [Output('jd-single-preview', 'children'),
     Output('jd-text', 'data', allow_duplicate=True)],
    Input('upload-jd-single', 'contents'),
    State('upload-jd-single', 'filename'),
    prevent_initial_call=True
)
def update_jd_single_preview(contents, filename):
    if contents is None:
        return "", None
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Extract text based on file type
        jd_text = extract_jd_from_bytes(decoded, filename)
        
        if not jd_text:
            return dbc.Alert(f"Failed to extract text from {filename}", color="danger", 
                           className="py-1 mb-0", style={'fontSize': '14px'}), None
        
        preview = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✓ {filename} uploaded ({len(jd_text)} chars)"
        ], color="success", className="py-1 mb-0", style={'fontSize': '14px'})
        
        return preview, jd_text
        
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger", 
                        className="py-1 mb-0", style={'fontSize': '14px'}), None
    
@app.callback(
    Output('single-results', 'children'),
    Input('analyze-btn', 'n_clicks'),
    [State('upload-cv-single', 'contents'),
     State('upload-cv-single', 'filename'),
     State('jd-text', 'data')]
)
def analyze_single_cv(n_clicks, cv_contents, cv_filename, jd_text):
    if n_clicks is None or cv_contents is None or jd_text is None:
        return ""
    
    try:
        # Decode CV file
        cv_content_type, cv_content_string = cv_contents.split(',')
        cv_decoded = base64.b64decode(cv_content_string)
        
        # Save temporarily
        temp_cv_path = f"temp_{cv_filename}"
        with open(temp_cv_path, 'wb') as f:
            f.write(cv_decoded)
        
        # Extract text from CV
        from src.ranker import extract_text
        cv_text = extract_text(temp_cv_path)
        
        # Create candidate object
        candidate = {
            "filename": cv_filename,
            "text": cv_text,
            "name": cv_filename.replace('.pdf', '').replace('.docx', ''),
            "cv_link": ""
        }
        
        # Rank with Gemini
        results = rank_with_gemini(
            cvs=[candidate],
            job_description=jd_text,
            api_key=config.FIREWORKS_API_KEY,
            batch_size=1
        )
        
        # Clean up temp file
        if os.path.exists(temp_cv_path):
            os.remove(temp_cv_path)
        
        if len(results) == 0:
            return dbc.Alert("Failed to analyze CV. Please try again.", color="danger")
        
        result = results[0]
        score = result['score']
        status = result.get('status', "Match" if score >= 60 else "No Match")
        reasoning = result['reasoning']
        
        # Score gauge chart
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Match Score"},
            delta = {'reference': 60},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#667eea"},
                'steps': [
                    {'range': [0, 60], 'color': "lightgray"},
                    {'range': [60, 100], 'color': "lightblue"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 60
                }
            }
        ))
        fig_gauge.update_layout(height=300, font={'color': '#2c3e50'})
        
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-user-check me-2"),
                "CV Analysis Result"
            ], className="bg-light"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=fig_gauge)
                    ], md=6),
                    dbc.Col([
                        html.Div([
                            html.H4([
                                "✅ Match" if score >= 60 else "❌ No Match",
                            ], className="text-success" if score >= 60 else "text-danger"),
                            html.Hr(),
                            html.H6("Analysis Summary:", className="fw-bold"),
                            html.P(reasoning, className="text-muted"),
                            html.Hr(),
                            dbc.Badge(f"Score: {score}/100", 
                                     color="success" if score >= 60 else "danger", 
                                     className="fs-6 p-2")
                        ], className="d-flex flex-column justify-content-center h-100")
                    ], md=6)
                ])
            ])
        ], style=custom_styles['card'], className="mt-4")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error analyzing single CV: {error_details}")
        return dbc.Alert(f"Error analyzing CV: {str(e)}", color="danger")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)