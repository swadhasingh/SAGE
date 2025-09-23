# app.py - Final Corrected SAGE Backend
# Description: This version fixes critical bugs in survey rendering and data retrieval,
# ensuring all pages (Create, Analyze, URL/QR) work correctly. It uses ChromaDB
# as the single source of truth and contains all necessary components to run.

# ----------------- IMPORTS -----------------
import os
import re
import json
import time
import uuid
import logging
import atexit
from io import BytesIO
from datetime import datetime

# --- Flask & Web Server ---
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
from flask_socketio import SocketIO

# --- AI & Database ---
from dotenv import load_dotenv
import chromadb
from langchain_google_genai import ChatGoogleGenerativeAI

# --- Utilities ---
import qrcode
from apscheduler.schedulers.background import BackgroundScheduler

# ----------------- INITIALIZATION & CONFIG -----------------
load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# --- Gemini LLM Client ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise ValueError("GEMINI_API_KEY is not set in the .env file.")
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", google_api_key=GEMINI_KEY)

# --- ChromaDB Persistent Client ---
db_client = chromadb.PersistentClient(path="./memory")
survey_collection = db_client.get_or_create_collection(name="surveys")
response_collection = db_client.get_or_create_collection(name="responses")
individual_analysis_collection = db_client.get_or_create_collection(
    name="individual_analyses")

# ----------------- SYSTEM PROMPTS -----------------
SURVEY_CREATION_PROMPT = """
You are an expert survey designer. Based on the user's request, create a JSON object for a survey.
Return ONLY a valid JSON object with this exact structure:
{
  "title": "Survey Title",
  "description": "Brief description of the survey's purpose.",
  "questions": [
    { "question": "Question text here?", "options": ["Option 1", "Option 2", "Option 3"] }
  ]
}
Guidelines: Create 5-7 relevant multiple-choice questions with 3-5 clear options each.
User request: """

ANALYSIS_PROMPT = """
You are a survey analysis expert. Analyze the aggregated survey responses and provide insights.
Return ONLY a valid JSON object with this structure:
{
  "overall_sentiment": "positive | negative | mixed | neutral",
  "key_insights": ["Insight 1...", "Insight 2..."],
  "recommendations": ["Actionable recommendation 1...", "Actionable recommendation 2..."],
  "priority_areas": ["Area to focus on 1..."]
}
Survey responses to analyze:
"""

INDIVIDUAL_ANALYSIS_PROMPT = """
You are an expert response analyzer. Analyze this individual response.
Return ONLY a valid JSON object with this structure:
{
  "sentiment": "positive | negative | neutral",
  "themes": ["theme1", "theme2"],
  "feedback": "Brief, actionable feedback from the response.",
  "full_analysis": "A detailed explanation of your reasoning."
}
Response to analyze: """

# ----------------- HTML TEMPLATE FOR SURVEY -----------------
# This was the missing piece causing the survey URLs to fail.
SURVEY_FORM_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ survey.title }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; background-color: #f4f7f6; color: #333; margin: 0; padding: 2rem; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { max-width: 700px; width: 100%; background: #fff; padding: 2.5rem; border-radius: 12px; box-shadow: 0 6px 25px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; margin-top: 0; }
        p.description { color: #555; text-align: center; margin-bottom: 2.5rem; font-size: 1.1rem; }
        .question-block { margin-bottom: 2rem; }
        .question-title { display: block; font-weight: 600; margin-bottom: 1rem; font-size: 1.15rem; }
        .options-group { display: flex; flex-direction: column; gap: 0.75rem; }
        .option { display: flex; align-items: center; padding: 1rem; border: 1px solid #ddd; border-radius: 8px; cursor: pointer; transition: all 0.2s ease-in-out; }
        .option:hover { background-color: #f8f9fa; border-color: #667eea; }
        .option input[type="radio"] { margin-right: 0.8rem; transform: scale(1.2); accent-color: #667eea; }
        button { display: block; width: 100%; padding: 1rem; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 1.1rem; font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; margin-top: 2rem; }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3); }
        .thank-you { text-align: center; padding: 3rem 1rem; font-size: 1.8rem; font-weight: 500; color: #28a745; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div id="survey-form">
            <h1>{{ survey.title }}</h1>
            <p class="description">{{ survey.description }}</p>
            <form id="sage-survey-form">
                {% for question in survey.questions %}
                <div class="question-block">
                    <label class="question-title">{{ question.question }}</label>
                    <div class="options-group">
                        {% for option in question.options %}
                        <label class="option">
                            <input type="radio" name="{{ question.question | replace(' ', '_') | replace('?', '') }}" value="{{ option }}" required>
                            <span>{{ option }}</span>
                        </label>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
                <button type="submit">Submit Response</button>
            </form>
        </div>
        <div id="thank-you-message" class="thank-you">
            ✅<br>Thank you for your response!
        </div>
    </div>
    <script>
        document.getElementById('sage-survey-form').addEventListener('submit', function(event) {
            event.preventDefault();
            const formData = new FormData(this);
            const responses = {};
            // Use the original question text as the key
            const questions = {{ survey.questions|tojson }};
            questions.forEach(q => {
                const key = q.question.replace(/ /g, '_').replace(/\\?/g, '');
                if (formData.has(key)) {
                    responses[q.question] = formData.get(key);
                }
            });
            fetch('/submit_survey_response/{{ survey_id }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ responses: responses })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('survey-form').style.display = 'none';
                    document.getElementById('thank-you-message').style.display = 'block';
                } else {
                    alert('Error submitting response. Please try again.');
                }
            }).catch(error => alert('An network error occurred.'));
        });
    </script>
</body>
</html>
"""

# ----------------- HELPER FUNCTIONS -----------------


def extract_json_like(s: str):
    """Robustly extracts a JSON object from a string."""
    match = re.search(r'```json\s*(\{.*\})\s*```', s, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        start = s.index('{')
        end = s.rindex('}') + 1
        return json.loads(s[start:end])
    except (ValueError, json.JSONDecodeError):
        app.logger.error(f"Could not extract JSON from: {s[:200]}")
        return None

# ----------------- CORE ROUTES -----------------


@app.route("/")
def home():
    return jsonify({"status": "SAGE Backend Running", "version": "2.2-stable"})

# ----------------- SURVEY CREATION & SERVING -----------------


@app.route("/create_survey", methods=["POST"])
def create_survey():
    data = request.get_json() or {}
    user_prompt = data.get("prompt", "").strip()
    if not user_prompt:
        return jsonify({"error": "Prompt cannot be empty"}), 400
    try:
        llm_response = llm.invoke(SURVEY_CREATION_PROMPT + user_prompt).content
        structure = extract_json_like(llm_response)
        if not structure or "questions" not in structure:
            return jsonify({"error": "AI failed to generate a valid survey.", "raw_response": llm_response}), 500

        survey_id = str(uuid.uuid4())
        metadata = {
            "survey_id": survey_id, "user_prompt": user_prompt,
            "title": structure.get("title", "AI Survey"), "description": structure.get("description", ""),
            "public_url": f"{request.host_url}survey/{survey_id}", "created_at": int(time.time())
        }
        survey_collection.add(ids=[survey_id], documents=[
                              json.dumps(structure)], metadatas=[metadata])
        socketio.emit(
            "new_survey", {"survey_id": survey_id, "metadata": metadata})
        return jsonify({"survey_id": survey_id, "public_url": metadata["public_url"], "structure": structure})
    except Exception as e:
        app.logger.error(f"Survey creation failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error during survey creation."}), 500


@app.route("/survey/<survey_id>")
def display_survey(survey_id):
    try:
        result = survey_collection.get(ids=[survey_id])
        if not result or not result.get('documents'):
            return render_template_string("<h1>404: Survey not found</h1>"), 404
        structure = json.loads(result['documents'][0])
        return render_template_string(SURVEY_FORM_TEMPLATE, survey=structure, survey_id=survey_id)
    except Exception as e:
        app.logger.error(
            f"Display survey {survey_id} failed: {e}", exc_info=True)
        return render_template_string("<h1>500: Error loading survey</h1>"), 500


@app.route("/survey/<survey_id>/qr")
def survey_qr(survey_id):
    """Generates and serves a QR code for the survey URL."""
    try:
        url = f"{request.host_url}survey/{survey_id}"
        qr_img = qrcode.make(url)
        buf = BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        app.logger.error(
            f"QR generation failed for {survey_id}: {e}", exc_info=True)
        return "Error generating QR code.", 500

# ----------------- RESPONSE & ANALYSIS ROUTES -----------------


@app.route("/submit_survey_response/<survey_id>", methods=["POST"])
def submit_survey_response(survey_id):
    data = request.get_json() or {}
    answers = data.get("responses", {})
    if not answers:
        return jsonify({"error": "No responses provided"}), 400
    try:
        response_id = str(uuid.uuid4())
        metadata = {"survey_id": survey_id, "timestamp": int(time.time())}
        response_collection.add(ids=[response_id], documents=[
                                json.dumps(answers)], metadatas=[metadata])
        socketio.emit("new_response", {"survey_id": survey_id})
        return jsonify({"success": True, "response_id": response_id})
    except Exception as e:
        app.logger.error(
            f"Response submission for {survey_id} failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to submit response."}), 500


@app.route("/get_survey_responses/<survey_id>")
def get_survey_responses(survey_id):
    try:
        results = response_collection.get(where={"survey_id": survey_id})
        if not results.get('ids'):
            return jsonify({"survey_id": survey_id, "responses": []})
        responses = [{"response_id": res_id, "answers": json.loads(doc), "timestamp": meta.get("timestamp")}
                     for res_id, doc, meta in zip(results['ids'], results['documents'], results['metadatas'])]
        return jsonify({"survey_id": survey_id, "responses": responses})
    except Exception as e:
        app.logger.error(
            f"Retrieving responses for {survey_id} failed: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve responses."}), 500


@app.route("/recent_surveys")
def get_recent_surveys():
    """ This function is now fixed to prevent data corruption. """
    try:
        results = survey_collection.get()
        if not results.get('ids'):
            return jsonify([])

        all_surveys = [
            {**meta, 'structure': json.loads(doc)}
            for meta, doc in zip(results['metadatas'], results['documents'])
        ]
        sorted_surveys = sorted(all_surveys, key=lambda x: x.get(
            'created_at', 0), reverse=True)
        return jsonify(sorted_surveys)
    except Exception as e:
        app.logger.error(f"Failed to get recent surveys: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve recent surveys."}), 500


@app.route("/analyze_survey_responses", methods=["POST"])
def analyze_survey_responses():
    data = request.get_json() or {}
    survey_id = data.get("form_id")
    if not survey_id:
        return jsonify({"error": "No survey_id provided"}), 400
    try:
        results = response_collection.get(where={"survey_id": survey_id})
        if not results.get('documents'):
            return jsonify({"error": "No responses found for this survey"}), 404

        raw_responses = [json.loads(doc) for doc in results['documents']]
        text_blob = "\n".join([str(item) for item in raw_responses])
        llm_resp = llm.invoke(ANALYSIS_PROMPT + text_blob).content
        analysis = extract_json_like(llm_resp)
        if not analysis:
            return jsonify({"error": "AI failed to produce a valid analysis.", "raw_response": llm_resp}), 500

        return jsonify({"form_id": survey_id, "analysis": analysis, "raw_responses": raw_responses})
    except Exception as e:
        app.logger.error(
            f"Analysis for {survey_id} failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error during analysis."}), 500


@app.route("/submit", methods=["POST"])
def submit_individual_analysis():
    data = request.get_json() or {}
    response_text = data.get("response", "").strip()
    if not response_text:
        return jsonify({"error": "No response text provided"}), 400
    try:
        llm_resp = llm.invoke(
            INDIVIDUAL_ANALYSIS_PROMPT + response_text).content
        analysis = extract_json_like(llm_resp)
        if not analysis:
            return jsonify({"error": "AI failed to produce a valid analysis."}), 500

        response_id = str(uuid.uuid4())
        metadata = {"user_input": response_text,
                    "timestamp": int(time.time()), **analysis}
        individual_analysis_collection.add(ids=[response_id], documents=[
                                           response_text], metadatas=[metadata])
        return jsonify({"id": response_id, "analysis": analysis})
    except Exception as e:
        app.logger.error(f"Individual analysis failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error during analysis."}), 500

# ----------------- AGENT & SOCKETS -----------------


@app.route("/agent/run_checks")
def run_checks():
    return jsonify({"ok": True, "status": "monitoring", "reason": "no_action_needed"})


@socketio.on('connect')
def handle_connect():
    app.logger.info("Socket.IO client connected")


# ----------------- SCHEDULER & SHUTDOWN -----------------
scheduler = BackgroundScheduler()
# scheduler.add_job(func=run_checks, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ----------------- MAIN EXECUTION -----------------
if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0',
                 port=5000, allow_unsafe_werkzeug=True)
