from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

NOTES_FILE = "notes.txt"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/notes", methods=["POST"])
def add_note():
    data = request.get_json()
    content = data.get("content", "").strip()
    
    if not content:
        return jsonify({"error": "内容不能为空"}), 400
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_line = f"[{timestamp}] {content}\n"
    
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(note_line)
    
    return jsonify({"message": "记录成功", "timestamp": timestamp}), 201

@app.route("/api/notes", methods=["GET"])
def get_notes():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    notes = []
    
    if not os.path.exists(NOTES_FILE):
        return jsonify({"notes": notes})
    
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 解析格式: [YYYY-MM-DD HH:MM:SS] content
            if line.startswith("[") and "]" in line:
                closing_bracket = line.find("]")
                timestamp_str = line[1:closing_bracket]
                content = line[closing_bracket + 2:].strip()
                
                try:
                    note_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    
                    # 时间筛选
                    if start_date:
                        start = datetime.strptime(start_date, "%Y-%m-%d")
                        if note_time.date() < start.date():
                            continue
                    
                    if end_date:
                        end = datetime.strptime(end_date, "%Y-%m-%d")
                        if note_time.date() > end.date():
                            continue
                    
                    notes.append({
                        "timestamp": timestamp_str,
                        "content": content
                    })
                except ValueError:
                    continue
    
    # 按时间倒序排列
    notes.reverse()
    return jsonify({"notes": notes})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
