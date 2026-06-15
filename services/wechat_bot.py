"""
微信机器人服务适配层
当前实现采用独立的 WeChaty Node 服务（负责扫码登录与收消息），Flask 侧只做状态/二维码的代理与消息落库。
"""

import os
import requests


class WeChatBot:
    def __init__(self):
        self.base_url = os.environ.get('WECHATY_SERVICE_URL', 'http://127.0.0.1:8788').rstrip('/')

    def get_login_status(self) -> dict:
        try:
            res = requests.get(f'{self.base_url}/status', timeout=3)
            data = res.json()
            if isinstance(data, dict):
                return data
            return {'success': False, 'logged_in': False, 'error': '微信服务返回格式错误'}
        except Exception as e:
            return {'success': False, 'logged_in': False, 'error': f'微信服务不可用: {str(e)}'}

    def get_qr_code(self) -> dict:
        try:
            res = requests.post(f'{self.base_url}/login', timeout=35)
            data = res.json()
            if isinstance(data, dict):
                return data
            return {'success': False, 'error': '微信服务返回格式错误'}
        except Exception as e:
            return {'success': False, 'error': f'获取二维码失败: {str(e)}'}

    def logout(self) -> dict:
        try:
            res = requests.post(f'{self.base_url}/logout', timeout=10)
            data = res.json()
            if isinstance(data, dict):
                return data
            return {'success': False, 'error': '微信服务返回格式错误'}
        except Exception as e:
            return {'success': False, 'error': f'退出失败: {str(e)}'}
