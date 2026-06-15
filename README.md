# 文档数据提取系统

一个基于 Vue + Flask + OpenRouter/阿里云百炼 的智能文档数据提取系统，支持多种文档类型、批量处理和租约提取。

## 功能特性

### 1. 多场景通用提取能力
- **财务类**: 发票、付款水单、银行回单
- **法务类**: 法律合同、补充协议、合规文件
- **运营类**: 楼宇设施报告、维保记录
- **租约类**: 租赁合同、扫描件（支持OCR）

### 2. 自定义提取模板
- 自然语言定义提取规则
- 字段映射和校验规则配置
- 模板复用和管理

### 3. 批量文档处理
- 多文件并行处理
- 自动模板匹配
- 处理状态跟踪
- 结果导出（JSON/CSV/XLSX）
- ZIP文件自动解压处理

### 4. 租约专项提取
- 支持上传规则Excel + 合同PDF
- 按指定模板字段自动抽取
- 生成标准格式Excel输出
- 支持扫描件OCR识别

### 5. 语音输入支持
- 前端ChatBot支持语音输入
- 自动转换为文字并填入输入框

## 技术栈

- **前端**: Vue 3 + Element Plus + Vite
- **后端**: Flask + SQLAlchemy + Jinja2
- **AI引擎**: OpenRouter API / 阿里云百炼 DashScope
- **数据库**: SQLite
- **文档解析**: pdfplumber, pytesseract, PIL, openpyxl
- **OCR支持**: 百炼VL模型（qwen-vl-plus等）

## 快速开始

### 1. 安装后端依赖

```bash
cd data_extraction
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，根据需要选择以下配置之一：

#### 方案A：使用OpenRouter
```
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=your-preferred-model
```

#### 方案B：使用阿里云百炼
```
LLM_PROVIDER=bailian
BAILIAN_API_KEY=your-bailian-api-key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_MODEL=qwen3.6-plus
```

#### OCR配置（用于扫描件）
```
PDF_OCR_ENABLED=1
BAILIAN_OCR_MODEL=qwen-vl-plus
PDF_OCR_TEXT_THRESHOLD=200
PDF_OCR_MAX_PAGES=5
PDF_OCR_RESOLUTION=180
LLM_HTTP_TIMEOUT=180
```

### 3. 启动后端服务

```bash
python app.py
```

后端服务将在 http://localhost:5000 启动

### 4. 安装前端依赖并启动

```bash
cd frontend
npm install
npm run dev
```

前端应用将在 http://localhost:3000 启动

### 5. 访问系统

打开浏览器访问 http://localhost:3000

## 项目结构

```
data_extraction/
├── app.py                 # Flask应用入口
├── config.py             # 配置文件
├── models.py             # 数据库模型
├── requirements.txt      # Python依赖
├── .env                  # 环境变量配置
├── .env.example          # 环境变量示例
├── .gitignore           # Git忽略文件
├── Dockerfile           # Docker配置
├── README.md            # 项目说明
├── routes/              # API路由
│   ├── document_routes.py
│   ├── template_routes.py
│   ├── batch_routes.py
│   └── chat_routes.py
├── services/            # 业务逻辑
│   ├── extraction_engine.py
│   ├── template_generator.py
│   ├── lease_pdf_extractor.py
│   └── lease_xlsx_extractor.py
├── utils/               # 工具模块
│   └── document_parser.py
├── uploads/             # 文件上传目录
└── frontend/            # Vue前端应用
    ├── src/
    │   ├── views/       # 页面组件
    │   ├── router/      # 路由配置
    │   └── main.js      # 应用入口
    └── package.json
```

## API接口

### 文档管理
- `POST /api/documents/upload` - 上传文档
- `GET /api/documents/list` - 获取文档列表
- `POST /api/documents/<id>/extract` - 提取文档数据

### 模板管理
- `POST /api/templates` - 创建模板
- `GET /api/templates/list` - 获取模板列表
- `POST /api/templates/generate-from-description` - AI生成模板

### 批量处理
- `POST /api/batch/upload` - 上传批量文件
- `POST /api/batch/<id>/process` - 开始处理
- `GET /api/batch/<id>/results` - 获取处理结果
- `GET /api/batch/<id>/export?format=json|csv|xlsx` - 导出结果

### 租约提取
- 上传规则Excel + 合同PDF触发自动提取
- 生成标准格式Excel并提供下载链接

## 使用说明

### 创建提取模板

1. 进入"模板管理"页面
2. 点击"创建模板"按钮
3. 选择文档类型（如：发票、租约）
4. 添加需要提取的字段
5. 配置验证规则（可选）
6. 保存模板

### 上传并提取文档

1. 进入"文档上传"页面
2. 选择已创建的模板
3. 拖拽或选择要上传的文件
4. 点击"上传并提取"
5. 查看提取结果

### 批量处理

1. 进入"批量处理"页面
2. 上传ZIP包或多个文件
3. 选择提取模板
4. 开始处理
5. 导出结果

### 租约专项提取

1. 在聊天页面上传"租约字段提取规则.xlsx"
2. 同时上传一个或多个合同PDF
3. 发送任意文字（如"开始"）
4. 系统自动按规则提取并生成Excel
5. 通过download_url下载结果

## 配置说明

### OpenRouter API

系统使用 OpenRouter 作为AI引擎，你需要：

1. 访问 https://openrouter.ai/ 注册账号
2. 获取API Key
3. 在 `.env` 文件中配置

### 阿里云百炼配置

系统支持阿里云百炼，你需要：

1. 访问 https://www.aliyun.com/product/dashscope 注册账号
2. 获取API Key
3. 在 `.env` 文件中配置百炼相关参数

### 支持的文档格式

- PDF文档 (.pdf)
- 图片文件 (.png, .jpg, .jpeg)
- Word文档 (.docx)
- Excel表格 (.xlsx)
- ZIP压缩包 (.zip)

### 置信度阈值

默认置信度阈值为 0.7，可以通过修改 `.env` 中的 `CONFIDENCE_THRESHOLD` 调整。

## 开发说明

### 添加新的文档类型

1. 在 `routes/template_routes.py` 的 `DOCUMENT_TYPES` 中添加新类型
2. 在 `utils/document_parser.py` 中添加对应的解析器
3. 在前端添加类型选择选项

### 自定义提取逻辑

在 `services/extraction_engine.py` 中修改 `_build_extraction_prompt` 方法来优化提取提示词。

### 租约提取逻辑

在 `services/lease_pdf_extractor.py` 中实现租约专项提取逻辑。

## 故障排除

### 问题：API调用失败

- 检查 OpenRouter/Bailian API Key 是否正确配置
- 确认网络连接正常
- 检查模型名称是否正确

### 问题：扫描件提取失败

- 确认已启用OCR功能
- 检查OCR模型配置
- 调整PDF_OCR_TEXT_THRESHOLD参数

### 问题：500错误

- 检查文件名是否包含特殊字符
- 确认上传文件格式支持
- 查看后端日志获取详细错误信息

## 部署

### Docker部署

```bash
docker build -t data-extraction .
docker run --rm -p 5000:5000 data-extraction
```

### 环境变量

确保在部署环境中正确配置所有必要的环境变量。

## 架构图

```
┌─────────────────┐    HTTP    ┌──────────────────┐
│   Frontend      │◄──────────►│   Backend        │
│   (Vue 3)       │            │   (Flask)        │
└─────────────────┘            └──────────────────┘
                                        │
                                        ▼
                            ┌─────────────────────────┐
                            │   AI Services           │
                            │   (OpenRouter/Bailian)  │
                            └─────────────────────────┘
                                        │
                                        ▼
                            ┌─────────────────────────┐
                            │   Document Processing   │
                            │   (pdfplumber, PIL, etc)│
                            └─────────────────────────┘
                                        │
                                        ▼
                            ┌─────────────────────────┐
                            │   Database & Storage    │
                            │   (SQLite, uploads/)    │
                            └─────────────────────────┘
```

前端负责用户界面和交互，后端处理业务逻辑和API请求，AI服务提供文档解析和数据提取能力，文档处理模块负责各种格式文档的解析，数据库和存储模块负责数据持久化。