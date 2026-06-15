"""
模板生成服务
基于自然语言描述生成提取模板
"""

import json
import re
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
            if not template.get('fields') or self._is_generic_keyinfo_only(template.get('fields') or []):
                return self._generate_default_template(description, document_type)
            return template
        
        except Exception:
            return self._generate_default_template(description, document_type)
    
    def _generate_default_template(self, description: str, document_type: str) -> dict:
        """生成默认模板"""
        fields, rules = self._heuristic_template_from_description(description)
        if fields:
            return {
                'name': f'自定义模板_{document_type}',
                'description': description,
                'document_type': document_type,
                'fields': fields,
                'validation_rules': rules
            }

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

    def _is_generic_keyinfo_only(self, fields: list[dict]) -> bool:
        if not fields:
            return True
        normalized = []
        for f in fields:
            name = (f or {}).get('name')
            if isinstance(name, str):
                normalized.append(name.strip().lower())
        normalized = [n for n in normalized if n]
        if not normalized:
            return True
        generic = {'key_info', 'keyinfo', 'keyinformation', 'key_information', '关键信息'}
        return all(n in generic for n in normalized)

    def _heuristic_template_from_description(self, description: str) -> tuple[list[dict], list[dict]]:
        text = (description or '').strip()
        if not text:
            return [], []

        cn_to_field = {
            '不含税金额': ('amount_excl_tax', 'number'),
            '税额': ('tax_amount', 'number'),
            '含税金额': ('amount_incl_tax', 'number'),
            '价税合计': ('amount_incl_tax', 'number'),
            '发票号码': ('invoice_no', 'string'),
            '发票号': ('invoice_no', 'string'),
            '发票代码': ('invoice_code', 'string'),
            '开票日期': ('invoice_date', 'date'),
            '日期': ('date', 'date'),
            '购买方名称': ('buyer_name', 'string'),
            '购买方': ('buyer_name', 'string'),
            '销售方名称': ('seller_name', 'string'),
            '销售方': ('seller_name', 'string'),
            '税率': ('tax_rate', 'number'),
        }

        def infer_type(term: str) -> str:
            if any(k in term for k in ['金额', '税', '数量', '单价', '合计', '率']):
                return 'number'
            if '日期' in term or term == '日期':
                return 'date'
            if term.startswith('是否') or term.endswith('是否'):
                return 'boolean'
            return 'string'

        def normalize_field(term: str, idx: int) -> tuple[str, str]:
            term = term.strip()
            if not term:
                return f'field_{idx}', 'string'
            if term in cn_to_field:
                return cn_to_field[term]
            return f'field_{idx}', infer_type(term)

        def extract_terms(t: str) -> list[str]:
            t = re.sub(r'\s+', ' ', t)
            parts = re.split(r'[，,;；。\n]', t)
            candidates: list[str] = []
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '用于' in p:
                    p = p.split('用于', 1)[0].strip()
                if '用来' in p:
                    p = p.split('用来', 1)[0].strip()
                if '以便' in p:
                    p = p.split('以便', 1)[0].strip()
                if '提取' in p:
                    p = p.split('提取', 1)[1].strip()
                p = re.sub(r'^(发票(上|里的|中的)?|合同(上|里的|中的)?)', '', p).strip()
                if not p:
                    continue
                for s in re.split(r'[、和与及 ]', p):
                    s = s.strip()
                    if s:
                        candidates.append(s)
            seen = set()
            out: list[str] = []
            for c in candidates:
                if c in seen:
                    continue
                seen.add(c)
                out.append(c)
            return out

        rules: list[dict] = []
        fields_terms = extract_terms(text)

        m = re.search(r'(校验规则|校验|验证规则)\s*[:：]\s*(.+)', text)
        rule_text = m.group(2).strip() if m else ''
        eq = None
        if rule_text:
            eq = re.search(r'(.+?)\s*=\s*(.+?)\s*([\+\-\*/])\s*(.+)', rule_text)
        if eq:
            left_cn = eq.group(1).strip()
            right1_cn = eq.group(2).strip()
            op = eq.group(3).strip()
            right2_cn = eq.group(4).strip()
            fields_terms.extend([left_cn, right1_cn, right2_cn])
            f_left, _ = normalize_field(left_cn, 1)
            f_r1, _ = normalize_field(right1_cn, 2)
            f_r2, _ = normalize_field(right2_cn, 3)
            rules.append({
                'type': 'equation',
                'field1': f_r1,
                'field2': f_r2,
                'operator': op,
                'result': f_left,
                'rule': f'{f_left} = {f_r1} {op} {f_r2}',
                'message': f'{left_cn}应等于{right1_cn}{op}{right2_cn}'
            })

        uniq_terms = []
        seen_terms = set()
        for t in fields_terms:
            if not t or t in seen_terms:
                continue
            seen_terms.add(t)
            uniq_terms.append(t)

        fields: list[dict] = []
        used_names = set()
        for i, term in enumerate(uniq_terms, start=1):
            name, ftype = normalize_field(term, i)
            if name in used_names:
                continue
            used_names.add(name)
            fields.append({
                'name': name,
                'description': term,
                'type': ftype,
                'required': True
            })

        return fields, rules
    
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
