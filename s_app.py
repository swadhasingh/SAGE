# streamlit_app.py - Complete Rewrite with Full Backend Integration
from sage_utils import apply_custom_css, check_backend_connection, generate_qr_code, safe_request
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import time
import qrcode
from io import BytesIO
import base64

# Configuration
BACKEND_URL = "http://127.0.0.1:5000"

# Page Configuration
st.set_page_config(
    page_title="SAGE - Survey Agent for General Evaluation",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import custom styling and helper functions

# Apply styling
apply_custom_css()

# Header
st.markdown('<h1 class="main-header">🤖 SAGE - Survey Analysis Generation Engine</h1>',
            unsafe_allow_html=True)

# Backend Connection Check
if not check_backend_connection(BACKEND_URL):
    st.error(
        "❌ Cannot connect to SAGE backend. Please ensure the Flask server is running on port 5000.")
    st.stop()

# Sidebar Navigation
st.sidebar.title("🧭 Navigation")
page = st.sidebar.selectbox(
    "Choose a page:",
    [
        "📊 Dashboard",
        "📝 Create Survey",
        "📈 Survey Analysis",
        "💬 Individual Analysis",
        "🤖 Agent Management",
        "📋 Response Monitor",
        "⚙️ System Settings"
    ]
)

# Agent Status in Sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🤖 Agent Status")

    agent_status = safe_request('get', f"{BACKEND_URL}/agent/run_checks")
    if agent_status and agent_status.get('ok'):
        if agent_status.get('status') == 'pending':
            st.markdown(
                '<div class="real-time-indicator">Agent Active</div>', unsafe_allow_html=True)
        else:
            st.success("Agent Monitoring")
    else:
        st.warning("Agent Offline")

# ============== DASHBOARD PAGE ==============
if page == "📊 Dashboard":
    st.markdown('<h2 class="section-header">📈 Dashboard Overview</h2>',
                unsafe_allow_html=True)

    # Real-time refresh
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", value=False)
    if auto_refresh:
        time.sleep(30)
        st.rerun()

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)

    # Fetch survey count
    surveys_data = safe_request(
        'get', f"{BACKEND_URL}/recent_surveys", params={'limit': 100})
    total_surveys = len(surveys_data) if surveys_data else 0

    # Fetch responses for all surveys
    all_responses = []
    if surveys_data:
        for survey in surveys_data:
            survey_id = survey.get('survey_id')
            if survey_id:
                responses = safe_request(
                    'get', f"{BACKEND_URL}/get_survey_responses/{survey_id}")
                if responses and responses.get('responses'):
                    all_responses.extend(responses['responses'])

    total_responses = len(all_responses)

    with col1:
        st.metric("Total Surveys", total_surveys,
                  delta=f"+{min(total_surveys, 5)} recent")

    with col2:
        st.metric("Total Responses", total_responses)

    with col3:
        # Calculate response rate (dummy calculation)
        avg_responses = total_responses / max(total_surveys, 1)
        st.metric("Avg Responses/Survey", f"{avg_responses:.1f}")

    with col4:
        # Recent activity
        recent_count = len([r for r in all_responses if r.get(
            'timestamp', 0) > time.time() - 86400])
        st.metric("Responses Today", recent_count)

    # Charts Row
    col1, col2 = st.columns(2)

    with col1:
        if total_responses > 0:
            # Response timeline
            response_dates = []
            for response in all_responses:
                timestamp = response.get('timestamp', 0)
                if timestamp:
                    response_dates.append(
                        datetime.fromtimestamp(timestamp).date())

            if response_dates:
                df_timeline = pd.DataFrame({'date': response_dates})
                df_timeline = df_timeline.groupby(
                    'date').size().reset_index(name='count')

                fig_timeline = px.line(df_timeline, x='date', y='count',
                                       title="📅 Response Timeline",
                                       markers=True)
                st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("No response data available yet.")

    with col2:
        if surveys_data:
            # Survey creation timeline
            survey_dates = []
            for survey in surveys_data:
                created_at = survey.get('created_at', 0)
                if created_at:
                    survey_dates.append(
                        datetime.fromtimestamp(created_at).date())

            if survey_dates:
                df_surveys = pd.DataFrame({'date': survey_dates})
                df_surveys = df_surveys.groupby(
                    'date').size().reset_index(name='count')

                fig_surveys = px.bar(df_surveys, x='date', y='count',
                                     title="📊 Surveys Created",
                                     color='count')
                st.plotly_chart(fig_surveys, use_container_width=True)
        else:
            st.info("No survey data available yet.")

    # Recent Activity
    st.markdown('<h3 class="section-header">🕒 Recent Activity</h3>',
                unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Recent Surveys", "Recent Responses"])

    with tab1:
        if surveys_data:
            for survey in surveys_data[:5]:
                created_date = datetime.fromtimestamp(
                    survey.get('created_at', 0)).strftime("%Y-%m-%d %H:%M")
                survey_title = survey.get('structure', {}).get(
                    'title', 'Untitled Survey')
                survey_desc = survey.get('structure', {}).get(
                    'description', 'No description')

                with st.expander(f"📋 {survey_title} - {created_date}"):
                    st.write(f"**Description:** {survey_desc}")
                    st.write(
                        f"**Questions:** {len(survey.get('structure', {}).get('questions', []))}")
                    st.write(
                        f"**Survey URL:** {BACKEND_URL.replace(':5000', ':8501')}/survey/{survey.get('survey_id', '')}")
        else:
            st.info("No surveys found. Create your first survey!")

    with tab2:
        if all_responses:
            recent_responses = sorted(all_responses, key=lambda x: x.get(
                'timestamp', 0), reverse=True)[:10]

            for response in recent_responses:
                timestamp = datetime.fromtimestamp(response.get(
                    'timestamp', 0)).strftime("%Y-%m-%d %H:%M")
                answers = response.get('answers', {})

                with st.expander(f"💬 Response - {timestamp}"):
                    for question, answer in answers.items():
                        st.write(f"**{question}:** {answer}")
        else:
            st.info("No responses found yet.")

# ============== CREATE SURVEY PAGE ==============
elif page == "📝 Create Survey":
    st.markdown('<h2 class="section-header">🆕 Create New Survey</h2>',
                unsafe_allow_html=True)

    st.markdown("""
    ### How it works:
    1. **Describe your survey goal** - Tell the AI what you want to survey about
    2. **AI generates questions** - Gemini creates relevant questions automatically
    3. **Survey form created** - A shareable form is generated with QR code
    4. **Real-time monitoring** - Track responses as they come in
    """)

    with st.form("create_survey_form", clear_on_submit=True):
        st.markdown("#### 📝 Survey Description")
        survey_prompt = st.text_area(
            "Describe what you want to survey about:",
            placeholder="Example: I want to survey customer satisfaction with our new mobile app, focusing on usability, performance, and feature requests.",
            height=120
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            create_btn = st.form_submit_button(
                "🚀 Create Survey", type="primary")
        with col2:
            example_btn = st.form_submit_button("💡 Use Example")

    if create_btn or example_btn:
        if example_btn:
            survey_prompt = "I want to survey employee satisfaction with remote work policies, including work-life balance, productivity tools, communication, and overall job satisfaction."

        if not survey_prompt:
            st.error("Please provide a survey description.")
        else:
            with st.spinner("🤖 AI is designing your survey..."):
                result = safe_request(
                    'post', f"{BACKEND_URL}/create_survey", json={"prompt": survey_prompt})

                if result:
                    st.markdown('<div class="success-box">',
                                unsafe_allow_html=True)
                    st.success("✅ Survey created successfully!")
                    st.markdown('</div>', unsafe_allow_html=True)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("#### 🔗 Survey Access")
                        survey_url = result['public_url']
                        st.markdown(
                            f"**Survey URL:** [Open Survey]({survey_url})")
                        st.code(survey_url)

                        # Generate QR Code
                        qr_img = generate_qr_code(survey_url)
                        st.markdown("**QR Code:**")
                        st.markdown(
                            f'<img src="{qr_img}" width="200">', unsafe_allow_html=True)

                    with col2:
                        st.markdown("#### 📋 Survey Details")
                        structure = result.get('structure', {})
                        st.write(f"**Title:** {structure.get('title', 'N/A')}")
                        st.write(
                            f"**Questions:** {len(structure.get('questions', []))}")
                        st.write(
                            f"**Survey ID:** {result.get('survey_id', 'N/A')}")

                    # Show generated questions
                    st.markdown("#### ❓ Generated Questions")
                    questions = structure.get('questions', [])
                    for i, q in enumerate(questions, 1):
                        with st.expander(f"Question {i}: {q.get('question', 'No question text')[:50]}..."):
                            st.write(
                                f"**Question:** {q.get('question', 'No question text')}")
                            st.write("**Options:**")
                            for option in q.get('options', []):
                                st.write(f"• {option}")
                else:
                    st.error(
                        "Failed to create survey. Please check the backend connection.")

# ============== SURVEY ANALYSIS PAGE ==============
elif page == "📈 Survey Analysis":
    st.markdown('<h2 class="section-header">📈 Survey Response Analysis</h2>',
                unsafe_allow_html=True)

    st.markdown("""
    ### Analyze Survey Responses
    Select a survey to get AI-powered insights and analysis of all responses.
    """)

    # Get list of surveys
    surveys_data = safe_request(
        'get', f"{BACKEND_URL}/recent_surveys", params={'limit': 50})

    if surveys_data:
        survey_options = {}
        for survey in surveys_data:
            survey_id = survey.get('survey_id')
            title = survey.get('structure', {}).get('title', 'Untitled Survey')
            created = datetime.fromtimestamp(
                survey.get('created_at', 0)).strftime("%Y-%m-%d")
            survey_options[f"{title} ({created})"] = survey_id

        with st.form("analyze_survey_form"):
            selected_survey = st.selectbox(
                "Select a survey to analyze:",
                options=list(survey_options.keys()),
                help="Choose from your created surveys"
            )

            analyze_btn = st.form_submit_button(
                "🔍 Analyze Responses", type="primary")

        if analyze_btn and selected_survey:
            survey_id = survey_options[selected_survey]

            with st.spinner("🧠 AI is analyzing survey responses..."):
                result = safe_request('post', f"{BACKEND_URL}/analyze_survey_responses",
                                      json={"form_id": survey_id})

                if result:
                    st.markdown('<div class="success-box">',
                                unsafe_allow_html=True)
                    st.success("✅ Analysis completed successfully!")
                    st.markdown('</div>', unsafe_allow_html=True)

                    # Display analysis results
                    analysis = result.get('analysis', {})

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("#### 📊 Overview")
                        st.write(f"**Survey:** {selected_survey}")
                        st.write(
                            f"**Total Responses:** {len(result.get('raw_responses', []))}")
                        st.write(
                            f"**Overall Sentiment:** {analysis.get('overall_sentiment', 'N/A').title()}")

                    with col2:
                        st.markdown("#### 🎯 Priority Areas")
                        priority_areas = analysis.get('priority_areas', [])
                        if priority_areas:
                            for area in priority_areas:
                                st.write(f"• {area}")
                        else:
                            st.write("No priority areas identified")

                    # Key Insights
                    st.markdown("#### 💡 Key Insights")
                    insights = analysis.get('key_insights', [])
                    if insights:
                        for insight in insights:
                            st.write(f"• {insight}")
                    else:
                        st.write("No specific insights identified")

                    # Recommendations
                    st.markdown("#### 🎯 Recommendations")
                    recommendations = analysis.get('recommendations', [])
                    if recommendations:
                        for i, rec in enumerate(recommendations, 1):
                            st.write(f"{i}. {rec}")
                    else:
                        st.write("No specific recommendations available")

                    # Raw data
                    with st.expander("📋 Raw Response Data"):
                        if result.get('raw_responses'):
                            df = pd.DataFrame(result['raw_responses'])
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.write("No response data available")
                else:
                    st.error("Failed to analyze survey responses.")
    else:
        st.info("No surveys found. Create a survey first to analyze responses.")

# ============== INDIVIDUAL ANALYSIS PAGE ==============
elif page == "💬 Individual Analysis":
    st.markdown('<h2 class="section-header">🔍 Individual Response Analysis</h2>',
                unsafe_allow_html=True)

    with st.form("individual_analysis_form"):
        response_text = st.text_area(
            "Enter response text to analyze:",
            placeholder="Example: The app works well but crashes sometimes. Overall I'm satisfied.",
            height=120
        )

        analyze_btn = st.form_submit_button(
            "🔍 Analyze Response", type="primary")

    if analyze_btn and response_text:
        with st.spinner("🤖 Analyzing response..."):
            result = safe_request(
                'post', f"{BACKEND_URL}/submit", json={"response": response_text})

            if result:
                analysis = result.get('analysis', {})

                col1, col2, col3 = st.columns(3)

                with col1:
                    sentiment = analysis.get('sentiment', 'neutral')
                    sentiment_colors = {'positive': '#28a745',
                                        'negative': '#dc3545', 'neutral': '#ffc107'}
                    st.markdown(f"""
                    <div style="background-color: {sentiment_colors[sentiment]}20; padding: 1rem; border-radius: 0.5rem; text-align: center;">
                        <h4 style="color: {sentiment_colors[sentiment]};">Sentiment: {sentiment.title()}</h4>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    themes = analysis.get('themes', [])
                    st.markdown("#### 🏷️ Themes")
                    if themes:
                        for theme in themes:
                            st.write(f"• {theme}")
                    else:
                        st.write("No themes identified")

                with col3:
                    st.markdown("#### 📊 Analysis ID")
                    st.code(result.get('id', 'N/A'))

                # Feedback
                st.markdown("#### 💡 AI Feedback")
                feedback = analysis.get('feedback', 'No feedback available')
                st.write(feedback)
            else:
                st.error("Failed to analyze response.")

# ============== AGENT MANAGEMENT PAGE ==============
elif page == "🤖 Agent Management":
    st.markdown('<h2 class="section-header">🤖 Agent Management</h2>',
                unsafe_allow_html=True)

    # Agent status
    agent_status = safe_request('get', f"{BACKEND_URL}/agent/run_checks")

    if agent_status:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📊 Agent Status")
            if agent_status.get('ok'):
                st.success("Agent is operational")
                if agent_status.get('status') == 'pending':
                    st.warning("Agent has pending actions")
                else:
                    st.info("Agent monitoring - no actions needed")
            else:
                st.error("Agent has issues")

        with col2:
            st.markdown("#### ⚙️ Agent Controls")
            if st.button("🔄 Run Agent Check Now"):
                with st.spinner("Running agent checks..."):
                    result = safe_request(
                        'get', f"{BACKEND_URL}/agent/run_checks")
                    if result:
                        st.json(result)
                    else:
                        st.error("Failed to run agent checks")

        # Agent memory and logs
        st.markdown("#### 🧠 Agent Activity")
        st.info("Agent monitors survey sentiment and can automatically create follow-up surveys when negative sentiment is detected.")

        if agent_status.get('plan'):
            st.markdown("#### 📋 Pending Actions")
            st.json(agent_status['plan'])
    else:
        st.error("Cannot connect to agent system.")

# ============== RESPONSE MONITOR PAGE ==============
elif page == "📋 Response Monitor":
    st.markdown('<h2 class="section-header">📋 Real-time Response Monitor</h2>',
                unsafe_allow_html=True)

    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh every 10 seconds", value=False)

    if auto_refresh:
        # Create placeholder for dynamic content
        placeholder = st.empty()

        with placeholder.container():
            # Fetch all recent responses
            all_responses = []
            surveys_data = safe_request(
                'get', f"{BACKEND_URL}/recent_surveys", params={'limit': 20})

            if surveys_data:
                for survey in surveys_data:
                    survey_id = survey.get('survey_id')
                    if survey_id:
                        responses = safe_request(
                            'get', f"{BACKEND_URL}/get_survey_responses/{survey_id}")
                        if responses and responses.get('responses'):
                            for resp in responses['responses']:
                                resp['survey_title'] = survey.get(
                                    'structure', {}).get('title', 'Untitled')
                                all_responses.append(resp)

            # Sort by timestamp
            all_responses.sort(key=lambda x: x.get(
                'timestamp', 0), reverse=True)

            st.markdown(f"**Total Responses:** {len(all_responses)}")
            st.markdown(
                f"**Last Updated:** {datetime.now().strftime('%H:%M:%S')}")

            # Display recent responses
            for i, response in enumerate(all_responses[:10]):
                timestamp = datetime.fromtimestamp(response.get(
                    'timestamp', 0)).strftime("%Y-%m-%d %H:%M:%S")
                survey_title = response.get('survey_title', 'Unknown Survey')

                with st.expander(f"#{i+1} - {survey_title} - {timestamp}"):
                    answers = response.get('answers', {})
                    for question, answer in answers.items():
                        st.write(f"**{question}:** {answer}")

        # Refresh every 10 seconds
        time.sleep(10)
        st.rerun()
    else:
        st.info("Enable auto-refresh to see real-time responses.")

# ============== SYSTEM SETTINGS PAGE ==============
elif page == "⚙️ System Settings":
    st.markdown('<h2 class="section-header">⚙️ System Settings</h2>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔧 Configuration")
        st.write(f"**Backend URL:** {BACKEND_URL}")

        # Test backend connection
        if st.button("🔗 Test Backend Connection"):
            if check_backend_connection(BACKEND_URL):
                st.success("✅ Backend connection successful")
            else:
                st.error("❌ Cannot connect to backend")

        st.markdown("#### 📊 System Stats")
        surveys_data = safe_request(
            'get', f"{BACKEND_URL}/recent_surveys", params={'limit': 1000})
        total_surveys = len(surveys_data) if surveys_data else 0
        st.write(f"**Total Surveys Created:** {total_surveys}")

    with col2:
        st.markdown("#### 🔄 System Actions")

        if st.button("🗑️ Clear Cache", help="Refresh all cached data"):
            # Clear Streamlit cache
            st.cache_data.clear()
            st.success("Cache cleared successfully")

        st.markdown("#### ℹ️ About SAGE")
        st.info("""
        **SAGE - Survey Analysis Generation Engine**
        
        - AI-powered survey creation
        - Real-time response monitoring  
        - Intelligent analysis and insights
        - Automated agent actions
        - Built with Flask + Streamlit + Gemini AI
        """)

# Footer
st.markdown("---")
st.markdown("**SAGE - Survey Analysis Generation Engine** | Powered by Gemini AI")
