"""
微信管理 API 路由
"""

import os
from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, WeChatSession, WeChatMessage
from services.wechat_bot import WeChatBot

bp = Blueprint('wechat', __name__, url_prefix='/api/wechat')


@bp.route('/status', methods=['GET'])
def get_status():
    """获取微信登录状态"""
    bot = WeChatBot()
    return jsonify(bot.get_login_status())


@bp.route('/login', methods=['POST'])
def login():
    """获取微信登录二维码"""
    bot = WeChatBot()
    result = bot.get_qr_code()
    return jsonify(result)


@bp.route('/logout', methods=['POST'])
def logout():
    """退出微信登录"""
    bot = WeChatBot()
    result = bot.logout()
    return jsonify(result)


@bp.route('/messages', methods=['GET'])
def get_messages():
    """获取聊天历史"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    chat_name = request.args.get('chat_name')
    is_group = request.args.get('is_group')
    sender_name = request.args.get('sender_name')

    query = WeChatMessage.query

    if start_time:
        try:
            query = query.filter(WeChatMessage.timestamp >= datetime.fromisoformat(start_time))
        except Exception:
            pass
    if end_time:
        try:
            query = query.filter(WeChatMessage.timestamp <= datetime.fromisoformat(end_time))
        except Exception:
            pass
    if chat_name:
        query = query.filter(WeChatMessage.chat_name.contains(chat_name))
    if sender_name:
        query = query.filter(WeChatMessage.sender_name.contains(sender_name))
    if is_group is not None:
        query = query.filter(WeChatMessage.is_group == (is_group.lower() == 'true'))

    query = query.order_by(WeChatMessage.timestamp.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    messages = []
    for msg in pagination.items:
        messages.append({
            'id': msg.id,
            'msg_type': msg.msg_type,
            'content': msg.content,
            'sender_name': msg.sender_name,
            'chat_name': msg.chat_name,
            'is_group': msg.is_group,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
        })

    return jsonify({
        'success': True,
        'messages': messages,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    })


@bp.route('/chat-groups', methods=['GET'])
def get_chat_groups():
    """获取聊天群组/联系人列表（用于筛选）"""
    query = db.session.query(
        WeChatMessage.chat_name,
        WeChatMessage.is_group,
        db.func.count(WeChatMessage.id).label('msg_count'),
        db.func.max(WeChatMessage.timestamp).label('last_msg_time')
    ).group_by(WeChatMessage.chat_name, WeChatMessage.is_group).order_by(
        db.func.max(WeChatMessage.timestamp).desc()
    )

    groups = []
    for row in query.all():
        groups.append({
            'chat_name': row.chat_name,
            'is_group': row.is_group,
            'msg_count': row.msg_count,
            'last_msg_time': row.last_msg_time.isoformat() if row.last_msg_time else None,
        })

    return jsonify({
        'success': True,
        'groups': groups,
    })


@bp.route('/ingest', methods=['POST'])
def ingest_message():
    secret = os.environ.get('WECHAT_INGEST_SECRET', '')
    if secret:
        if request.headers.get('X-Wechat-Ingest-Secret') != secret:
            return jsonify({'success': False, 'error': 'unauthorized'}), 401
    else:
        if request.remote_addr not in ('127.0.0.1', '::1'):
            return jsonify({'success': False, 'error': 'unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    msg_id = str(payload.get('msg_id') or '').strip()
    if not msg_id:
        return jsonify({'success': False, 'error': 'missing msg_id'}), 400

    existing = WeChatMessage.query.filter_by(msg_id=msg_id).first()
    if existing:
        return jsonify({'success': True, 'duplicated': True})

    content = payload.get('content')
    if content is None:
        content = ''

    ts = payload.get('timestamp')
    msg_time = None
    if ts:
        try:
            msg_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except Exception:
            msg_time = None

    msg = WeChatMessage(
        msg_id=msg_id,
        msg_type=str(payload.get('msg_type') or 'Text'),
        content=str(content),
        sender_name=payload.get('sender_name'),
        sender_username=payload.get('sender_username'),
        chat_name=payload.get('chat_name'),
        chat_username=payload.get('chat_username'),
        is_group=bool(payload.get('is_group')),
        timestamp=msg_time or datetime.utcnow(),
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True})
