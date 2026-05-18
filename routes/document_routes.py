"""
文档处理API路由
"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
from models import db, Document, ExtractionRecord, Template
from services.extraction_engine import AIExtractionEngine
from utils.document_parser import DocumentParser
import uuid
from datetime import datetime

bp = Blueprint('documents', __name__, url_prefix='/api/documents')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/upload', methods=['POST'])
def upload_document():
    """上传单个文档"""
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的文件类型'}), 400
    
    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join('uploads', unique_filename)
        
        file.save(file_path)
        
        file_size = os.path.getsize(file_path)
        file_type = filename.rsplit('.', 1)[1].lower()
        
        document = Document(
            filename=unique_filename,
            original_filename=filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            status='uploaded'
        )
        
        db.session.add(document)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'document': {
                'id': document.id,
                'filename': document.original_filename,
                'file_type': document.file_type,
                'file_size': document.file_size,
                'status': document.status
            }
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    """获取文档信息"""
    document = Document.query.get_or_404(doc_id)
    
    return jsonify({
        'success': True,
        'document': {
            'id': document.id,
            'filename': document.original_filename,
            'file_type': document.file_type,
            'file_size': document.file_size,
            'status': document.status,
            'document_type': document.document_type,
            'created_at': document.created_at.isoformat()
        }
    })

@bp.route('/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档"""
    document = Document.query.get_or_404(doc_id)
    
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        db.session.delete(document)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '文档已删除'}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/<int:doc_id>/extract', methods=['POST'])
def extract_document(doc_id):
    """提取文档数据"""
    document = Document.query.get_or_404(doc_id)
    
    data = request.get_json()
    template_id = data.get('template_id')
    context = data.get('context', {})
    
    if not template_id:
        return jsonify({'success': False, 'error': '缺少template_id'}), 400
    
    template = Template.query.get_or_404(template_id)
    
    try:
        parsed_doc = DocumentParser.auto_parse(document.file_path)
        
        if not parsed_doc.get('success'):
            return jsonify({
                'success': False,
                'error': f'文档解析失败: {parsed_doc.get("error")}'
            }), 500
        
        document_type = template.document_type
        
        if document_type == '发票' or document_type == 'invoice':
            extract_text = parsed_doc.get('text', '')
        elif document_type == '图片':
            extract_text = f"[图片文件]\n{parsed_doc.get('text', '')}"
        else:
            extract_text = parsed_doc.get('text', '')
        
        engine = AIExtractionEngine()
        result = engine.extract(
            document_text=extract_text,
            template={
                'fields': template.fields,
                'validation_rules': template.validation_rules,
                'document_type': template.document_type
            },
            context=context
        )
        
        document.status = 'extracted'
        document.document_type = template.document_type
        
        extraction = ExtractionRecord(
            document_id=document.id,
            template_id=template.id,
            extracted_data=result.get('data', {}),
            confidence_score=result.get('confidence', 0.0),
            status='completed' if result.get('success') else 'failed',
            error_message=result.get('error')
        )
        
        db.session.add(extraction)
        db.session.commit()
        
        return jsonify({
            'success': result.get('success', False),
            'extraction': {
                'id': extraction.id,
                'data': extraction.extracted_data,
                'confidence': extraction.confidence_score,
                'status': extraction.status,
                'error': extraction.error_message
            }
        }), 200
    
    except Exception as e:
        document.status = 'error'
        db.session.commit()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<int:doc_id>/extractions', methods=['GET'])
def get_extractions(doc_id):
    """获取文档的所有提取记录"""
    document = Document.query.get_or_404(doc_id)
    
    extractions = ExtractionRecord.query.filter_by(document_id=doc_id).order_by(
        ExtractionRecord.created_at.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'extractions': [{
            'id': e.id,
            'template_id': e.template_id,
            'template_name': e.template.name if e.template else None,
            'data': e.extracted_data,
            'confidence': e.confidence_score,
            'status': e.status,
            'error': e.error_message,
            'created_at': e.created_at.isoformat()
        } for e in extractions]
    })

@bp.route('/list', methods=['GET'])
def list_documents():
    """获取文档列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = Document.query
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Document.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'documents': [{
            'id': d.id,
            'filename': d.original_filename,
            'file_type': d.file_type,
            'file_size': d.file_size,
            'status': d.status,
            'document_type': d.document_type,
            'created_at': d.created_at.isoformat()
        } for d in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })
