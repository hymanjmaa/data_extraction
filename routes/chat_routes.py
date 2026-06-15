"""
即时通讯/碎片信息处理API路由
"""

from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import os
import uuid
import zipfile
import shutil
from models import db, ChatMessage, ChatSession, Template, Document, ExtractionRecord, BatchProcess
from services.extraction_engine import AIExtractionEngine
from services.lease_pdf_extractor import extract_lease_from_pdfs
from services.lease_rule_to_template import lease_rules_to_template_fields
from services.template_generator import TemplateGenerator
from utils.document_parser import DocumentParser
from datetime import datetime
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

bp = Blueprint('chat', __name__, url_prefix='/api/chat')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx', 'zip'}

def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _ensure_upload_dir():
    os.makedirs('uploads', exist_ok=True)

def _get_or_create_session(session_id: str | None) -> ChatSession:
    if session_id:
        session = ChatSession.query.get(session_id)
        if session:
            return session
    new_id = uuid.uuid4().hex
    session = ChatSession(id=new_id, state={})
    db.session.add(session)
    db.session.commit()
    return session

def _save_session_state(session: ChatSession, state: dict):
    session.state = state
    session.updated_at = datetime.utcnow()
    db.session.commit()

def _parse_command(engine: AIExtractionEngine, user_text: str, session_state: dict, templates: list[dict]) -> dict:
    def _empty_slots() -> dict:
        return {
            'template_id': None,
            'template_name': None,
            'template_description': None,
            'template_save_name': None,
            'batch_id': None,
            'export_format': None
        }

    def _rule_based_parse(text: str) -> dict:
        t = (text or '').strip()
        tl = t.lower()
        slots = _empty_slots()

        if not t:
            return {'intent': 'extract_documents', 'slots': slots}

        if tl in ['帮助', 'help', '?', '？']:
            return {'intent': 'help', 'slots': slots}
        if tl in ['取消', '算了', '停止', 'cancel', 'exit', '退出']:
            return {'intent': 'cancel', 'slots': slots}

        if '统计' in t:
            return {'intent': 'stats', 'slots': slots}
        if '列出模板' in t or '模板列表' in t:
            return {'intent': 'list_templates', 'slots': slots}

        import re

        if '租约' in t and ('提取' in t or '解析' in t or '导入' in t) and ('pdf' in tl or '合同' in t or '规则' in t):
            return {'intent': 'lease_pdf_extract', 'slots': slots}

        if '导出' in t and ('批次' in t or 'batch' in tl):
            m = re.search(r'(?:批次|batch)\s*([0-9]+)', t, re.IGNORECASE)
            if m:
                slots['batch_id'] = int(m.group(1))
            else:
                m = re.search(r'\b([0-9]+)\b', t)
                if m:
                    slots['batch_id'] = int(m.group(1))
            if 'csv' in tl:
                slots['export_format'] = 'csv'
            elif 'json' in tl:
                slots['export_format'] = 'json'
            return {'intent': 'export_batch', 'slots': slots}

        if '生成模板' in t or '创建模板' in t:
            parts = re.split(r'[:：]', t, maxsplit=1)
            if len(parts) == 2:
                slots['template_description'] = parts[1].strip()
            else:
                slots['template_description'] = re.sub(r'(生成模板|创建模板)', '', t).strip()
            return {'intent': 'generate_template', 'slots': slots}

        if '保存模板' in t:
            m = re.search(r'(?:名称|name)\s*=\s*([^\s]+)', t, re.IGNORECASE)
            if m:
                slots['template_save_name'] = m.group(1).strip()
            else:
                v = re.sub(r'保存模板', '', t).strip()
                if v:
                    slots['template_save_name'] = v
            return {'intent': 'save_template', 'slots': slots}

        if '提取' in t or '解析' in t:
            template_slots = _try_parse_template_from_text(t)
            slots['template_id'] = template_slots.get('template_id')
            slots['template_name'] = template_slots.get('template_name')
            if '批量' in t or '一堆' in t or '多个' in t or '多份' in t or 'zip' in tl:
                return {'intent': 'batch_extract', 'slots': slots}
            return {'intent': 'extract_documents', 'slots': slots}

        return {'intent': 'help', 'slots': slots}

    template_lines = "\n".join([f"- {t['id']}: {t['name']}" for t in templates]) if templates else "无"
    state_hint = json.dumps(session_state, ensure_ascii=False)
    prompt = f"""你是一个系统指令解析器。你只输出JSON，不要输出其它文本。

你要把用户的自然语言消息解析成一个“意图(intent)”和“参数(slots)”。

当前会话状态(session_state):
{state_hint}

当前模板列表(templates):
{template_lines}

支持的intent:
- help: 展示可用指令
- stats: 系统统计
- list_templates: 列出模板
- generate_template: 根据描述生成模板草稿
- save_template: 保存上一条生成的模板草稿
- cancel: 取消当前待办(例如取消模板草稿)
- extract_documents: 对附件文件做提取(需要template_id或template_name)
- batch_extract: 对多附件文件做批量提取(需要template_id或template_name)
- export_batch: 导出批次结果(需要batch_id与format)
- lease_pdf_extract: 上传租约规则xlsx与合同PDF并提取并生成输出Excel

slots字段定义:
- template_id: number|null
- template_name: string|null
- template_description: string|null
- template_save_name: string|null
- batch_id: number|null
- export_format: string|null

规则:
1) 如果用户表达“生成模板/创建模板”，intent=generate_template，并把描述写入template_description
2) 如果用户表达“保存模板”，intent=save_template，并从用户消息中抽取template_save_name(如有)
3) 如果用户表达“提取/解析附件/文件”，intent=extract_documents 或 batch_extract(多文件/批量/一堆/zip)
4) 如果缺少关键参数，仍返回intent，但对应slot为null

输出JSON示例:
{{"intent":"list_templates","slots":{{"template_id":null,"template_name":null,"template_description":null,"template_save_name":null,"batch_id":null,"export_format":null}}}}

用户消息:
{user_text}
"""
    parsed = engine.run_json_prompt(prompt)
    rule_parsed = _rule_based_parse(user_text)

    if not parsed.get('success') or not isinstance(parsed.get('data'), dict):
        return rule_parsed

    data = parsed['data']
    intent = data.get('intent') or 'help'
    slots = data.get('slots') or {}

    if rule_parsed.get('intent') in ['generate_template', 'generate_template_from_rules', 'save_template']:
        return rule_parsed

    return {'intent': intent, 'slots': slots}

def _find_template(slots: dict) -> Template | None:
    template_id = slots.get('template_id')
    template_name = slots.get('template_name')
    if template_id:
        try:
            return Template.query.get(int(template_id))
        except Exception:
            return None
    if template_name:
        return Template.query.filter(Template.name == template_name).first()
    return None

def _text_is_cancel(text: str) -> bool:
    t = (text or '').strip().lower()
    return t in ['取消', '算了', '停止', 'cancel', 'exit', '退出']

def _text_is_help(text: str) -> bool:
    t = (text or '').lower().strip()
    return t in ['帮助', 'help', '?', '？', '指令']

def _text_is_generate(text: str) -> bool:
    t = (text or '').lower().strip()
    return '生成模板' in t or '创建模板' in t or '按规则' in t or '生成' in t

def _text_is_confirm(text: str) -> bool:
    t = (text or '').strip().lower()
    return t in ['确认', '是', '好的', '好', 'ok', 'okay', 'yes', 'y']

def _try_parse_template_from_text(text: str) -> dict:
    t = (text or '').strip()
    slots: dict = {'template_id': None, 'template_name': None}
    if not t:
        return slots

    import re
    m = re.search(r'(?:模板|template)\s*=\s*([^\s]+)', t, re.IGNORECASE)
    if m:
        v = m.group(1).strip()
        if v.isdigit():
            slots['template_id'] = int(v)
        else:
            slots['template_name'] = v
        return slots

    m = re.search(r'(?:ID|id)\s*=\s*(\d+)', t)
    if m:
        slots['template_id'] = int(m.group(1))
        return slots

    if t.isdigit():
        slots['template_id'] = int(t)
        return slots

    slots['template_name'] = t
    return slots

def _render_template_choices(templates: list[Template]) -> str:
    if not templates:
        return '当前还没有模板。你可以说“生成模板：...”来创建。'
    lines = []
    for t in templates[:10]:
        lines.append(f"- {t.id}: {t.name}")
    more = '' if len(templates) <= 10 else f"\n(还有 {len(templates) - 10} 个模板未展示，可继续“列出模板”)"
    return "可选模板：\n" + "\n".join(lines) + more

def _extract_saved_file(file_path: str, unique_filename: str, original_filename: str, template: Template) -> dict:
    file_size = os.path.getsize(file_path)
    file_type = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''

    document = Document(
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        status='uploaded',
        document_type=template.document_type
    )
    db.session.add(document)
    db.session.commit()

    parsed_doc = DocumentParser.auto_parse(document.file_path)
    if not parsed_doc.get('success'):
        document.status = 'failed'
        db.session.commit()
        return {
            'document_id': document.id,
            'filename': original_filename,
            'success': False,
            'error': parsed_doc.get('error')
        }

    engine = AIExtractionEngine()
    result = engine.extract(
        document_text=parsed_doc.get('text', ''),
        template={
            'fields': template.fields,
            'validation_rules': template.validation_rules,
            'document_type': template.document_type
        }
    )

    extraction = ExtractionRecord(
        document_id=document.id,
        template_id=template.id,
        extracted_data=result.get('data', {}),
        confidence_score=result.get('confidence', 0.0),
        status='completed' if result.get('success') else 'failed',
        error_message=result.get('error')
    )
    db.session.add(extraction)
    document.status = 'extracted' if result.get('success') else 'failed'
    db.session.commit()

    return {
        'document_id': document.id,
        'filename': original_filename,
        'success': bool(result.get('success')),
        'confidence': result.get('confidence', 0.0),
        'data': extraction.extracted_data,
        'error': extraction.error_message
    }

def _extract_zip_file(zip_path: str, zip_name: str, template: Template) -> list[dict]:
    supported_exts = {e for e in ALLOWED_EXTENSIONS if e != 'zip'}
    results: list[dict] = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            if len(infos) > 200:
                return [{'filename': zip_name, 'success': False, 'error': 'ZIP内文件过多(>200)，已拒绝处理'}]

            total_size = sum([i.file_size for i in infos])
            if total_size > 200 * 1024 * 1024:
                return [{'filename': zip_name, 'success': False, 'error': 'ZIP解压后总大小超过200MB，已拒绝处理'}]

            for info in infos:
                inner_name = Path(info.filename).name
                if not inner_name:
                    continue
                inner_ext = inner_name.rsplit('.', 1)[1].lower() if '.' in inner_name else ''
                if inner_ext not in supported_exts:
                    continue

                safe_inner_name = secure_filename(inner_name)
                unique_filename = f"{uuid.uuid4().hex}_{safe_inner_name}"
                file_path = os.path.join('uploads', unique_filename)

                with zf.open(info, 'r') as src, open(file_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

                results.append(_extract_saved_file(file_path, unique_filename, inner_name, template))

    except Exception as e:
        return [{'filename': zip_name, 'success': False, 'error': str(e)}]

    if not results:
        return [{'filename': zip_name, 'success': False, 'error': 'ZIP内未找到可处理的文件'}]

    return results

def _extract_one_file(file_storage, template: Template) -> dict | list[dict]:
    _ensure_upload_dir()

    original_name = file_storage.filename or 'unknown'
    original_ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
    
    safe_stem = secure_filename(Path(original_name).stem) or 'file'
    safe_ext = original_ext if original_ext in ALLOWED_EXTENSIONS else ''
    filename = f"{safe_stem}.{safe_ext}" if safe_ext else f"{safe_stem}"
    
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join('uploads', unique_filename)
    file_storage.save(file_path)

    ext = original_ext
    if ext == 'zip':
        try:
            results = _extract_zip_file(file_path, original_name, template)
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
        return results

    return _extract_saved_file(file_path, unique_filename, original_name, template)

@bp.route('/agent/message', methods=['POST'])
def agent_message():
    content = request.form.get('content', '').strip()
    source = request.form.get('source', 'unknown')
    sender = request.form.get('sender') or None
    session_id = request.form.get('session_id')
    files_in_request = request.files.getlist('files')
    has_files = any([f for f in files_in_request if f and f.filename])

    if not content and not has_files:
        return jsonify({'success': False, 'error': '消息内容不能为空'}), 400

    session = _get_or_create_session(session_id)
    state = session.state or {}

    templates = Template.query.order_by(Template.created_at.desc()).limit(50).all()
    template_list = [{'id': t.id, 'name': t.name} for t in templates]

    engine = AIExtractionEngine()
    lease_rule_file = None
    lease_pdf_files = []
    candidate_xlsx_files = []
    if has_files:
        for f in files_in_request:
            if not f or not f.filename:
                continue
            name = f.filename
            lower = name.lower()
            if lower.endswith('.xlsx'):
                candidate_xlsx_files.append(f)
                if '规则' in name and not lease_rule_file:
                    lease_rule_file = f
            if lower.endswith('.pdf'):
                lease_pdf_files.append(f)

    pass  # Debug logging removed

    if not lease_rule_file and candidate_xlsx_files and _text_is_generate(content):
        lease_rule_file = candidate_xlsx_files[0]

    if lease_rule_file and lease_pdf_files:
        parsed = {'intent': 'lease_pdf_extract', 'slots': {}}
    elif lease_rule_file and _text_is_generate(content):
        parsed = {'intent': 'generate_template_from_rules', 'slots': {}}
    elif _text_is_help(content):
        parsed = {'intent': 'help', 'slots': {}}
    elif _text_is_cancel(content):
        parsed = {'intent': 'cancel', 'slots': {}}
    elif _text_is_generate(content) and not lease_rule_file:
        import re
        desc = None
        parts = re.split(r'[:：]', content, maxsplit=1)
        if len(parts) == 2:
            v = parts[1].strip()
            if v:
                desc = v
        if desc is None:
            v = re.sub(r'(生成模板|创建模板)', '', content).strip()
            if v:
                desc = v
        parsed = {'intent': 'generate_template', 'slots': {'template_description': desc}}
    elif '保存模板' in content:
        parsed = {'intent': 'save_template', 'slots': {}}
    elif '列出模板' in content or '模板列表' in content:
        parsed = {'intent': 'list_templates', 'slots': {}}
    elif '统计' in content:
        parsed = {'intent': 'stats', 'slots': {}}
    elif '导出' in content and ('批次' in content or 'batch' in content.lower()):
        parsed = {'intent': 'export_batch', 'slots': {}}
    elif '提取' in content or '解析' in content or '批量' in content:
        parsed = {'intent': 'batch_extract' if '批量' in content else 'extract_documents', 'slots': {}}
    else:
        pending = state.get('pending')
        if pending:
            parsed = {'intent': 'pending', 'slots': {}}
        else:
            parsed = _parse_command(engine, content, state, template_list)
    intent = parsed.get('intent')
    slots = parsed.get('slots') or {}

    message = ChatMessage(
        source=source,
        content=content,
        sender=sender,
        timestamp=datetime.utcnow(),
        status='processing',
        structured_data={'session_id': session.id, 'intent': intent, 'slots': slots}
    )
    db.session.add(message)
    db.session.commit()

    assistant_message = ''
    structured_data = None

    try:
        pending = state.get('pending')

        if intent == 'help':
            assistant_message = (
                "可用指令示例：\n"
                "1) 列出模板\n"
                "2) 系统统计\n"
                "3) 生成模板：提取发票上的不含税金额和税额\n"
                "4) 生成模板：上传规则Excel后发送“生成模板”\n"
                "5) 保存模板 名称=增值税专票\n"
                "6) 提取附件：使用模板=增值税专票 提取附件\n"
                "7) 批量提取：批量提取 模板=租约 附件\n"
                "8) 导出批次：导出批次 12 csv\n"
                "9) 取消"
            )
            structured_data = {'session_id': session.id, 'intent': intent}

        elif intent == 'stats':
            assistant_message = '系统统计如下：'
            structured_data = {
                'total_documents': Document.query.count(),
                'total_templates': Template.query.count(),
                'total_extractions': ExtractionRecord.query.count()
            }

        elif intent == 'list_templates':
            assistant_message = '模板列表如下：'
            structured_data = {
                'templates': [{'id': t.id, 'name': t.name, 'document_type': t.document_type} for t in templates]
            }

        elif intent == 'cancel':
            state.pop('pending_template', None)
            state.pop('pending_batch', None)
            state.pop('pending', None)
            _save_session_state(session, state)
            assistant_message = '已取消当前待办。'
            structured_data = {'session_id': session.id, 'intent': intent}

        elif intent == 'export_batch':
            batch_id = slots.get('batch_id')
            export_format = (slots.get('export_format') or 'json').lower()
            if not batch_id:
                assistant_message = '请提供批次ID，例如：导出批次 12 csv'
            else:
                assistant_message = '导出链接如下：'
                structured_data = {
                    'batch_id': int(batch_id),
                    'export_json_url': f"/api/batch/{int(batch_id)}/export?format=json",
                    'export_csv_url': f"/api/batch/{int(batch_id)}/export?format=csv",
                    'format': export_format
                }

        elif intent == 'lease_pdf_extract':
            if not lease_rule_file or not lease_pdf_files:
                assistant_message = '请上传：租约字段提取规则.xlsx（规则）和一个或多个合同PDF，然后发送“开始”。'
            else:
                _ensure_upload_dir()
                rule_original = lease_rule_file.filename or 'rules.xlsx'
                rule_suffix = Path(rule_original).suffix.lower()
                if rule_suffix != '.xlsx':
                    rule_suffix = '.xlsx'
                rule_stem = secure_filename(Path(rule_original).stem) or 'rules'
                rule_name = f"{rule_stem}{rule_suffix}"
                rule_path = os.path.join('uploads', f"{uuid.uuid4().hex}_{rule_name}")
                lease_rule_file.save(rule_path)

                pdf_paths = []
                try:
                    for pf in lease_pdf_files:
                        pdf_original = pf.filename or 'contract.pdf'
                        pdf_suffix = Path(pdf_original).suffix.lower()
                        if pdf_suffix != '.pdf':
                            pdf_suffix = '.pdf'
                        pdf_stem = secure_filename(Path(pdf_original).stem) or 'contract'
                        pdf_name = f"{pdf_stem}{pdf_suffix}"
                        pdf_path = os.path.join('uploads', f"{uuid.uuid4().hex}_{pdf_name}")
                        pf.save(pdf_path)
                        pdf_paths.append(pdf_path)

                    pass  # Debug logging removed

                    result = extract_lease_from_pdfs(
                        rule_xlsx_path=rule_path,
                        pdf_paths=pdf_paths,
                        output_template_xlsx_path='输出：租约完整信息.xlsx',
                        output_dir='uploads',
                    )
                finally:
                    try:
                        if os.path.exists(rule_path):
                            os.remove(rule_path)
                    except Exception:
                        pass
                    for p in pdf_paths:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass

                if not result.get('success'):
                    assistant_message = f"租约提取失败：{result.get('error') or '未知错误'}"
                    structured_data = result
                else:
                    out_file = result.get('output_file')
                    meta_info = (result or {}).get('meta') or {}
                    assistant_message = f"租约提取完成：租约{meta_info.get('lease_count', 0)}条，费用{meta_info.get('fee_count', 0)}条。"
                    structured_data = {
                        **result,
                        'download_url': f"/api/chat/download/{out_file}" if out_file else None
                    }

        elif intent == 'generate_template':
            desc = (slots.get('template_description') or '').strip()
            if not desc:
                state['pending'] = {'type': 'generate_template', 'step': 'await_description'}
                _save_session_state(session, state)
                assistant_message = '好的。请描述你要提取的字段和用途（例如：提取发票上的不含税金额和税额，用于财务记账）。'
                structured_data = {'session_id': session.id, 'pending': state['pending']}
            else:
                generator = TemplateGenerator()
                draft = generator.generate_from_description(desc, 'custom')
                state['pending_template'] = draft
                state['pending'] = {'type': 'save_template', 'step': 'await_name'}
                _save_session_state(session, state)
                assistant_message = '模板草稿已生成。请给模板起一个名称并回复（例如：名称=增值税专票），我再为你保存。'
                structured_data = {'draft': draft, 'session_id': session.id, 'pending': state['pending']}

        elif intent == 'generate_template_from_rules':
            if not lease_rule_file:
                assistant_message = '请上传规则Excel文件（文件名包含"规则"的.xlsx），然后发送"生成模板"。'
            else:
                _ensure_upload_dir()
                rule_original = lease_rule_file.filename or 'rules.xlsx'
                rule_suffix = Path(rule_original).suffix.lower()
                if rule_suffix != '.xlsx':
                    rule_suffix = '.xlsx'
                rule_stem = secure_filename(Path(rule_original).stem) or 'rules'
                rule_name = f"{rule_stem}{rule_suffix}"
                rule_path = os.path.join('uploads', f"{uuid.uuid4().hex}_{rule_name}")
                lease_rule_file.save(rule_path)

                try:
                    fields = lease_rules_to_template_fields(rule_path)
                finally:
                    try:
                        if os.path.exists(rule_path):
                            os.remove(rule_path)
                    except Exception:
                        pass

                if not fields:
                    assistant_message = '未能从规则Excel中解析出字段，请检查文件格式。'
                else:
                    draft = {
                        'name': None,
                        'description': '从租约规则Excel自动生成的模板',
                        'document_type': 'lease',
                        'fields': fields,
                        'validation_rules': [],
                    }
                    state['pending_template'] = draft
                    state['pending'] = {'type': 'save_template', 'step': 'await_name'}
                    _save_session_state(session, state)
                    assistant_message = f'已解析规则Excel，共{len(fields)}个字段。请给模板起一个名称并回复（例如：名称=租约全量提取）。'
                    structured_data = {'draft': draft, 'session_id': session.id, 'pending': state['pending'], 'field_count': len(fields)}

        elif intent == 'save_template':
            draft = state.get('pending_template')
            if not draft:
                state['pending'] = {'type': 'generate_template', 'step': 'await_description'}
                _save_session_state(session, state)
                assistant_message = '当前没有模板草稿。请先描述需求（例如：生成模板：提取发票上的不含税金额和税额）。'
                structured_data = {'session_id': session.id, 'pending': state['pending']}
            else:
                save_name = (slots.get('template_save_name') or '').strip()
                if save_name:
                    draft['name'] = save_name

                if not draft.get('name') or not draft.get('fields'):
                    state['pending'] = {'type': 'save_template', 'step': 'await_name'}
                    _save_session_state(session, state)
                    assistant_message = '请提供模板名称（例如：名称=增值税专票），我才能保存模板。'
                    structured_data = {'draft': draft, 'session_id': session.id, 'pending': state['pending']}
                else:
                    exists = Template.query.filter_by(name=draft['name']).first()
                    if exists:
                        state['pending'] = {'type': 'save_template', 'step': 'await_name'}
                        _save_session_state(session, state)
                        assistant_message = f"模板名称已存在：{draft['name']}。请换个名称并回复（例如：名称=xxx）。"
                        structured_data = {'draft': draft, 'session_id': session.id, 'pending': state['pending']}
                    else:
                        template = Template(
                            name=draft['name'],
                            description=draft.get('description', ''),
                            document_type=draft.get('document_type', 'custom'),
                            fields=draft.get('fields', []),
                            validation_rules=draft.get('validation_rules', [])
                        )
                        db.session.add(template)
                        db.session.commit()
                        state.pop('pending_template', None)
                        state.pop('pending', None)
                        _save_session_state(session, state)
                        assistant_message = f"模板已保存：{template.name}（ID={template.id}）"
                        structured_data = {'template': {'id': template.id, 'name': template.name, 'document_type': template.document_type}}

        elif intent in ['extract_documents', 'batch_extract']:
            template = _find_template(slots)
            if not template:
                mode = 'batch' if intent == 'batch_extract' else 'single'
                state['pending'] = {'type': 'extract', 'step': 'await_template', 'mode': mode}
                _save_session_state(session, state)
                assistant_message = '好的。请先选择要使用的模板（回复模板ID或模板名称）。\n' + _render_template_choices(templates)
                structured_data = {'session_id': session.id, 'pending': state['pending'], 'templates': template_list}
            else:
                mode = 'batch' if intent == 'batch_extract' else 'single'
                state['pending'] = {'type': 'extract', 'step': 'await_confirm', 'mode': mode, 'template_id': template.id}
                _save_session_state(session, state)
                assistant_message = f"已选择模板：{template.name}。确认使用该模板进行{'批量' if mode == 'batch' else '单文档'}提取吗？回复：确认/取消"
                structured_data = {'session_id': session.id, 'pending': state['pending'], 'template': {'id': template.id, 'name': template.name}}

        elif intent == 'pending' and pending:
            p_type = pending.get('type')
            p_step = pending.get('step')

            if p_type == 'generate_template' and p_step == 'await_description':
                desc = content.strip()
                if not desc:
                    assistant_message = '请描述要提取的字段和用途（例如：提取发票上的不含税金额和税额）。'
                else:
                    generator = TemplateGenerator()
                    draft = generator.generate_from_description(desc, 'custom')
                    state['pending_template'] = draft
                    state['pending'] = {'type': 'save_template', 'step': 'await_name'}
                    _save_session_state(session, state)
                    assistant_message = '模板草稿已生成。请给模板起一个名称并回复（例如：名称=增值税专票）。'
                    structured_data = {'draft': draft, 'session_id': session.id, 'pending': state['pending']}

            elif p_type == 'save_template' and p_step == 'await_name':
                draft = state.get('pending_template')
                name_slots = _try_parse_template_from_text(content)
                save_name = None
                if name_slots.get('template_name'):
                    save_name = name_slots.get('template_name')
                import re
                m = re.search(r'名称\s*=\s*([^\s]+)', content)
                if m:
                    save_name = m.group(1).strip()

                if not draft:
                    state['pending'] = {'type': 'generate_template', 'step': 'await_description'}
                    _save_session_state(session, state)
                    assistant_message = '当前没有模板草稿。请先描述需求（例如：生成模板：...）。'
                elif not save_name:
                    assistant_message = '请提供模板名称（例如：名称=增值税专票）。'
                    structured_data = {'draft': draft, 'session_id': session.id, 'pending': pending}
                else:
                    draft['name'] = save_name
                    exists = Template.query.filter_by(name=draft['name']).first()
                    if exists:
                        assistant_message = f"模板名称已存在：{draft['name']}。请换个名称并回复（例如：名称=xxx）。"
                        structured_data = {'draft': draft, 'session_id': session.id, 'pending': pending}
                    else:
                        template = Template(
                            name=draft['name'],
                            description=draft.get('description', ''),
                            document_type=draft.get('document_type', 'custom'),
                            fields=draft.get('fields', []),
                            validation_rules=draft.get('validation_rules', [])
                        )
                        db.session.add(template)
                        db.session.commit()
                        state.pop('pending_template', None)
                        state.pop('pending', None)
                        _save_session_state(session, state)
                        assistant_message = f"模板已保存：{template.name}（ID={template.id}）"
                        structured_data = {'template': {'id': template.id, 'name': template.name, 'document_type': template.document_type}}

            elif p_type == 'extract' and p_step == 'await_template':
                t_slots = _try_parse_template_from_text(content)
                template = _find_template(t_slots)
                if not template:
                    assistant_message = '未找到该模板。请回复模板ID或模板名称。\n' + _render_template_choices(templates)
                else:
                    state['pending'] = {
                        'type': 'extract',
                        'step': 'await_confirm',
                        'mode': pending.get('mode', 'single'),
                        'template_id': template.id
                    }
                    _save_session_state(session, state)
                    assistant_message = f"已选择模板：{template.name}。确认继续吗？回复：确认/取消"
                    structured_data = {'session_id': session.id, 'pending': state['pending'], 'template': {'id': template.id, 'name': template.name}}

            elif p_type == 'extract' and p_step == 'await_confirm':
                if _text_is_cancel(content):
                    state.pop('pending', None)
                    _save_session_state(session, state)
                    assistant_message = '已取消。'
                elif not _text_is_confirm(content):
                    assistant_message = '请回复：确认 或 取消'
                else:
                    state['pending'] = {
                        'type': 'extract',
                        'step': 'await_files',
                        'mode': pending.get('mode', 'single'),
                        'template_id': pending.get('template_id')
                    }
                    _save_session_state(session, state)
                    assistant_message = '请上传附件文件，然后发送任意文字（例如：开始）。'
                    structured_data = {'session_id': session.id, 'pending': state['pending']}

            elif p_type == 'extract' and p_step == 'await_files':
                template = Template.query.get(pending.get('template_id'))
                if not template:
                    state.pop('pending', None)
                    _save_session_state(session, state)
                    assistant_message = '模板不存在或已删除，请重新选择模板。'
                else:
                    files = request.files.getlist('files')
                    files = [f for f in files if f and f.filename and _allowed_file(f.filename)]
                    if not files:
                        assistant_message = '未检测到附件。请先选择附件文件并发送。'
                    else:
                        results = []
                        for f in files:
                            r = _extract_one_file(f, template)
                            if isinstance(r, list):
                                results.extend(r)
                            else:
                                results.append(r)

                        mode = pending.get('mode', 'single')
                        if mode == 'batch' or len(results) > 1:
                            batch = BatchProcess(
                                name=f"Chat批量_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                                status='completed',
                                total_files=len(results),
                                processed_files=len(results),
                                successful_files=len([r for r in results if r.get('success')]),
                                failed_files=len([r for r in results if not r.get('success')]),
                                template_id=template.id,
                                results={
                                    'results': results,
                                    'document_ids': [r.get('document_id') for r in results if r.get('document_id')]
                                },
                                completed_at=datetime.utcnow()
                            )
                            db.session.add(batch)
                            db.session.commit()
                            assistant_message = f"提取完成。批次ID={batch.id}。需要导出可说：导出批次 {batch.id} csv/json"
                            structured_data = {
                                'batch_id': batch.id,
                                'template': {'id': template.id, 'name': template.name},
                                'results': results,
                                'export_json_url': f"/api/batch/{batch.id}/export?format=json",
                                'export_csv_url': f"/api/batch/{batch.id}/export?format=csv"
                            }
                        else:
                            assistant_message = '提取完成。'
                            structured_data = {
                                'template': {'id': template.id, 'name': template.name},
                                'results': results
                            }
                        state.pop('pending', None)
                        _save_session_state(session, state)

            else:
                assistant_message = '当前待办状态异常，已重置。你可以说“帮助”查看可用指令。'
                state.pop('pending', None)
                _save_session_state(session, state)


        else:
            assistant_message = '我没理解你的指令。你可以说“帮助”查看可用指令。'

        message.structured_data = {
            'session_id': session.id,
            'intent': intent,
            'slots': slots,
            'assistant_message': assistant_message,
            'structured_data': structured_data
        }
        message.status = 'completed'
        db.session.commit()

        return jsonify({
            'success': True,
            'session_id': session.id,
            'assistant_message': assistant_message,
            'structured_data': structured_data
        }), 200

    except Exception as e:
        message.status = 'failed'
        message.structured_data = {
            'session_id': session.id,
            'intent': intent,
            'slots': slots,
            'error': str(e)
        }
        db.session.commit()
        return jsonify({'success': False, 'error': str(e), 'session_id': session.id}), 500

@bp.route('/process', methods=['POST'])
def process_chat_message():
    """处理即时通讯消息"""
    data = request.get_json()
    
    content = data.get('content', '')
    source = data.get('source', 'unknown')
    sender = data.get('sender')
    timestamp = data.get('timestamp')
    
    if not content:
        return jsonify({'success': False, 'error': '消息内容不能为空'}), 400
    
    try:
        message = ChatMessage(
            source=source,
            content=content,
            sender=sender,
            timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow(),
            status='processing'
        )
        
        db.session.add(message)
        db.session.commit()
        
        engine = AIExtractionEngine()
        
        structured_data = extract_structured_from_chat(
            content=content,
            source=source,
            engine=engine
        )
        
        message.structured_data = structured_data
        message.status = 'completed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'source': message.source,
                'sender': message.sender,
                'content': message.content,
                'structured_data': message.structured_data,
                'timestamp': message.timestamp.isoformat()
            }
        }), 200
    
    except Exception as e:
        if message:
            message.status = 'failed'
            db.session.commit()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def extract_structured_from_chat(content: str, source: str, engine) -> dict:
    """从聊天内容中提取结构化数据"""
    
    context_prompt = f"""你是一个智能助手，专门从即时通讯消息中提取结构化的业务信息。

## 消息来源
{source}

## 消息内容
{content}

## 提取任务
请分析这条消息，识别其中包含的业务信息，如：
- 租赁意向或变更
- 交易信息
- 联系人信息
- 时间安排
- 金额信息
- 其他关键业务数据

## 输出要求
以JSON格式返回提取的信息：
{{
    "has_business_info": true/false,
    "business_type": "租赁意向/交易信息/联系人/其他/无",
    "entities": {{
        "contacts": ["联系人列表"],
        "amounts": ["金额列表"],
        "dates": ["日期列表"],
        "locations": ["地点列表"]
    }},
    "summary": "简要总结",
    "confidence": 0.0-1.0,
    "needs_review": true/false,
    "suggestions": ["建议或备注"]
}}

请开始提取："""
    
    try:
        response = engine.run_json_prompt(context_prompt)
        if response.get('success'):
            return response.get('data') or {}
        return {
            'has_business_info': False,
            'error': response.get('error')
        }
    
    except Exception as e:
        return {
            'has_business_info': False,
            'error': str(e)
        }

@bp.route('/batch-process', methods=['POST'])
def batch_process_messages():
    """批量处理即时通讯消息"""
    data = request.get_json()
    
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({'success': False, 'error': '消息列表为空'}), 400
    
    results = []
    
    engine = AIExtractionEngine()
    
    for msg in messages:
        content = msg.get('content', '')
        source = msg.get('source', 'unknown')
        sender = msg.get('sender')
        
        try:
            structured_data = extract_structured_from_chat(
                content=content,
                source=source,
                engine=engine
            )
            
            message = ChatMessage(
                source=source,
                content=content,
                sender=sender,
                structured_data=structured_data,
                status='completed'
            )
            
            db.session.add(message)
            db.session.commit()
            
            results.append({
                'id': message.id,
                'content': content,
                'structured_data': structured_data,
                'status': 'completed'
            })
        
        except Exception as e:
            results.append({
                'content': content,
                'error': str(e),
                'status': 'failed'
            })
    
    successful = len([r for r in results if r.get('status') == 'completed'])
    
    return jsonify({
        'success': True,
        'total': len(messages),
        'successful': successful,
        'failed': len(messages) - successful,
        'results': results
    }), 200

@bp.route('/<int:message_id>', methods=['GET'])
def get_message(message_id):
    """获取消息详情"""
    message = ChatMessage.query.get_or_404(message_id)
    
    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'source': message.source,
            'content': message.content,
            'sender': message.sender,
            'structured_data': message.structured_data,
            'status': message.status,
            'timestamp': message.timestamp.isoformat()
        }
    })

@bp.route('/list', methods=['GET'])
def list_messages():
    """获取消息列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    source = request.args.get('source')
    status = request.args.get('status')
    
    query = ChatMessage.query
    
    if source:
        query = query.filter_by(source=source)
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(ChatMessage.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'messages': [{
            'id': m.id,
            'source': m.source,
            'content': m.content[:100] + '...' if len(m.content) > 100 else m.content,
            'sender': m.sender,
            'structured_data': m.structured_data,
            'status': m.status,
            'timestamp': m.timestamp.isoformat()
        } for m in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })

@bp.route('/<int:message_id>', methods=['PUT'])
def update_message(message_id):
    """更新消息（修正提取结果）"""
    message = ChatMessage.query.get_or_404(message_id)
    data = request.get_json()
    
    try:
        if 'structured_data' in data:
            message.structured_data = data['structured_data']
        
        if 'status' in data:
            message.status = data['status']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': {
                'id': message.id,
                'structured_data': message.structured_data,
                'status': message.status,
                'updated_at': message.timestamp.isoformat()
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/export', methods=['POST'])
def export_chat_data():
    """导出发送给CRM的数据"""
    data = request.get_json()
    
    message_ids = data.get('message_ids', [])
    export_format = data.get('format', 'json')
    
    if not message_ids:
        return jsonify({'success': False, 'error': '消息ID列表为空'}), 400
    
    messages = ChatMessage.query.filter(
        ChatMessage.id.in_(message_ids)
    ).filter(
        ChatMessage.structured_data.isnot(None)
    ).all()
    
    if export_format == 'json':
        export_data = [
            {
                'message_id': msg.id,
                'source': msg.source,
                'content': msg.content,
                'sender': msg.sender,
                'business_data': msg.structured_data,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in messages
        ]
        
        return jsonify({
            'success': True,
            'format': 'json',
            'data': export_data,
            'total': len(export_data)
        }), 200
    
    elif export_format == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Message ID', 'Source', 'Sender', 'Content', 
            'Business Type', 'Summary', 'Timestamp'
        ])
        
        for msg in messages:
            structured = msg.structured_data or {}
            writer.writerow([
                msg.id,
                msg.source,
                msg.sender,
                msg.content[:200],
                structured.get('business_type', ''),
                structured.get('summary', ''),
                msg.timestamp.isoformat()
            ])
        
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=chat_extracted_data.csv'
        }
    
    else:
        return jsonify({
            'success': False,
            'error': '不支持的导出格式'
        }), 400

@bp.route('/download/<path:filename>', methods=['GET'])
def download_generated_file(filename: str):
    safe_name = os.path.basename(filename or '')
    if not safe_name or safe_name != filename:
        return jsonify({'success': False, 'error': '非法文件名'}), 400
    if not safe_name.lower().endswith('.xlsx'):
        return jsonify({'success': False, 'error': '仅支持下载xlsx文件'}), 400
    file_path = os.path.join('uploads', safe_name)
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': '文件不存在或已过期'}), 404
    return send_from_directory('uploads', safe_name, as_attachment=True, download_name=safe_name)
