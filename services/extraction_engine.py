"""
AI提取引擎
基于OpenRouter的通用文档提取
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

class AIExtractionEngine:
    """AI文档提取引擎"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.base_url = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        self.model = os.getenv('OPENROUTER_MODEL', 'openai/gpt-3.5-turbo')
        self.max_retries = 3
    
    def extract(self, document_text: str, template: Dict[str, Any], context: Optional[Dict] = None) -> Dict[str, Any]:
        """从文档中提取数据"""
        
        if not self.api_key:
            return {
                'success': False,
                'error': 'OpenRouter API密钥未配置',
                'data': {}
            }
        
        prompt = self._build_extraction_prompt(document_text, template, context)
        
        for attempt in range(self.max_retries):
            try:
                response = self._call_openrouter(prompt)
                
                if response.get('success'):
                    return {
                        'success': True,
                        'data': response.get('data', {}),
                        'confidence': response.get('confidence', 0.0),
                        'model': self.model
                    }
                else:
                    if attempt == self.max_retries - 1:
                        return {
                            'success': False,
                            'error': response.get('error', '提取失败'),
                            'data': {}
                        }
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return {
                        'success': False,
                        'error': str(e),
                        'data': {}
                    }
        
        return {
            'success': False,
            'error': '最大重试次数已用完',
            'data': {}
        }
    
    def _build_extraction_prompt(self, document_text: str, template: Dict[str, Any], context: Optional[Dict]) -> str:
        """构建提取提示词"""
        
        fields = template.get('fields', [])
        document_type = template.get('document_type', '通用文档')
        
        fields_description = "\n".join([
            f"- {field['name']}: {field.get('description', '未定义')}"
            for field in fields
        ])
        
        validation_rules = template.get('validation_rules', [])
        validation_description = "\n".join([
            f"- {rule['rule']}"
            for rule in validation_rules
        ]) if validation_rules else "无"
        
        prompt = f"""你是一个专业的{document_type}数据提取助手。请从以下文档内容中提取指定的字段信息。

## 文档类型
{document_type}

## 需要提取的字段
{fields_description}

## 验证规则
{validation_description}

## 文档内容
{document_text}

## 输出要求
1. 以JSON格式返回提取的数据
2. 对于每个字段，如果找到值则返回实际值，如果未找到则返回null
3. 确保数值字段为数字类型，日期字段为标准日期格式
4. 如果某个字段的值不确定或缺失，明确标注

## 返回格式
请返回以下JSON格式的数据：
{{
    "extracted_data": {{
        "字段名1": "提取的值1",
        "字段名2": "提取的值2",
        ...
    }},
    "confidence": 0.0-1.0之间的置信度分数,
    "missing_fields": ["未找到的字段列表"],
    "notes": "备注说明（如有）"
}}

请开始提取数据："""
        
        if context:
            prompt += f"\n\n## 额外上下文信息\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        
        return prompt
    
    def _call_openrouter(self, prompt: str) -> Dict[str, Any]:
        """调用OpenRouter API"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': 2000
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            content = result['choices'][0]['message']['content']
            
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_str = content[json_start:json_end]
                parsed = json.loads(json_str)
                
                return {
                    'success': True,
                    'data': parsed.get('extracted_data', {}),
                    'confidence': parsed.get('confidence', 0.0)
                }
            else:
                return {
                    'success': False,
                    'error': '无法解析AI响应'
                }
        
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'API请求失败: {str(e)}'
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'JSON解析失败: {str(e)}'
            }

    def run_json_prompt(self, prompt: str, temperature: float = 0.1, max_tokens: int = 2000) -> Dict[str, Any]:
        if not self.api_key:
            return {
                'success': False,
                'error': 'OpenRouter API密钥未配置',
                'data': None
            }

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': temperature,
            'max_tokens': max_tokens
        }

        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']

            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                return {
                    'success': False,
                    'error': '无法解析AI响应',
                    'data': None
                }

            parsed = json.loads(content[json_start:json_end])
            return {
                'success': True,
                'data': parsed
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'API请求失败: {str(e)}',
                'data': None
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'JSON解析失败: {str(e)}',
                'data': None
            }
    
    def batch_extract(self, documents: List[Dict[str, Any]], template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """批量提取"""
        
        results = []
        
        for doc in documents:
            result = self.extract(
                document_text=doc.get('text', ''),
                template=template,
                context=doc.get('context')
            )
            
            result['document_id'] = doc.get('id')
            results.append(result)
        
        return results
    
    def validate_extraction(self, extracted_data: Dict[str, Any], validation_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证提取结果"""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        for rule in validation_rules:
            rule_type = rule.get('type')
            
            if rule_type == 'equation':
                if not self._validate_equation(extracted_data, rule):
                    validation_results['valid'] = False
                    validation_results['errors'].append(rule.get('message', '验证失败'))
            
            elif rule_type == 'range':
                if not self._validate_range(extracted_data, rule):
                    validation_results['warnings'].append(rule.get('message', '范围验证警告'))
            
            elif rule_type == 'required':
                if not self._validate_required(extracted_data, rule):
                    validation_results['valid'] = False
                    validation_results['errors'].append(f"必填字段缺失: {rule.get('field')}")
        
        return validation_results
    
    def _validate_equation(self, data: Dict, rule: Dict) -> bool:
        """验证等式关系"""
        try:
            field1 = rule.get('field1')
            field2 = rule.get('field2')
            operator = rule.get('operator', '+')
            
            val1 = float(data.get(field1, 0))
            val2 = float(data.get(field2, 0))
            
            if operator == '+':
                expected = data.get(rule.get('result'))
                return abs(val1 + val2 - float(expected)) < 0.01
            
            return True
        except:
            return True
    
    def _validate_range(self, data: Dict, rule: Dict) -> bool:
        """验证数值范围"""
        try:
            field = rule.get('field')
            min_val = rule.get('min')
            max_val = rule.get('max')
            
            value = float(data.get(field, 0))
            
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
            
            return True
        except:
            return True
    
    def _validate_required(self, data: Dict, rule: Dict) -> bool:
        """验证必填字段"""
        field = rule.get('field')
        return data.get(field) is not None and data.get(field) != ''
