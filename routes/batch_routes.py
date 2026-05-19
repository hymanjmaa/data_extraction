"""
批量处理API路由
支持多文件并行处理
"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import zipfile
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import db, Document, BatchProcess, Template, ExtractionRecord
from services.extraction_engine import AIExtractionEngine
from utils.document_parser import DocumentParser
from datetime import datetime
from pathlib import Path

bp = Blueprint('batch', __name__, url_prefix='/api/batch')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _extract_zip_to_documents(zip_path: str, template: Template, uploaded_files: list[int], errors: list[str]):
    supported_exts = {e for e in ALLOWED_EXTENSIONS if e != 'zip'}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > 200:
            errors.append('ZIP内文件过多(>200)，已拒绝处理')
            return

        total_size = sum([i.file_size for i in infos])
        if total_size > 200 * 1024 * 1024:
            errors.append('ZIP解压后总大小超过200MB，已拒绝处理')
            return

        for info in infos:
            inner_name = Path(info.filename).name
            if not inner_name:
                continue
            inner_ext = inner_name.rsplit('.', 1)[1].lower() if '.' in inner_name else ''
            if inner_ext not in supported_exts:
                continue

            try:
                safe_inner_name = secure_filename(inner_name)
                unique_filename = f"{uuid.uuid4().hex}_{safe_inner_name}"
                file_path = os.path.join('uploads', unique_filename)

                with zf.open(info, 'r') as src, open(file_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

                file_size = os.path.getsize(file_path)

                document = Document(
                    filename=unique_filename,
                    original_filename=inner_name,
                    file_path=file_path,
                    file_type=inner_ext,
                    file_size=file_size,
                    status='uploaded',
                    document_type=template.document_type
                )

                db.session.add(document)
                db.session.commit()

                uploaded_files.append(document.id)
            except Exception as e:
                errors.append(f"{inner_name}: {str(e)}")

@bp.route('/upload', methods=['POST'])
def upload_batch():
    """上传批量文件"""
    
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400
    
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({'success': False, 'error': '文件列表为空'}), 400
    
    data = request.form
    template_id = data.get('template_id')
    batch_name = data.get('name', f"批量任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if not template_id:
        return jsonify({'success': False, 'error': '缺少template_id'}), 400
    
    template = Template.query.get(int(template_id))
    if not template:
        return jsonify({'success': False, 'error': '模板不存在'}), 400
    
    try:
        batch = BatchProcess(
            name=batch_name,
            total_files=0,
            template_id=template.id,
            status='uploading'
        )
        db.session.add(batch)
        db.session.commit()
        
        uploaded_files = []
        errors = []
        
        for file in files:
            if file.filename == '':
                continue
            
            if not allowed_file(file.filename):
                errors.append(f"{file.filename}: 不支持的文件类型")
                continue
            
            try:
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                if ext == 'zip':
                    zip_filename = f"{uuid.uuid4().hex}.zip"
                    zip_path = os.path.join('uploads', zip_filename)
                    file.save(zip_path)
                    try:
                        _extract_zip_to_documents(zip_path, template, uploaded_files, errors)
                    finally:
                        try:
                            if os.path.exists(zip_path):
                                os.remove(zip_path)
                        except Exception:
                            pass
                else:
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = os.path.join('uploads', unique_filename)
                    
                    file.save(file_path)
                    
                    file_size = os.path.getsize(file_path)
                    file_type = ext
                    
                    document = Document(
                        filename=unique_filename,
                        original_filename=filename,
                        file_path=file_path,
                        file_type=file_type,
                        file_size=file_size,
                        status='uploaded',
                        document_type=template.document_type
                    )
                    
                    db.session.add(document)
                    db.session.commit()
                    
                    uploaded_files.append(document.id)
            
            except Exception as e:
                errors.append(f"{file.filename}: {str(e)}")
        
        batch.total_files = len(uploaded_files)
        batch.processed_files = 0
        batch.successful_files = 0
        batch.failed_files = len(errors)
        batch.status = 'pending'
        batch.results = {'document_ids': uploaded_files}
        db.session.commit()
        
        return jsonify({
            'success': True,
            'batch': {
                'id': batch.id,
                'name': batch.name,
                'total_files': batch.total_files,
                'uploaded_files': uploaded_files,
                'errors': errors
            }
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/upload-zip', methods=['POST'])
def upload_batch_zip():
    """上传ZIP包批量文件"""
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有ZIP文件'}), 400
    
    zip_file = request.files['file']
    data = request.form
    template_id = data.get('template_id')
    batch_name = data.get('name', f"批量任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if not template_id:
        return jsonify({'success': False, 'error': '缺少template_id'}), 400
    
    template = Template.query.get(int(template_id))
    if not template:
        return jsonify({'success': False, 'error': '模板不存在'}), 400
    
    try:
        batch = BatchProcess(
            name=batch_name,
            total_files=0,
            template_id=template.id,
            status='uploading'
        )
        db.session.add(batch)
        db.session.commit()
        
        zip_filename = f"{uuid.uuid4().hex}.zip"
        zip_path = os.path.join('uploads', zip_filename)
        zip_file.save(zip_path)
        
        uploaded_files = []
        errors = []
        
        _extract_zip_to_documents(zip_path, template, uploaded_files, errors)
        
        os.remove(zip_path)
        
        batch.total_files = len(uploaded_files)
        batch.processed_files = 0
        batch.successful_files = 0
        batch.failed_files = len(errors)
        batch.status = 'pending'
        batch.results = {'document_ids': uploaded_files}
        db.session.commit()
        
        return jsonify({
            'success': True,
            'batch': {
                'id': batch.id,
                'name': batch.name,
                'total_files': batch.total_files,
                'uploaded_files': uploaded_files,
                'errors': errors
            }
        }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/<int:batch_id>/process', methods=['POST'])
def process_batch(batch_id):
    """开始批量处理"""
    batch = BatchProcess.query.get_or_404(batch_id)
    
    if batch.status not in ['pending', 'paused']:
        return jsonify({'success': False, 'error': '批次状态不允许处理'}), 400
    
    data = request.get_json() or {}
    max_workers = data.get('max_workers', 4)
    
    try:
        batch.status = 'processing'
        db.session.commit()
        
        documents = Document.query.filter_by(
            document_type=batch.template.document_type
        ).filter(
            Document.id.in_([d.id for d in batch.documents])
        ).all() if hasattr(batch, 'documents') else []
        
        if not documents:
            document_ids = batch.results.get('document_ids', []) if batch.results else []
            documents = Document.query.filter(Document.id.in_(document_ids)).all()
        
        engine = AIExtractionEngine()
        results = []
        
        def process_document(doc):
            try:
                parsed_doc = DocumentParser.auto_parse(doc.file_path)
                
                if not parsed_doc.get('success'):
                    return {
                        'document_id': doc.id,
                        'success': False,
                        'error': parsed_doc.get('error')
                    }
                
                extract_text = parsed_doc.get('text', '')
                
                result = engine.extract(
                    document_text=extract_text,
                    template={
                        'fields': batch.template.fields,
                        'validation_rules': batch.template.validation_rules,
                        'document_type': batch.template.document_type
                    }
                )
                
                extraction = ExtractionRecord(
                    document_id=doc.id,
                    template_id=batch.template_id,
                    extracted_data=result.get('data', {}),
                    confidence_score=result.get('confidence', 0.0),
                    status='completed' if result.get('success') else 'failed',
                    error_message=result.get('error')
                )
                
                db.session.add(extraction)
                doc.status = 'extracted' if result.get('success') else 'failed'
                db.session.commit()
                
                return {
                    'document_id': doc.id,
                    'success': result.get('success', False),
                    'confidence': result.get('confidence', 0.0),
                    'error': result.get('error')
                }
            
            except Exception as e:
                return {
                    'document_id': doc.id,
                    'success': False,
                    'error': str(e)
                }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_doc = {executor.submit(process_document, doc): doc for doc in documents}
            
            for future in as_completed(future_to_doc):
                result = future.result()
                results.append(result)
                
                batch.processed_files += 1
                
                if result.get('success'):
                    batch.successful_files += 1
                else:
                    batch.failed_files += 1
                
                db.session.commit()
        
        batch.results = {
            'results': results,
            'document_ids': [r['document_id'] for r in results]
        }
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'batch': {
                'id': batch.id,
                'status': batch.status,
                'total_files': batch.total_files,
                'processed_files': batch.processed_files,
                'successful_files': batch.successful_files,
                'failed_files': batch.failed_files,
                'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
            }
        }), 200
    
    except Exception as e:
        batch.status = 'failed'
        db.session.commit()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/<int:batch_id>', methods=['GET'])
def get_batch(batch_id):
    """获取批次详情"""
    batch = BatchProcess.query.get_or_404(batch_id)
    
    return jsonify({
        'success': True,
        'batch': {
            'id': batch.id,
            'name': batch.name,
            'status': batch.status,
            'total_files': batch.total_files,
            'processed_files': batch.processed_files,
            'successful_files': batch.successful_files,
            'failed_files': batch.failed_files,
            'template_id': batch.template_id,
            'template_name': batch.template.name if batch.template else None,
            'results': batch.results,
            'created_at': batch.created_at.isoformat(),
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
        }
    })

@bp.route('/<int:batch_id>/results', methods=['GET'])
def get_batch_results(batch_id):
    """获取批次处理结果"""
    batch = BatchProcess.query.get_or_404(batch_id)
    
    if not batch.results:
        return jsonify({
            'success': False,
            'error': '批次处理未完成或无结果'
        }), 400
    
    document_ids = (batch.results or {}).get('document_ids') or []
    if not document_ids:
        rs = (batch.results or {}).get('results') or []
        document_ids = [r.get('document_id') for r in rs if r.get('document_id')]
    documents = Document.query.filter(Document.id.in_(document_ids)).all()
    
    extractions = ExtractionRecord.query.filter(
        ExtractionRecord.document_id.in_(document_ids)
    ).all()
    
    return jsonify({
        'success': True,
        'results': {
            'batch_info': {
                'id': batch.id,
                'name': batch.name,
                'status': batch.status,
                'total_files': batch.total_files,
                'successful_files': batch.successful_files,
                'failed_files': batch.failed_files
            },
            'documents': [{
                'id': doc.id,
                'filename': doc.original_filename,
                'status': doc.status,
                'extractions': [e.extracted_data for e in extractions if e.document_id == doc.id]
            } for doc in documents]
        }
    }), 200

@bp.route('/<int:batch_id>/export', methods=['GET'])
def export_batch_results(batch_id):
    """导出批次处理结果"""
    batch = BatchProcess.query.get_or_404(batch_id)
    export_format = request.args.get('format', 'json')
    
    if not batch.results:
        return jsonify({'success': False, 'error': '批次处理未完成'}), 400
    
    document_ids = (batch.results or {}).get('document_ids') or []
    if not document_ids:
        rs = (batch.results or {}).get('results') or []
        document_ids = [r.get('document_id') for r in rs if r.get('document_id')]
    extractions = ExtractionRecord.query.filter(
        ExtractionRecord.document_id.in_(document_ids)
    ).all()
    
    if export_format == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        if extractions:
            headers = list(extractions[0].extracted_data.keys())
            writer.writerow(['Document ID', 'Filename'] + headers)
            
            for extraction in extractions:
                doc = Document.query.get(extraction.document_id)
                row = [extraction.document_id, doc.original_filename if doc else '']
                row.extend([extraction.extracted_data.get(h, '') for h in headers])
                writer.writerow(row)
        
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=batch_{batch.id}_results.csv'
        }
    
    else:
        return jsonify({
            'success': True,
            'format': 'json',
            'data': [{
                'document_id': e.document_id,
                'data': e.extracted_data,
                'confidence': e.confidence_score,
                'status': e.status
            } for e in extractions]
        }), 200

@bp.route('/list', methods=['GET'])
def list_batches():
    """获取批次列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = BatchProcess.query
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(BatchProcess.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'batches': [{
            'id': b.id,
            'name': b.name,
            'status': b.status,
            'total_files': b.total_files,
            'processed_files': b.processed_files,
            'successful_files': b.successful_files,
            'failed_files': b.failed_files,
            'template_id': b.template_id,
            'created_at': b.created_at.isoformat(),
            'completed_at': b.completed_at.isoformat() if b.completed_at else None
        } for b in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })
