"""
模板管理API路由
支持自定义提取模板配置
"""

from flask import Blueprint, request, jsonify
from models import db, Template
from datetime import datetime

bp = Blueprint('templates', __name__, url_prefix='/api/templates')

DOCUMENT_TYPES = [
    ('invoice', '发票'),
    ('payment_slip', '付款水单/银行回单'),
    ('legal_contract', '法律合同'),
    ('lease', '租约'),
    ('maintenance', '维保记录'),
    ('facility_report', '楼宇设施报告'),
    ('custom', '自定义')
]

@bp.route('/types', methods=['GET'])
def get_document_types():
    """获取支持的文档类型列表"""
    return jsonify({
        'success': True,
        'types': DOCUMENT_TYPES
    })

@bp.route('', methods=['POST'])
def create_template():
    """创建新的提取模板"""
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'success': False, 'error': '模板名称不能为空'}), 400
    
    if not data.get('document_type'):
        return jsonify({'success': False, 'error': '文档类型不能为空'}), 400
    
    if not data.get('fields') or not isinstance(data.get('fields'), list):
        return jsonify({'success': False, 'error': '字段定义不能为空'}), 400
    
    existing = Template.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify({'success': False, 'error': '模板名称已存在'}), 400
    
    try:
        template = Template(
            name=data['name'],
            description=data.get('description', ''),
            document_type=data['document_type'],
            fields=data['fields'],
            validation_rules=data.get('validation_rules', [])
        )
        
        db.session.add(template)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'document_type': template.document_type,
                'fields': template.fields,
                'validation_rules': template.validation_rules,
                'created_at': template.created_at.isoformat()
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/<int:template_id>', methods=['GET'])
def get_template(template_id):
    """获取模板详情"""
    template = Template.query.get_or_404(template_id)
    
    return jsonify({
        'success': True,
        'template': {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'document_type': template.document_type,
            'fields': template.fields,
            'validation_rules': template.validation_rules,
            'created_at': template.created_at.isoformat(),
            'updated_at': template.updated_at.isoformat()
        }
    })

@bp.route('/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """更新模板"""
    template = Template.query.get_or_404(template_id)
    data = request.get_json()
    
    try:
        if 'name' in data:
            template.name = data['name']
        if 'description' in data:
            template.description = data['description']
        if 'fields' in data:
            template.fields = data['fields']
        if 'validation_rules' in data:
            template.validation_rules = data['validation_rules']
        
        template.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'document_type': template.document_type,
                'fields': template.fields,
                'updated_at': template.updated_at.isoformat()
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """删除模板"""
    template = Template.query.get_or_404(template_id)
    
    try:
        db.session.delete(template)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '模板已删除'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/list', methods=['GET'])
def list_templates():
    """获取模板列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    document_type = request.args.get('document_type')
    
    query = Template.query
    
    if document_type:
        query = query.filter_by(document_type=document_type)
    
    pagination = query.order_by(Template.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'templates': [{
            'id': t.id,
            'name': t.name,
            'description': t.description,
            'document_type': t.document_type,
            'fields_count': len(t.fields) if t.fields else 0,
            'created_at': t.created_at.isoformat(),
            'updated_at': t.updated_at.isoformat()
        } for t in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })

@bp.route('/<int:template_id>/duplicate', methods=['POST'])
def duplicate_template(template_id):
    """复制模板"""
    original = Template.query.get_or_404(template_id)
    data = request.get_json()
    
    new_name = data.get('new_name', f"{original.name} (副本)")
    
    existing = Template.query.filter_by(name=new_name).first()
    if existing:
        return jsonify({'success': False, 'error': '模板名称已存在'}), 400
    
    try:
        new_template = Template(
            name=new_name,
            description=original.description,
            document_type=original.document_type,
            fields=original.fields,
            validation_rules=original.validation_rules
        )
        
        db.session.add(new_template)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'template': {
                'id': new_template.id,
                'name': new_template.name,
                'document_type': new_template.document_type
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/generate-from-description', methods=['POST'])
def generate_template_from_description():
    """根据自然语言描述生成模板"""
    data = request.get_json()
    
    description = data.get('description', '')
    document_type = data.get('document_type', 'custom')
    
    if not description:
        return jsonify({'success': False, 'error': '描述不能为空'}), 400
    
    from services.template_generator import TemplateGenerator
    generator = TemplateGenerator()
    
    try:
        template_data = generator.generate_from_description(description, document_type)
        
        return jsonify({
            'success': True,
            'template': template_data
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
