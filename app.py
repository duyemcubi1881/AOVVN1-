# backend/aov/app.py
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import random
import string
import json # Để xử lý trường used_by (JSON string)
from flask_cors import CORS # Cần thiết cho việc gọi API từ frontend/client app
import os # Để lấy base directory

app = Flask(__name__, template_folder='templates') # Chỉ định thư mục templates
CORS(app) # Cho phép các origin khác gọi API của bạn (quan trọng cho frontend)

# Cấu hình Database
# Đường dẫn tuyệt đối cho database file để tránh lỗi khi chạy từ các thư mục khác
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'keys.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Định nghĩa Model cho Key trong Database
class Key(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_string = db.Column(db.String(20), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    hwid = db.Column(db.String(100), nullable=True)
    used_by = db.Column(db.Text, default="[]") # Dùng Text thay vì String nếu dữ liệu có thể dài
    is_banned = db.Column(db.Boolean, default=False)
    violations = db.Column(db.Integer, default=0)
    created_by = db.Column(db.String(50), nullable=True) # ID của người tạo (Discord user ID)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Key {self.key_string}>"

# --- HÀM PHỤ TRỢ ---
def generate_key_string():
    return "AOV-VN-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# --- API ENDPOINTS ---

# Trang chủ của Web Admin Panel
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint để lấy tất cả key (cho bảng trong admin panel)
@app.route('/api/keys', methods=['GET'])
def get_all_keys():
    keys = Key.query.all()
    key_list = []
    for key in keys:
        key_list.append({
            "key_string": key.key_string,
            "expires_at": key.expires_at.isoformat(),
            "hwid": key.hwid,
            "used_by": json.loads(key.used_by),
            "is_banned": key.is_banned,
            "violations": key.violations,
            "created_by": key.created_by,
            "created_at": key.created_at.isoformat()
        })
    return jsonify(key_list), 200


@app.route('/api/createkey', methods=['POST'])
def create_key():
    data = request.get_json()
    days = data.get('days', 3)
    created_by = data.get('created_by', 'Unknown')

    key_str = generate_key_string()
    expires = datetime.utcnow() + timedelta(days=days)

    new_key = Key(
        key_string=key_str,
        expires_at=expires,
        created_by=created_by
    )
    db.session.add(new_key)
    db.session.commit()

    return jsonify({"message": "Key created successfully", "key": key_str, "expires": expires.isoformat()}), 200

@app.route('/api/deletekey', methods=['POST'])
def delete_key():
    data = request.get_json()
    key_str = data.get('key')
    if not key_str:
        return jsonify({"error": "Key is required"}), 400

    key = Key.query.filter_by(key_string=key_str).first()
    if key:
        db.session.delete(key)
        db.session.commit()
        return jsonify({"message": f"Key {key_str} deleted successfully"}), 200
    return jsonify({"error": "Key not found"}), 404

@app.route('/api/redeem', methods=['POST'])
def redeem_key():
    data = request.get_json()
    key_str = data.get('key')
    hwid = data.get('hwid')
    user_id = data.get('user_id')

    if not all([key_str, hwid, user_id]):
        return jsonify({"error": "Key, HWID, and User ID are required"}), 400

    key = Key.query.filter_by(key_string=key_str).first()

    if not key:
        return jsonify({"error": "Key does not exist"}), 404

    if key.is_banned:
        return jsonify({"error": "Key is banned and cannot be used"}), 403

    if key.expires_at < datetime.utcnow():
        key.is_banned = True
        db.session.commit()
        return jsonify({"error": "Key has expired and been banned"}), 403

    # Kiểm tra HWID
    if key.hwid and key.hwid != hwid:
        key.is_banned = True
        key.violations += 1
        db.session.commit()
        leak_message = (
            f"🚨 PHÁT HIỆN LEAK KEY `{key.key_string}`!\n"
            f"HWID gốc: `{key.hwid}`\n"
            f"HWID lạ: `{hwid}`\n"
            f"❌ Key đã bị BAN ngay lập tức!"
        )
        return jsonify({"error": leak_message, "type": "leak"}), 403

    # Gán HWID lần đầu
    if not key.hwid:
        key.hwid = hwid

    used_by_list = json.loads(key.used_by)
    if user_id not in used_by_list:
        used_by_list.append(user_id)
        key.used_by = json.dumps(used_by_list)

    db.session.commit()
    return jsonify({"message": "Key activated successfully", "key": key_str, "hwid": hwid}), 200

@app.route('/api/checkkey', methods=['GET'])
def check_key():
    key_str = request.args.get('key')
    if not key_str:
        return jsonify({"error": "Key is required"}), 400

    key = Key.query.filter_by(key_string=key_str).first()
    if not key:
        return jsonify({"error": "Key not found"}), 404

    status = "Bình thường" if not key.is_banned else "Đã ban"
    expires_info = key.expires_at.isoformat()
    hwid_info = key.hwid if key.hwid else "Chưa gán"
    used_by_info = json.loads(key.used_by) if key.used_by else []

    return jsonify({
        "key": key.key_string,
        "status": status,
        "expires": expires_info,
        "hwid": hwid_info,
        "used_by": used_by_info,
        "is_banned": key.is_banned, # Thêm trường này để frontend dễ xử lý
        "violations": key.violations,
        "created_by": key.created_by,
        "created_at": key.created_at.isoformat()
    }), 200

@app.route('/api/ban', methods=['POST'])
def ban_key():
    data = request.get_json()
    key_str = data.get('key')
    if not key_str:
        return jsonify({"error": "Key is required"}), 400

    key = Key.query.filter_by(key_string=key_str).first()
    if key:
        key.is_banned = True
        db.session.commit()
        return jsonify({"message": f"Key {key_str} has been banned"}), 200
    return jsonify({"error": "Key not found"}), 404

@app.route('/api/unban', methods=['POST'])
def unban_key():
    data = request.get_json()
    key_str = data.get('key')
    if not key_str:
        return jsonify({"error": "Key is required"}), 400

    key = Key.query.filter_by(key_string=key_str).first()
    if key:
        key.is_banned = False
        db.session.commit()
        return jsonify({"message": f"Key {key_str} has been unbanned"}), 200
    return jsonify({"error": "Key not found"}), 404

# Khởi tạo database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
