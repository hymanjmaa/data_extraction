"""
Flask应用主文件
文档数据提取系统 - Vue + Flask + OpenRouter + SQLite
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data_extraction.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from models import db, init_db
db.init_app(app)

from routes import document_routes, template_routes, batch_routes, chat_routes
from models import Document, Template, ExtractionRecord

app.register_blueprint(document_routes.bp)
app.register_blueprint(template_routes.bp)
app.register_blueprint(batch_routes.bp)
app.register_blueprint(chat_routes.bp)

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取系统统计信息"""
    return jsonify({
        'total_documents': Document.query.count(),
        'total_templates': Template.query.count(),
        'total_extractions': ExtractionRecord.query.count(),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    with app.app_context():
        init_db()
    print("🚀 文档数据提取系统已启动")
    print("📊 健康检查: http://localhost:5000/api/health")
    app.run(debug=True, host='0.0.0.0', port=5000)
