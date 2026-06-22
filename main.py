from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import json
import requests
import re
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# 微信小程序配置（需要在环境变量中设置）
WX_APPID = os.environ.get('WX_APPID', '')
WX_SECRET = os.environ.get('WX_SECRET', '')

# 存储临时登录状态（生产环境应使用 Redis）
login_states = {}

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
USERS_FILE = "users.txt"
TAGS_FILE = "tags.txt"

# 确保文件存在
def ensure_file(filename):
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            pass

def read_users():
    ensure_file(USERS_FILE)
    users = {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    user = json.loads(line)
                    users[user.get('openid')] = user
                except:
                    pass
    return users

def write_user(user):
    users = read_users()
    users[user['openid']] = user
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        for u in users.values():
            f.write(json.dumps(u, ensure_ascii=False) + "\n")

def find_user_by_username(username):
    """通过用户名查找用户"""
    users = read_users()
    for user in users.values():
        if user.get('username') == username:
            return user
    return None

def ensure_admin_user():
    """确保存在 admin 用户，默认密码 admin123"""
    users = read_users()
    for u in users.values():
        if u.get('role') == 'admin':
            return
    admin_user = {
        "openid": "web_admin",
        "username": "admin",
        "password_hash": generate_password_hash("admin123"),
        "nickname": "管理员",
        "avatar": "",
        "user_type": "web",
        "role": "admin",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    write_user(admin_user)

def get_current_user():
    """从请求头获取当前用户"""
    openid = request.headers.get('X-User-Openid')
    if openid:
        users = read_users()
        return users.get(openid)
    return None

def get_user_identifier():
    """
    获取用户标识，兼容小程序和浏览器访问：
    - 小程序/Web登录用户：从请求头获取 openid
    - 未登录浏览器：返回 None（需要登录才能使用）
    """
    openid = request.headers.get('X-User-Openid')
    if openid:
        return openid
    return None

# 确保笔记文件存在
def ensure_notes_file():
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            pass

# 读取所有笔记（支持按用户筛选）
def read_notes(user_openid=None):
    ensure_notes_file()
    notes = []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                note = json.loads(line)
                # 如果指定了用户，只返回该用户的笔记
                if user_openid and note.get('user_openid') != user_openid:
                    continue
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
                        "status": "待处理",
                        "user_openid": None
                    })
    return notes

# 写入所有笔记
def write_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        for note in notes:
            f.write(json.dumps(note, ensure_ascii=False) + "\n")

# 读取标签库（持久化的用户标签）
def read_tag_library(user_openid=None):
    """读取标签库，返回 {(openid, tag)} 的列表"""
    ensure_file(TAGS_FILE)
    entries = []
    with open(TAGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if user_openid and entry.get('openid') != user_openid:
                    continue
                entries.append(entry)
            except:
                pass
    return entries

# 写入一个标签到标签库
def write_tag_to_library(openid, tag):
    """将标签写入用户的标签库（防重复）"""
    tag = tag.strip()
    if not tag:
        return
    entries = read_tag_library()
    # 防重复（同用户同名标签）
    for e in entries:
        if e.get('openid') == openid and e.get('tag') == tag:
            return
    entries.append({"openid": openid, "tag": tag})
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

@app.route("/")
def index():
    return render_template("index.html")

# ==================== 用户登录接口 ====================
@app.route("/api/login", methods=["POST"])
def login():
    """微信小程序登录"""
    data = request.get_json()
    code = data.get('code')
    user_info = data.get('userInfo', {})
    
    if not code:
        return jsonify({"error": "缺少code参数"}), 400
    
    # 如果没有配置 appid/secret，使用模拟登录（开发测试用）
    if not WX_APPID or not WX_SECRET:
        # 开发模式：使用 code 作为 openid
        openid = f"dev_{code[:20]}"
        users = read_users()
        existing = users.get(openid)
        user = {
            "openid": openid,
            "nickname": user_info.get('nickName', existing.get('nickname', '用户') if existing else '用户'),
            "avatar": user_info.get('avatarUrl', existing.get('avatar', '') if existing else ''),
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if existing:
            for key in ['role', 'user_type', 'created_at']:
                if key in existing:
                    user[key] = existing[key]
        write_user(user)
        return jsonify({
            "openid": openid,
            "nickname": user["nickname"],
            "avatar": user["avatar"],
            "role": user.get('role')
        })
    
    # 生产模式：调用微信接口获取 openid
    try:
        url = f"https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": WX_APPID,
            "secret": WX_SECRET,
            "js_code": code,
            "grant_type": "authorization_code"
        }
        resp = requests.get(url, params=params, timeout=10)
        result = resp.json()
        
        if 'openid' not in result:
            return jsonify({"error": "微信登录失败", "detail": result}), 400
        
        openid = result['openid']
        users = read_users()
        existing = users.get(openid)
        user = {
            "openid": openid,
            "nickname": user_info.get('nickName', existing.get('nickname', '微信用户') if existing else '微信用户'),
            "avatar": user_info.get('avatarUrl', existing.get('avatar', '') if existing else ''),
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if existing:
            for key in ['role', 'user_type', 'created_at']:
                if key in existing:
                    user[key] = existing[key]
        write_user(user)
        
        return jsonify({
            "openid": openid,
            "nickname": user["nickname"],
            "avatar": user["avatar"],
            "role": user.get('role')
        })
    except Exception as e:
        return jsonify({"error": "登录失败", "detail": str(e)}), 500


# ==================== 网页版用户名/密码登录 ====================
@app.route("/api/register", methods=["POST"])
def register():
    """用户注册"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    nickname = data.get('nickname', '').strip()
    
    # 验证参数
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    
    # 用户名长度限制
    if len(username) < 3 or len(username) > 20:
        return jsonify({"error": "用户名长度需在3-20个字符之间"}), 400
    
    # 密码长度限制
    if len(password) < 6:
        return jsonify({"error": "密码长度不能少于6位"}), 400
    
    # 用户名格式：只允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({"error": "用户名只能包含字母、数字和下划线"}), 400
    
    # 检查用户名是否已存在
    existing_user = find_user_by_username(username)
    if existing_user:
        return jsonify({"error": "用户名已被注册"}), 409
    
    # 创建用户
    openid = f"web_{username}"
    user = {
        "openid": openid,
        "username": username,
        "password_hash": generate_password_hash(password),
        "nickname": nickname or username,
        "avatar": "",
        "user_type": "web",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    write_user(user)
    
    return jsonify({
        "message": "注册成功",
        "openid": openid,
        "nickname": user["nickname"]
    }), 201


@app.route("/api/web-login", methods=["POST"])
def web_login():
    """网页版用户名密码登录"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    
    # 查找用户
    user = find_user_by_username(username)
    if not user:
        return jsonify({"error": "用户名或密码错误"}), 401
    
    # 检查是否是Web用户
    if user.get('user_type') != 'web':
        return jsonify({"error": "该账号为微信登录账号，请使用微信登录"}), 401
    
    # 验证密码
    if not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "用户名或密码错误"}), 401
    
    # 更新登录时间
    user['login_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_user(user)
    
    return jsonify({
        "message": "登录成功",
        "openid": user['openid'],
        "nickname": user['nickname'],
        "username": user['username'],
        "role": user.get('role', 'user')
    })

@app.route("/api/notes", methods=["POST"])
def add_note():
    data = request.get_json()
    content = data.get("content", "").strip()
    tags = data.get("tags", [])
    user_id = get_user_identifier()  # 兼容小程序和浏览器
    
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    if not content:
        return jsonify({"error": "内容不能为空"}), 400
    
    # 标签去重（保留顺序，去除空白项）
    seen = set()
    tags = [t.strip() for t in tags if t.strip() and not (t.strip() in seen or seen.add(t.strip()))]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_id = timestamp.replace(" ", "_").replace(":", "-")
    
    note = {
        "id": note_id,
        "timestamp": timestamp,
        "content": content,
        "status": "待处理",
        "user_openid": user_id,  # 绑定用户标识
        "tags": tags
    }
    
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(note, ensure_ascii=False) + "\n")
    
    # 将新标签持久化到标签库
    for tag in tags:
        write_tag_to_library(user_id, tag)
    
    return jsonify({"message": "记录成功", "timestamp": timestamp, "id": note_id}), 201

@app.route("/api/notes", methods=["GET"])
def get_notes():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    status_filter = request.args.get("status")  # 待处理, 已处理, 全部
    tag_filter = request.args.get("tag")  # 标签筛选
    user_id = get_user_identifier()  # 兼容小程序和浏览器
    
    if not user_id:
        return jsonify({"error": "请先登录", "notes": []}), 401
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    notes = read_notes(user_openid=None if is_admin else user_id)
    filtered_notes = []
    
    for note in notes:
        # 兼容旧笔记：确保 tags 字段存在
        if 'tags' not in note:
            note['tags'] = []
        
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
        
        # 标签筛选
        if tag_filter and tag_filter != "全部":
            if tag_filter not in note.get('tags', []):
                continue
        
        filtered_notes.append(note)
    
    # 按时间倒序排列
    filtered_notes.reverse()
    return jsonify({"notes": filtered_notes})

@app.route("/api/notes/<note_id>/status", methods=["PUT"])
def update_note_status(note_id):
    data = request.get_json()
    new_status = data.get("status")
    user_id = get_user_identifier()  # 兼容小程序和浏览器
    
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    if new_status not in ["待处理", "已处理"]:
        return jsonify({"error": "状态必须是'待处理'或'已处理'"}), 400
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    notes = read_notes(user_openid=None if is_admin else user_id)
    found = False
    
    for note in notes:
        if note["id"] == note_id:
            note["status"] = new_status
            found = True
            break
    
    if not found:
        return jsonify({"error": "笔记不存在"}), 404
    
    # 需要保留其他用户的笔记，所以读取全部再写入
    all_notes = read_notes()
    for note in all_notes:
        if note["id"] == note_id and (is_admin or note.get('user_openid') == user_id):
            note["status"] = new_status
            break
    write_notes(all_notes)
    return jsonify({"message": "状态更新成功"})

@app.route("/api/notes/batch/status", methods=["PUT"])
def batch_update_status():
    data = request.get_json()
    note_ids = data.get("ids", [])
    new_status = data.get("status")
    user_id = get_user_identifier()  # 兼容小程序和浏览器
    
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    if not note_ids:
        return jsonify({"error": "请选择要更新的笔记"}), 400
    
    if new_status not in ["待处理", "已处理"]:
        return jsonify({"error": "状态必须是'待处理'或'已处理'"}), 400
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    all_notes = read_notes()
    updated_count = 0
    
    for note in all_notes:
        if note["id"] in note_ids and (is_admin or note.get('user_openid') == user_id):
            note["status"] = new_status
            updated_count += 1
    
    write_notes(all_notes)
    return jsonify({"message": f"成功更新 {updated_count} 条笔记", "updated": updated_count})

@app.route("/api/notes/batch", methods=["DELETE"])
def batch_delete_notes():
    data = request.get_json()
    note_ids = data.get("ids", [])
    user_id = get_user_identifier()  # 兼容小程序和浏览器
    
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    if not note_ids:
        return jsonify({"error": "请选择要删除的笔记"}), 400
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    all_notes = read_notes()
    original_count = len(all_notes)
    
    notes = [note for note in all_notes if not (note["id"] in note_ids and (is_admin or note.get('user_openid') == user_id))]
    
    deleted_count = original_count - len(notes)
    
    write_notes(notes)
    return jsonify({"message": f"成功删除 {deleted_count} 条笔记", "deleted": deleted_count})

# ==================== 标签接口 ====================
@app.route("/api/tags", methods=["GET"])
def get_tags():
    """获取当前用户的所有标签（标签库 + 笔记中聚合，去重）"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    tags = set()
    
    # 1. 从标签库读取
    if is_admin:
        lib_entries = read_tag_library()  # 所有用户
    else:
        lib_entries = read_tag_library(user_openid=user_id)
    for entry in lib_entries:
        tags.add(entry.get('tag', ''))
    
    # 2. 从笔记中聚合（兼容旧数据）
    if is_admin:
        notes = read_notes()
    else:
        notes = read_notes(user_openid=user_id)
    for note in notes:
        for tag in note.get('tags', []):
            tags.add(tag)
    
    tags.discard('')
    return jsonify({"tags": sorted(tags)})


@app.route("/api/tags", methods=["POST"])
def add_tag():
    """添加标签到当前用户的标签库（持久化）"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    data = request.get_json()
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "标签不能为空"}), 400
    write_tag_to_library(user_id, tag)
    return jsonify({"message": "标签添加成功", "tag": tag}), 201


@app.route("/api/notes/<note_id>/tag", methods=["DELETE"])
def remove_note_tag(note_id):
    """从某条笔记中删除一个标签"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    data = request.get_json()
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "标签不能为空"}), 400
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    all_notes = read_notes()
    found = False
    for note in all_notes:
        if note["id"] == note_id and (is_admin or note.get('user_openid') == user_id):
            if 'tags' in note and tag in note['tags']:
                note['tags'] = [t for t in note['tags'] if t != tag]
                found = True
            break
    if not found:
        return jsonify({"error": "笔记或标签不存在"}), 404
    write_notes(all_notes)
    return jsonify({"message": "标签删除成功"})


@app.route("/api/notes/batch/tags", methods=["POST"])
def batch_add_tags():
    """为多条笔记批量添加标签"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    data = request.get_json()
    note_ids = data.get("ids", [])
    tags = data.get("tags", [])
    
    if not note_ids:
        return jsonify({"error": "请选择笔记"}), 400
    if not tags:
        return jsonify({"error": "请选择标签"}), 400
    
    # 标签去重
    seen = set()
    tags = [t.strip() for t in tags if t.strip() and not (t.strip() in seen or seen.add(t.strip()))]
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    all_notes = read_notes()
    updated_count = 0
    for note in all_notes:
        if note["id"] in note_ids and (is_admin or note.get('user_openid') == user_id):
            if 'tags' not in note:
                note['tags'] = []
            for tag in tags:
                if tag not in note['tags']:
                    note['tags'].append(tag)
            updated_count += 1
    
    write_notes(all_notes)
    
    # 将新标签持久化到当前用户的标签库
    for tag in tags:
        write_tag_to_library(user_id, tag)
    
    return jsonify({"message": f"成功为 {updated_count} 条笔记添加标签", "updated": updated_count})


@app.route("/api/tags/rename", methods=["PUT"])
def rename_tag():
    """重命名标签：更新标签库及所有相关笔记中的标签（仅限当前用户，admin仅更新自己创建的标签库记录但笔记按权限）"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    data = request.get_json()
    old_tag = data.get("old_tag", "").strip()
    new_tag = data.get("new_tag", "").strip()
    if not old_tag or not new_tag:
        return jsonify({"error": "旧标签和新标签不能为空"}), 400
    if old_tag == new_tag:
        return jsonify({"error": "新标签与旧标签相同"}), 400
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    # 1. 更新标签库
    lib_entries = read_tag_library()
    for entry in lib_entries:
        if entry.get('openid') == user_id and entry.get('tag') == old_tag:
            entry['tag'] = new_tag
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        for e in lib_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    
    # 2. 更新相关笔记中的标签
    all_notes = read_notes()
    updated_notes = 0
    for note in all_notes:
        # 普通用户只能改自己的笔记；admin 可以改所有
        if is_admin or note.get('user_openid') == user_id:
            if 'tags' in note and old_tag in note['tags']:
                # 替换为新标签，避免重复
                note['tags'] = [new_tag if t == old_tag else t for t in note['tags']]
                # 去重
                seen = set()
                note['tags'] = [t for t in note['tags'] if not (t in seen or seen.add(t))]
                updated_notes += 1
    write_notes(all_notes)
    
    return jsonify({"message": f"标签已重命名，更新了 {updated_notes} 条笔记", "updated_notes": updated_notes})


@app.route("/api/tags/delete", methods=["POST"])
def delete_tag():
    """删除标签：从标签库中删除，并提示是否从笔记中移除"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    data = request.get_json()
    tag = data.get("tag", "").strip()
    force = data.get("force", False)  # 是否强制从笔记中移除
    if not tag:
        return jsonify({"error": "标签不能为空"}), 400
    
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    
    # 检查是否有笔记使用该标签
    all_notes = read_notes()
    note_count = 0
    for note in all_notes:
        if is_admin or note.get('user_openid') == user_id:
            if tag in note.get('tags', []):
                note_count += 1
    
    if note_count > 0 and not force:
        return jsonify({"error": f"有 {note_count} 条笔记正在使用该标签，确认要删除吗？", "note_count": note_count, "need_confirm": True}), 409
    
    # 确认删除：从标签库移除
    lib_entries = read_tag_library()
    lib_entries = [e for e in lib_entries if not (e.get('openid') == user_id and e.get('tag') == tag)]
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        for e in lib_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    
    # 如果 force=True，从笔记中移除该标签
    removed_from_notes = 0
    if force and note_count > 0:
        for note in all_notes:
            if is_admin or note.get('user_openid') == user_id:
                if tag in note.get('tags', []):
                    note['tags'] = [t for t in note['tags'] if t != tag]
                    removed_from_notes += 1
        write_notes(all_notes)
    
    return jsonify({"message": f"标签已删除", "removed_from_notes": removed_from_notes, "note_count": note_count})


# ==================== 导出接口 ====================
def get_export_filtered_notes(user_id, start_date, end_date, selected_tags):
    """根据筛选条件获取要导出的笔记（admin 导出所有用户）"""
    user = get_current_user()
    is_admin = user and user.get('role') == 'admin'
    # admin 导出所有用户的记录；普通用户仅导出自己的
    notes = read_notes(user_openid=None if is_admin else user_id)
    
    filtered = []
    for note in notes:
        # 兼容旧笔记
        if 'tags' not in note:
            note['tags'] = []
        note_time = datetime.strptime(note["timestamp"], "%Y-%m-%d %H:%M:%S")
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            if note_time.date() < start.date():
                continue
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            if note_time.date() > end.date():
                continue
        # 标签筛选
        if selected_tags and selected_tags != "all":
            tag_list = [t.strip() for t in selected_tags.split(",") if t.strip()]
            if not any(t in note.get('tags', []) for t in tag_list):
                continue
        filtered.append(note)
    return filtered


@app.route("/api/export/preview", methods=["GET"])
def export_preview():
    """预览导出：返回符合筛选条件的笔记条数"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    selected_tags = request.args.get("tags", "all")
    filtered = get_export_filtered_notes(user_id, start_date, end_date, selected_tags)
    return jsonify({"count": len(filtered)})


@app.route("/api/export", methods=["GET"])
def export_notes():
    """导出笔记为 md，按标签分类（admin 导出所有用户）"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    selected_tags = request.args.get("tags", "all")
    
    filtered = get_export_filtered_notes(user_id, start_date, end_date, selected_tags)
    
    # 按标签分组
    tag_groups = {}  # tag -> list of contents
    untagged = []
    for note in filtered:
        tags = note.get('tags', [])
        if tags:
            for tag in tags:
                tag_groups.setdefault(tag, []).append(note['content'])
        else:
            untagged.append(note['content'])
    
    # 构建 md
    lines = []
    for tag in sorted(tag_groups.keys()):
        lines.append(f"## {tag}")
        lines.append("")
        for content in tag_groups[tag]:
            lines.append(f"- {content}")
        lines.append("")
    
    if untagged:
        lines.append("## 未分类")
        lines.append("")
        for content in untagged:
            lines.append(f"- {content}")
        lines.append("")
    
    md_content = "\n".join(lines).strip() + "\n"
    filename = f"notes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    return jsonify({"content": md_content, "filename": filename})


# ==================== 导入接口 ====================
@app.route("/api/import", methods=["POST"])
def import_notes():
    """从 md 文件导入笔记，时间记为导入时间，状态为已处理"""
    user_id = get_user_identifier()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    
    data = request.get_json()
    md_content = data.get("content", "")
    
    if not md_content.strip():
        return jsonify({"error": "导入内容为空"}), 400
    
    # 解析 md：## 标签 为标题，- 内容 为笔记
    current_tag = None
    imported_count = 0
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_notes = []
    
    for line in md_content.split("\n"):
        line = line.rstrip()
        if line.startswith("## "):
            current_tag = line[3:].strip()
            if current_tag == "未分类":
                current_tag = None
        elif line.startswith("- "):
            content = line[2:].strip()
            if content:
                note_id = (timestamp + "_" + str(imported_count)).replace(" ", "_").replace(":", "-")
                note = {
                    "id": note_id,
                    "timestamp": timestamp,
                    "content": content,
                    "status": "已处理",
                    "user_openid": user_id,
                    "tags": [current_tag] if current_tag else []
                }
                new_notes.append(note)
                imported_count += 1
    
    if new_notes:
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            for note in new_notes:
                f.write(json.dumps(note, ensure_ascii=False) + "\n")
    
    return jsonify({"message": f"成功导入 {imported_count} 条笔记", "imported": imported_count})


ensure_admin_user()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
else:
    # 生产环境由 Gunicorn 导入 main:app，不执行 app.run()
    pass
