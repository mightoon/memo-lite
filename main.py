from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import json

app = Flask(__name__)

class PrefixMiddleware:
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        # 检查是否有 X-Forwarded-Prefix 头（由 Nginx 设置）
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if prefix:
            environ['SCRIPT_NAME'] = prefix
        return self.app(environ, start_response)

app.wsgi_app = PrefixMiddleware(app.wsgi_app)

NOTES_FILE = "notes.txt"

# 确保笔记文件存在
def ensure_notes_file():
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            pass

# 读取所有笔记
def read_notes():
    ensure_notes_file()
    notes = []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                note = json.loads(line)
                notes.append(note)
            except json.JSONDecodeError:
                # 兼容旧格式: [timestamp] content
                if line.startswith("[") and "]" in line:
                    closing_bracket = line.find("]")
                    timestamp_str = line[1:closing_bracket]
                    content = line[closing_bracket + 2:].strip()
                    notes.append({
                        "id": timestamp_str.replace(" ", "_").replace(":", "-"),
                        "timestamp": timestamp_str,
                        "content": content,
                        "status": "待处理"
                    })
    return notes

# 写入所有笔记
def write_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        for note in notes:
            f.write(json.dumps(note, ensure_ascii=False) + "\n")

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
    note_id = timestamp.replace(" ", "_").replace(":", "-")
    
    note = {
        "id": note_id,
        "timestamp": timestamp,
        "content": content,
        "status": "待处理"
    }
    
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(note, ensure_ascii=False) + "\n")
    
    return jsonify({"message": "记录成功", "timestamp": timestamp, "id": note_id}), 201

@app.route("/api/notes", methods=["GET"])
def get_notes():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    status_filter = request.args.get("status")  # 待处理, 已处理, 全部
    
    notes = read_notes()
    filtered_notes = []
    
    for note in notes:
        note_time = datetime.strptime(note["timestamp"], "%Y-%m-%d %H:%M:%S")
        
        # 时间筛选
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            if note_time.date() < start.date():
                continue
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            if note_time.date() > end.date():
                continue
        
        # 状态筛选
        if status_filter and status_filter != "全部":
            if note.get("status", "待处理") != status_filter:
                continue
        
        filtered_notes.append(note)
    
    # 按时间倒序排列
    filtered_notes.reverse()
    return jsonify({"notes": filtered_notes})

@app.route("/api/notes/<note_id>/status", methods=["PUT"])
def update_note_status(note_id):
    data = request.get_json()
    new_status = data.get("status")
    
    if new_status not in ["待处理", "已处理"]:
        return jsonify({"error": "状态必须是'待处理'或'已处理'"}), 400
    
    notes = read_notes()
    found = False
    
    for note in notes:
        if note["id"] == note_id:
            note["status"] = new_status
            found = True
            break
    
    if not found:
        return jsonify({"error": "笔记不存在"}), 404
    
    write_notes(notes)
    return jsonify({"message": "状态更新成功"})

@app.route("/api/notes/batch/status", methods=["PUT"])
def batch_update_status():
    data = request.get_json()
    note_ids = data.get("ids", [])
    new_status = data.get("status")
    
    if not note_ids:
        return jsonify({"error": "请选择要更新的笔记"}), 400
    
    if new_status not in ["待处理", "已处理"]:
        return jsonify({"error": "状态必须是'待处理'或'已处理'"}), 400
    
    notes = read_notes()
    updated_count = 0
    
    for note in notes:
        if note["id"] in note_ids:
            note["status"] = new_status
            updated_count += 1
    
    write_notes(notes)
    return jsonify({"message": f"成功更新 {updated_count} 条笔记", "updated": updated_count})

@app.route("/api/notes/batch", methods=["DELETE"])
def batch_delete_notes():
    data = request.get_json()
    note_ids = data.get("ids", [])
    
    if not note_ids:
        return jsonify({"error": "请选择要删除的笔记"}), 400
    
    notes = read_notes()
    original_count = len(notes)
    
    # 过滤掉要删除的笔记
    notes = [note for note in notes if note["id"] not in note_ids]
    
    deleted_count = original_count - len(notes)
    
    write_notes(notes)
    return jsonify({"message": f"成功删除 {deleted_count} 条笔记", "deleted": deleted_count})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
