"""
模板生成服务
基于自然语言描述生成提取模板
"""

import json
from services.extraction_engine import AIExtractionEngine

class TemplateGenerator:
    """模板生成器"""
    
    def __init__(self):
        self.engine = AIExtractionEngine()
    
    def generate_from_description(self, description: str, document_type: str = 'custom') -> dict:
        """根据自然语言描述生成模板"""
        
        prompt = f"""你是一个专业的文档提取模板设计师。请根据用户的描述，生成一个完整的提取模板配置。

## 用户需求描述
{description}

## 文档类型
{document_type}

## 任务
请分析用户需求，生成一个JSON格式的提取模板，包含：
1. 模板名称（name）
2. 描述（description）
3. 文档类型（document_type）
4. 字段定义（fields）- 包含字段名、描述、类型、是否必填
5. 验证规则（validation_rules）- 可选的验证逻辑

## 字段定义格式
每个字段应包含：
- name: 字段英文名
- description: 字段描述
- type: 字段类型（string/number/date/array/boolean）
- required: 是否必填（true/false）

## 验证规则格式
每个规则应包含：
- type: 规则类型（equation/range/required/format）
- field: 应用的字段
- rule: 规则描述
- message: 验证失败消息

## 示例输出格式
{{
    "name": "模板名称",
    "description": "模板描述",
    "document_type": "文档类型",
    "fields": [
        {{
            "name": "field_name",
            "description": "字段描述",
            "type": "string",
            "required": true
        }}
    ],
    "validation_rules": [
        {{
            "type": "equation",
            "field1": "field_a",
            "field2": "field_b",
            "operator": "+",
            "result": "field_total",
            "message": "验证消息"
        }}
    ]
}}

请生成模板配置："""
        
        try:
            response = self.engine.run_json_prompt(prompt)
            if not response.get('success') or not isinstance(response.get('data'), dict):
                return self._generate_default_template(description, document_type)

            data = response.get('data') or {}
            template = {
                'name': data.get('name', f'自动生成模板_{document_type}'),
                'description': data.get('description', description),
                'document_type': data.get('document_type', document_type),
                'fields': data.get('fields', []),
                'validation_rules': data.get('validation_rules', [])
            }
            if not template.get('fields'):
                return self._generate_default_template(description, document_type)
            return template
        
        except Exception:
            return self._generate_default_template(description, document_type)
    
    def _generate_default_template(self, description: str, document_type: str) -> dict:
        """生成默认模板"""
        
        return {
            'name': f'自定义模板_{document_type}',
            'description': description,
            'document_type': document_type,
            'fields': [
                {
                    'name': 'key_info',
                    'description': '关键信息',
                    'type': 'string',
                    'required': True
                }
            ],
            'validation_rules': []
        }
    
    def improve_template(self, current_template: dict, feedback: str) -> dict:
        """根据反馈改进模板"""
        
        prompt = f"""你是一个模板优化专家。用户提供了以下反馈，请改进模板配置。

## 当前模板配置
{json.dumps(current_template, ensure_ascii=False, indent=2)}

## 用户反馈
{feedback}

## 任务
分析反馈，对模板进行改进，返回更新后的JSON配置。

请返回改进后的模板："""
        
        try:
            response = self.engine.extract(
                document_text=json.dumps(current_template),
                template={
                    'fields': [],
                    'document_type': '模板优化',
                    'context': {
                        'task': 'improve_template',
                        'feedback': feedback
                    }
                }
            )
            
            if response.get('success'):
                return response.get('data', current_template)
            else:
                return current_template
        
        except Exception:
            return current_template
