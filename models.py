"""
数据库模型定义
支持多类型文档提取的数据库结构
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Template(db.Model):
    """提取模板模型"""
    __tablename__ = 'templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    document_type = db.Column(db.String(50), nullable=False)
    fields = db.Column(db.JSON, nullable=False)
    validation_rules = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    extractions = db.relationship('ExtractionRecord', backref='template', lazy=True)

class Document(db.Model):
    """文档模型"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.Integer)
    document_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    extractions = db.relationship('ExtractionRecord', backref='document', lazy=True)

class ExtractionRecord(db.Model):
    """提取记录模型"""
    __tablename__ = 'extraction_records'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'))
    extracted_data = db.Column(db.JSON, nullable=False)
    confidence_score = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BatchProcess(db.Model):
    """批量处理记录模型"""
    __tablename__ = 'batch_processes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')
    total_files = db.Column(db.Integer, default=0)
    processed_files = db.Column(db.Integer, default=0)
    successful_files = db.Column(db.Integer, default=0)
    failed_files = db.Column(db.Integer, default=0)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'))
    results = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class ChatMessage(db.Model):
    """即时通讯消息模型"""
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    structured_data = db.Column(db.JSON)
    status = db.Column(db.String(20), default='pending')

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'

    id = db.Column(db.String(64), primary_key=True)
    state = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    """初始化数据库"""
    db.create_all()
    print("✅ 数据库初始化完成")
