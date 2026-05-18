# 文档数据提取系统

一个基于 Vue + Flask + OpenRouter 的智能文档数据提取系统，支持多种文档类型、批量处理和即时通讯集成。

## 功能特性

### 1. 多场景通用提取能力
- **财务类**: 发票、付款水单、银行回单
- **法务类**: 法律合同、补充协议、合规文件
- **运营类**: 楼宇设施报告、维保记录
- **租约类**: 租赁合同、扫描件

### 2. 自定义提取模板
- 自然语言定义提取规则
- 字段映射和校验规则配置
- 模板复用和管理

### 3. 批量文档处理
- 多文件并行处理
- 自动模板匹配
- 处理状态跟踪
- 结果导出（JSON/CSV）

### 4. 即时通讯集成
- 微信群/IM消息解析
- 碎片信息提炼
- CRM数据导出

## 技术栈

- **前端**: Vue 3 + Element Plus
- **后端**: Flask + SQLAlchemy
- **AI引擎**: OpenRouter API
- **数据库**: SQLite

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

编辑 `.env` 文件，填入你的 OpenRouter API Key：

```
OPENROUTER_API_KEY=your-actual-api-key-here
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
├── routes/               # API路由
│   ├── document_routes.py
│   ├── template_routes.py
│   ├── batch_routes.py
│   └── chat_routes.py
├── services/             # 业务逻辑
│   ├── extraction_engine.py
│   └── template_generator.py
├── utils/                 # 工具模块
│   └── document_parser.py
├── uploads/              # 文件上传目录
└── frontend/             # Vue前端应用
    ├── src/
    │   ├── views/        # 页面组件
    │   ├── router/       # 路由配置
    │   └── main.js       # 应用入口
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

### 即时通讯
- `POST /api/chat/process` - 处理单条消息
- `GET /api/chat/list` - 获取消息列表
- `POST /api/chat/export` - 导出CRM数据

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

### 处理即时通讯消息

1. 进入"即时通讯"页面
2. 输入微信群/邮件内容
3. AI自动提取结构化信息
4. 发送到CRM系统

## 配置说明

### OpenRouter API

系统使用 OpenRouter 作为AI引擎，你需要：

1. 访问 https://openrouter.ai/ 注册账号
2. 获取API Key
3. 在 `.env` 文件中配置

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

## 故障排除

### 问题：API调用失败

- 检查 OpenRouter API Key 是否正确配置
- 确认网络连接正常
- 查看后端日志中的错误信息

### 问题：文件上传失败

- 检查文件大小是否超过限制（默认16MB）
- 确认文件格式是否支持
- 检查上传目录权限

### 问题：提取结果不准确

- 优化模板字段描述
- 调整验证规则
- 使用更具体的文档样本

## 许可证

MIT License

## 联系方式

如有问题，请提交Issue。
