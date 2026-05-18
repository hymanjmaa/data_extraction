"""
文档处理工具模块
支持PDF、图片、Word、Excel等文档解析
"""

import os
import pdfplumber
from PIL import Image
from typing import Dict, Any, List
import json

class DocumentParser:
    """文档解析器基类"""
    
    @staticmethod
    def parse_pdf(file_path: str) -> Dict[str, Any]:
        """解析PDF文档"""
        try:
            text_content = []
            
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            return {
                'success': True,
                'text': '\n'.join(text_content),
                'pages': len(text_content),
                'type': 'pdf'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'pdf'
            }
    
    @staticmethod
    def parse_image(file_path: str) -> Dict[str, Any]:
        """解析图片文档（OCR预处理）"""
        try:
            image = Image.open(file_path)
            
            return {
                'success': True,
                'image_data': file_path,
                'width': image.width,
                'height': image.height,
                'format': image.format,
                'type': 'image'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'image'
            }
    
    @staticmethod
    def parse_docx(file_path: str) -> Dict[str, Any]:
        """解析Word文档"""
        try:
            from docx import Document
            
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs]
            tables = []
            
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    table_data.append(row_data)
                tables.append(table_data)
            
            return {
                'success': True,
                'text': '\n'.join(paragraphs),
                'tables': tables,
                'type': 'docx'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'docx'
            }
    
    @staticmethod
    def parse_xlsx(file_path: str) -> Dict[str, Any]:
        """解析Excel文档"""
        try:
            import openpyxl
            
            wb = openpyxl.load_workbook(file_path)
            sheets_data = {}
            
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                rows = []
                
                for row in sheet.iter_rows(values_only=True):
                    rows.append([str(cell) if cell is not None else '' for cell in row])
                
                sheets_data[sheet_name] = rows
            
            return {
                'success': True,
                'sheets': sheets_data,
                'sheet_names': wb.sheetnames,
                'type': 'xlsx'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'xlsx'
            }
    
    @staticmethod
    def auto_parse(file_path: str) -> Dict[str, Any]:
        """自动识别并解析文档"""
        ext = os.path.splitext(file_path)[1].lower()
        
        parsers = {
            '.pdf': DocumentParser.parse_pdf,
            '.png': DocumentParser.parse_image,
            '.jpg': DocumentParser.parse_image,
            '.jpeg': DocumentParser.parse_image,
            '.docx': DocumentParser.parse_docx,
            '.xlsx': DocumentParser.parse_xlsx,
        }
        
        parser = parsers.get(ext)
        
        if parser:
            return parser(file_path)
        else:
            return {
                'success': False,
                'error': f'不支持的文件类型: {ext}',
                'type': ext
            }
