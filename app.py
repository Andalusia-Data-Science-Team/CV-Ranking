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
from src.ranker import *
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
               style={"color": "#B68648"}),  # warm golden-brown
            html.P("Alandalusia Health Egypt",
                   className="lead mb-0 opacity-75",
                   style={"color": "#B68648"})  # warm golden-brown
        ], style={
            "backgroundColor": "#F2F2F2",  # light gray
            "backgroundImage": "url('/assets/paper-texture.png')",  # subtle texture
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
                create_upload_component("jd-bulk", "Upload Job Description", "(.txt)", "fa-file-text"),
                html.Div(id="jd-preview", className="mt-3")
            ], md=6)
        ], className="mb-4"),

        # Second row: The progress status card
        dbc.Row([
            dbc.Col([
                create_progress_card()
            ], md=12)  # Use the full width for the status card
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
            ], md=12) # Use the full width for the results
        ])
    ]
def create_single_tab():
    return [
        dbc.Row([
            dbc.Col([
                create_upload_component("cv-single", "Upload CV", "(.pdf, .docx)", "fa-file-pdf"),
                html.Div(id="cv-preview", className="mt-3")
            ], md=6),
            dbc.Col([
                create_upload_component("jd-single", "Upload Job Description", "(.txt)", "fa-file-text"),
                html.Div(id="jd-single-preview", className="mt-3")
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
        
        # This is the simplified confirmation message
        preview = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✓ {filename} uploaded successfully ({len(df)} rows)"
        ], color="success", className="mt-3")
        
        return preview, df.to_dict('records')
        
    except Exception as e:
        return dbc.Alert(f"Error reading file: {str(e)}", color="danger"), None

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
        jd_text = decoded.decode('utf-8')
        
        # This is the simplified confirmation message
        preview = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✓ {filename} uploaded successfully"
        ], color="success", className="mt-3")
        
        return preview, jd_text
        
    except Exception as e:
        return dbc.Alert(f"Error reading job description: {str(e)}", color="danger"), None

# Process Button Callback
@app.callback(
    [Output('progress-content', 'children'),
     Output('results-content', 'children'),
     Output('processing-results', 'data')],
    Input('process-btn', 'n_clicks'),
    [State('leads-data', 'data'),
     State('jd-text', 'data')]
)
def process_bulk_analysis(n_clicks, leads_data, jd_text):
    if n_clicks is None or leads_data is None or jd_text is None:
        return "Ready to process files", "", None
    
    try:
        # Convert back to DataFrame
        leads_df = pd.DataFrame(leads_data)
        
        # Progress indicators
        progress_steps = [
            dbc.Alert([
                html.I(className="fas fa-download me-2"),
                "Step 1/3: Downloading CVs from links..."
            ], color="info"),
            dcc.Interval(id="download-interval", interval=1000, n_intervals=0, max_intervals=1)
        ]
        
        # Here you would call your actual processing functions
        # leads_df = download_cvs_from_leads(leads_df, output_dir=dl_folder)
        # cvs = load_cvs_from_dataframe(leads_df)
        
        # Mock results for demonstration
        results = []
        for index, row in leads_df.iterrows():
            score = 85 - index * 5 # Replace with actual ranking logic
            results.append({
                "Full Name": row.get("Full Name"), # Use .get() to prevent errors if column is missing
                "score": score,
                "status": "Match" if score >= 60 else "No-Match",
                "reasoning": f"Strong match with a score of {score}",
                "CV": row.get("CV") # Use .get()
            })
            
        # Create results visualization
        results_df = pd.DataFrame(results)
        
        # Match vs No Match pie chart
        status_counts = results_df['status'].value_counts()
        fig_pie = px.pie(values=status_counts.values, names=status_counts.index, 
                         title="Match Rate", color_discrete_sequence=['#667eea', '#f093fb'])
        fig_pie.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font={'color': '#2c3e50'}
        )
        
        results_content = [
            # Metrics Row (only total CVs and matches found)
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3(f"{len(results)}", className="text-white mb-1"),
                            html.P("Total CVs Processed", className="mb-0 opacity-75")
                        ])
                    ], style={**custom_styles['metric_card'], 'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'})
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3(f"{len(results_df[results_df['status']=='Match'])}", className="text-white mb-1"),
                            html.P("Matches Found", className="mb-0 opacity-75")
                        ])
                    ], style={**custom_styles['metric_card'], 'background': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'})
                ], md=6),
            ], className="mb-4"),
            
            # Pie Chart Row
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=fig_pie, style={'height': '400px'})
                ], md=12)
            ], className="mb-4"),
            
            # Results Table
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-table me-2"),
                    "Detailed Results"
                ]),
                dbc.CardBody([
                    dash_table.DataTable(
                        data=results_df.to_dict('records'),
                        columns=[
                            {"name": "Candidate", "id": "Full Name"}, # ID changed to match data key
                            {"name": "Score", "id": "score", "type": "numeric"},
                            {"name": "Status", "id": "status"},
                            {"name": "Reasoning", "id": "reasoning"},
                            {"name": "CV Link", "id": "CV"} # New column for the CV link
                        ],
                        sort_action="native",
                        style_cell={'textAlign': 'left', 'padding': '12px'},
                        style_header={'backgroundColor': '#667eea', 'color': 'white', 'fontWeight': 'bold'},
                        style_data_conditional=[
                            {
                                'if': {'filter_query': '{status} = Match'},
                                'backgroundColor': '#d4edda',
                                'color': 'black',
                            },
                            {
                                'if': {'filter_query': '{status} = No-Match'},
                                'backgroundColor': '#f8d7da',
                                'color': 'black',
                            }
                        ],
                        page_size=10
                    )
                ])
            ], style=custom_styles['card'])
        ]
        
        progress_complete = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            "✅ Processing completed successfully!"
        ], color="success")
        
        return progress_complete, results_content, results
        
    except Exception as e:
        error_msg = dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            f"Error during processing: {str(e)}"
        ], color="danger")
        return error_msg, "", None

# Single CV Analysis Callbacks
@app.callback(
    Output('cv-preview', 'children'),
    Input('upload-cv-single', 'contents'),
    State('upload-cv-single', 'filename')
)
def update_cv_preview(contents, filename):
    if contents is None:
        return ""
    
    preview = dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-check-circle text-success me-2"),
            f"✓ {filename} uploaded"
        ]),
        dbc.CardBody([
            html.P("CV uploaded successfully. Ready for analysis.", 
                className="text-muted mb-0")
        ])
    ], className="mt-3")
    
    return preview

@app.callback(
    Output('jd-single-preview', 'children'),
    Input('upload-jd-single', 'contents'),
    State('upload-jd-single', 'filename')
)
def update_jd_single_preview(contents, filename):
    if contents is None:
        return ""
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        jd_text = decoded.decode('utf-8')
        
        preview = dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-check-circle text-success me-2"),
                f"✓ {filename} uploaded"
            ]),
            dbc.CardBody([
                html.P(jd_text[:300] + "..." if len(jd_text) > 300 else jd_text,
                    style={'fontSize': '14px', 'lineHeight': '1.5'})
            ])
        ], className="mt-3")
        
        return preview
        
    except Exception as e:
        return dbc.Alert(f"Error reading job description: {str(e)}", color="danger")

@app.callback(
    Output('single-results', 'children'),
    Input('analyze-btn', 'n_clicks'),
    [State('upload-cv-single', 'contents'),
     State('upload-jd-single', 'contents')]
)
def analyze_single_cv(n_clicks, cv_contents, jd_contents):
    if n_clicks is None or cv_contents is None or jd_contents is None:
        return ""
    
    # Mock analysis result
    score = 78
    status = "Match" if score >= 60 else "No Match"
    reasoning = "Strong technical background with 85% keyword match. Relevant experience in required technologies."
    
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
                            "✅ Match" if status == "Match" else "❌ No Match",
                        ], className="text-success" if status == "Match" else "text-danger"),
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)