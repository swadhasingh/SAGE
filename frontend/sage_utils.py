# sage_utils.py - Helper Functions and Utilities for SAGE Frontend
import streamlit as st
import requests
import qrcode
from io import BytesIO
import base64
import json
import logging
from datetime import datetime
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_custom_css():
    """Apply custom CSS styling to the Streamlit app"""
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 2rem;
        }
        .section-header {
            font-size: 1.5rem;
            font-weight: bold;
            color: #2c3e50;
            margin-top: 2rem;
            margin-bottom: 1rem;
            border-bottom: 2px solid #667eea;
            padding-bottom: 0.5rem;
        }
        .metric-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 1.5rem;
            border-radius: 0.8rem;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        .success-box {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            padding: 1.5rem;
            border-radius: 0.8rem;
            border-left: 4px solid #28a745;
            margin: 1rem 0;
            box-shadow: 0 2px 10px rgba(40, 167, 69, 0.2);
        }
        .warning-box {
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            padding: 1.5rem;
            border-radius: 0.8rem;
            border-left: 4px solid #ffc107;
            margin: 1rem 0;
            box-shadow: 0 2px 10px rgba(255, 193, 7, 0.2);
        }
        .error-box {
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            padding: 1.5rem;
            border-radius: 0.8rem;
            border-left: 4px solid #dc3545;
            margin: 1rem 0;
            box-shadow: 0 2px 10px rgba(220, 53, 69, 0.2);
        }
        .agent-status {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 0.8rem;
            text-align: center;
            margin-bottom: 1rem;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .real-time-indicator {
            background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.8rem;
            display: inline-block;
            animation: pulse 2s infinite;
            box-shadow: 0 2px 10px rgba(40, 167, 69, 0.3);
        }
        .offline-indicator {
            background: linear-gradient(90deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.8rem;
            display: inline-block;
        }
        .survey-card {
            background: white;
            padding: 1.5rem;
            border-radius: 0.8rem;
            border: 1px solid #dee2e6;
            margin-bottom: 1rem;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .survey-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        .response-card {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 0.5rem;
            border-left: 3px solid #667eea;
            margin-bottom: 0.5rem;
        }
        .qr-container {
            text-align: center;
            padding: 1rem;
            background: white;
            border-radius: 0.8rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.05); }
            100% { opacity: 1; transform: scale(1); }
        }
        .stButton > button {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 0.5rem;
            padding: 0.5rem 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .sidebar .stSelectbox > div > div {
            background-color: #f8f9fa;
        }
        .metric-container {
            background: white;
            padding: 1rem;
            border-radius: 0.5rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)


def check_backend_connection(backend_url):
    """
    Check if the Flask backend is running and responsive

    Args:
        backend_url (str): The base URL of the Flask backend

    Returns:
        bool: True if backend is accessible, False otherwise
    """
    try:
        response = requests.get(f"{backend_url}/", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Backend connection failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking backend: {e}")
        return False


def safe_request(method, url, **kwargs):
    """
    Make a safe HTTP request with error handling

    Args:
        method (str): HTTP method ('get', 'post', etc.)
        url (str): Request URL
        **kwargs: Additional arguments for requests

    Returns:
        dict or None: Response JSON if successful, None otherwise
    """
    try:
        response = getattr(requests, method.lower())(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        logger.error(f"Timeout on {method} {url}")
        return None
    except requests.exceptions.ConnectionError:
        st.error(
            "Cannot connect to backend. Please ensure the Flask server is running.")
        logger.error(f"Connection error on {method} {url}")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error: {e.response.status_code}")
        logger.error(f"HTTP error on {method} {url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Request failed: {str(e)}")
        logger.error(f"Request exception on {method} {url}: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Invalid response from server")
        logger.error(f"JSON decode error on {method} {url}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error on {method} {url}: {e}")
        return None


def generate_qr_code(url):
    """
    Generate QR code for a given URL and return as base64 image

    Args:
        url (str): URL to encode in QR code

    Returns:
        str: Base64 encoded image data URL
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        # Convert to base64 for display
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logger.error(f"QR code generation failed: {e}")
        return None


def format_timestamp(timestamp):
    """
    Format unix timestamp to readable string

    Args:
        timestamp (int): Unix timestamp

    Returns:
        str: Formatted datetime string
    """
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return "Invalid timestamp"


def display_success_message(message):
    """Display a styled success message"""
    st.markdown(f"""
    <div class="success-box">
        <h4>✅ Success</h4>
        <p>{message}</p>
    </div>
    """, unsafe_allow_html=True)


def display_warning_message(message):
    """Display a styled warning message"""
    st.markdown(f"""
    <div class="warning-box">
        <h4>⚠️ Warning</h4>
        <p>{message}</p>
    </div>
    """, unsafe_allow_html=True)


def display_error_message(message):
    """Display a styled error message"""
    st.markdown(f"""
    <div class="error-box">
        <h4>❌ Error</h4>
        <p>{message}</p>
    </div>
    """, unsafe_allow_html=True)


def get_survey_list(backend_url):
    """
    Get formatted list of surveys for selection

    Args:
        backend_url (str): Backend URL

    Returns:
        dict: Survey options mapping display name to survey_id
    """
    surveys_data = safe_request(
        'get', f"{backend_url}/recent_surveys", params={'limit': 100})
    survey_options = {}

    if surveys_data:
        for survey in surveys_data:
            survey_id = survey.get('survey_id')
            title = survey.get('structure', {}).get('title', 'Untitled Survey')
            created = format_timestamp(survey.get('created_at', 0))
            survey_options[f"{title} ({created})"] = survey_id

    return survey_options


def calculate_response_metrics(responses):
    """
    Calculate basic metrics from response data

    Args:
        responses (list): List of response objects

    Returns:
        dict: Calculated metrics
    """
    if not responses:
        return {
            'total': 0,
            'today': 0,
            'this_week': 0,
            'avg_per_day': 0
        }

    now = time.time()
    today_start = now - (now % 86400)  # Start of today
    week_start = now - (7 * 86400)    # 7 days ago

    today_count = sum(1 for r in responses if r.get(
        'timestamp', 0) >= today_start)
    week_count = sum(1 for r in responses if r.get(
        'timestamp', 0) >= week_start)

    # Calculate average responses per day over the past week
    days_with_responses = len(set(
        int(r.get('timestamp', 0) // 86400)
        for r in responses
        if r.get('timestamp', 0) >= week_start
    ))

    avg_per_day = week_count / max(days_with_responses, 1)

    return {
        'total': len(responses),
        'today': today_count,
        'this_week': week_count,
        'avg_per_day': round(avg_per_day, 1)
    }


def create_response_timeline_chart(responses):
    """
    Create timeline chart from response data

    Args:
        responses (list): List of response objects

    Returns:
        plotly figure or None
    """
    if not responses:
        return None

    try:
        # Group responses by date
        response_dates = []
        for response in responses:
            timestamp = response.get('timestamp', 0)
            if timestamp:
                response_dates.append(datetime.fromtimestamp(timestamp).date())

        if response_dates:
            df = pd.DataFrame({'date': response_dates})
            df = df.groupby('date').size().reset_index(name='responses')

            fig = px.line(
                df,
                x='date',
                y='responses',
                title="Response Timeline",
                markers=True,
                line_shape="spline"
            )

            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Number of Responses",
                hovermode='x unified'
            )

            return fig
    except Exception as e:
        logger.error(f"Chart creation failed: {e}")

    return None


def validate_survey_structure(structure):
    """
    Validate survey structure from backend

    Args:
        structure (dict): Survey structure

    Returns:
        bool: True if valid structure
    """
    required_fields = ['title', 'questions']

    if not isinstance(structure, dict):
        return False

    for field in required_fields:
        if field not in structure:
            return False

    questions = structure.get('questions', [])
    if not isinstance(questions, list) or len(questions) == 0:
        return False

    for question in questions:
        if not isinstance(question, dict):
            return False
        if 'question' not in question or 'options' not in question:
            return False
        if not isinstance(question['options'], list) or len(question['options']) < 2:
            return False

    return True


def get_real_time_stats(backend_url):
    """
    Get real-time statistics for dashboard

    Args:
        backend_url (str): Backend URL

    Returns:
        dict: Real-time stats
    """
    stats = {
        'surveys_count': 0,
        'responses_count': 0,
        'agent_status': 'offline',
        'last_updated': datetime.now().strftime("%H:%M:%S")
    }

    # Get surveys
    surveys = safe_request(
        'get', f"{backend_url}/recent_surveys", params={'limit': 1000})
    if surveys:
        stats['surveys_count'] = len(surveys)

        # Get responses for all surveys
        all_responses = []
        for survey in surveys:
            survey_id = survey.get('survey_id')
            if survey_id:
                responses = safe_request(
                    'get', f"{backend_url}/get_survey_responses/{survey_id}")
                if responses and responses.get('responses'):
                    all_responses.extend(responses['responses'])

        stats['responses_count'] = len(all_responses)

    # Get agent status
    agent_status = safe_request('get', f"{backend_url}/agent/run_checks")
    if agent_status and agent_status.get('ok'):
        if agent_status.get('status') == 'pending':
            stats['agent_status'] = 'active'
        else:
            stats['agent_status'] = 'monitoring'

    return stats
