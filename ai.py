import os
import openai
import pandas as pd
from flask import Flask, request, jsonify
from sklearn.cluster import KMeans

app = Flask(__name__)

# Set OpenAI API Key
openai.api_key = os.getenv("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")

# 1. CSV Dosyasını Oku ve Veriyi İşle
df = pd.read_csv("study_sessions_detailed.csv")
df['date'] = pd.to_datetime(df['date'])

# Kullanıcı bazında ortalama istatistikleri hesapla
user_stats = df.groupby("user_id").agg(
    avg_session_duration=("session_duration", "mean"),
    avg_break_duration=("break_duration", "mean"),
    avg_distractions=("distractions", "mean"),
    avg_productivity_score=("productivity_score", "mean"),
    avg_focus_level=("focus_level", "mean"),
    total_tasks_completed=("task_completed", "sum")
).reset_index()

# 2. Kullanıcıları K-Means ile Gruplandır
def perform_clustering():
    features = user_stats[[
        "avg_session_duration", "avg_break_duration", 
        "avg_distractions", "avg_productivity_score", 
        "avg_focus_level", "total_tasks_completed"
    ]]
    kmeans = KMeans(n_clusters=3, random_state=42)
    user_stats["cluster"] = kmeans.fit_predict(features)

perform_clustering()

# 3. KİŞisel Öneriler

def generate_recommendation(user_id):
    user_data = user_stats[user_stats["user_id"] == user_id]
    if user_data.empty:
        return "No data available for this user."
    user_data = user_data.iloc[0]
    cluster = user_data["cluster"]
    recommendations = []

    if cluster == 0:
        recommendations.append("Your overall performance is low; consider reducing session durations and increasing breaks.")
    elif cluster == 1:
        recommendations.append("Your performance is average; try optimizing your environment to reduce distractions.")
    elif cluster == 2:
        recommendations.append("Excellent performance! Maintain your current study habits.")

    if user_data["avg_session_duration"] > 60:
        recommendations.append("Your work sessions are long, try shorter Pomodoro cycles.")
    else:
        recommendations.append("Your work session duration is optimal.")

    if user_data["avg_break_duration"] < 5:
        recommendations.append("Consider extending your break duration to improve focus.")
    else:
        recommendations.append("Your break durations are well balanced.")

    if user_data["avg_distractions"] > 3:
        recommendations.append("Minimize distractions by working in a quieter environment.")
    else:
        recommendations.append("Your distraction levels are low.")

    if user_data["avg_productivity_score"] < 3:
        recommendations.append("Your productivity seems low; experiment with new techniques.")
    else:
        recommendations.append("Your productivity scores are good.")

    if user_data["avg_focus_level"] < 6:
        recommendations.append("Your focus level is below average; consider concentration improvement techniques.")
    else:
        recommendations.append("Your focus level is impressive!")

    return {
        "user_id": user_id,
        "study_report": recommendations,
        "cluster": int(cluster),
        "avg_session_duration": round(user_data["avg_session_duration"], 2),
        "avg_break_duration": round(user_data["avg_break_duration"], 2),
        "avg_productivity_score": round(user_data["avg_productivity_score"], 2),
        "avg_focus_level": round(user_data["avg_focus_level"], 2),
        "total_tasks_completed": int(user_data["total_tasks_completed"])
    }

# 4. Haftalık İlerleme

def get_weekly_progress(user_id):
    base_progress = {"M": 0.0, "T": 0.0, "W": 0.0, "T2": 0.0, "F": 0.0, "S": 0.0, "S2": 0.0}
    user_data = df[df["user_id"] == user_id]
    if user_data.empty:
        return base_progress

    weekly_progress = user_data.groupby(user_data["date"].dt.strftime('%A'))["session_duration"].mean().to_dict()
    day_map = {"Monday": "M", "Tuesday": "T", "Wednesday": "W", "Thursday": "T2", "Friday": "F", "Saturday": "S", "Sunday": "S2"}
    
    for day, duration in weekly_progress.items():
        key = day_map.get(day, day)
        base_progress[key] = round(duration / 90, 2)

    return base_progress

# 5. OpenAI Prompt ve yanıt

def build_prompt(user_id):
    user_data = user_stats[user_stats["user_id"] == user_id].iloc[0]
    prompt = (
        f"User ID: {user_id}\n"
        f"Average Session Duration: {round(user_data['avg_session_duration'], 2)} min\n"
        f"Average Break Duration: {round(user_data['avg_break_duration'], 2)} min\n"
        f"Average Productivity Score: {round(user_data['avg_productivity_score'], 2)}\n"
        f"Average Focus Level: {round(user_data['avg_focus_level'], 2)} / 10\n"
        f"Total Tasks Completed: {int(user_data['total_tasks_completed'])}\n\n"
        "Based on the above statistics, provide personalized study suggestions in a concise and clear format."
    )
    return prompt

def get_openai_suggestions(prompt_text):
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt_text,
            max_tokens=150,
            temperature=0.7
        )
        suggestion = response.choices[0].text.strip()
        return suggestion
    except Exception as e:
        return f"Error fetching suggestions: {e}"

# Flask API Endpoint

@app.route('/openaiSuggestions', methods=['GET'])
def openai_suggestions():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return jsonify({"error": "Please provide a valid user_id"}), 400

    prompt = build_prompt(user_id)
    suggestions = get_openai_suggestions(prompt)
    return jsonify({
        "user_id": user_id,
        "openai_suggestions": suggestions
    })

@app.route('/stats', methods=['GET'])
def stats():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return jsonify({"error": "Please provide a valid user_id"}), 400

    report = generate_recommendation(user_id)
    weekly_progress = get_weekly_progress(user_id)
    total_sessions = df[df["user_id"] == user_id].shape[0]
    user_data = user_stats[user_stats["user_id"] == user_id].iloc[0]
    avg_focus = user_data["avg_focus_level"]
    focus_rate_calculated = f"{round(avg_focus * 10)}%"
    latest_data = df[df["user_id"] == user_id].sort_values("date", ascending=False).iloc[0]

    return jsonify({
        "user_id": user_id,
        "today_focus_time": f"{latest_data['session_duration']} min",
        "completed_pomodoros": str(total_sessions),
        "focus_rate": focus_rate_calculated,
        "weekly_progress": weekly_progress,
        "study_report": report["study_report"],
        "avg_session_duration": report["avg_session_duration"],
        "avg_break_duration": report["avg_break_duration"],
        "avg_productivity_score": report["avg_productivity_score"],
        "avg_focus_level": report["avg_focus_level"],
        "total_tasks_completed": report["total_tasks_completed"],
        "cluster": report["cluster"]
    })

@app.route('/studyReport', methods=['GET'])
def study_report_endpoint():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return jsonify({"error": "Please provide a valid user_id"}), 400

    report = generate_recommendation(user_id)
    return jsonify(report)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
