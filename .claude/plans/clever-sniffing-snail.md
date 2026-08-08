# 前端交互改造 — 双 Tab 页方案

## Context

用户要求将前端改为两个 Tab 页：
- **Tab1 图片识别**：上传图片 → 识别 → 结果展示在页面（保持现有功能，移除导出按钮）
- **Tab2 批量导出**：上传内嵌发票图片的 Excel → 后端提取图片 → OCR 识别 → 自动导出结果 Excel 下载

## 改动清单

### 1. 新增后端 API：`POST /api/invoice/batch-export`

文件：`routes/invoice_routes.py`

- 接收上传的 `.xlsx` 文件
- 用 `zipfile` 从 xlsx 的 `xl/media/` 目录提取所有嵌入图片
- 逐张调用已有的 `recognize()` + `parse_invoice()` 流程
- 调用已有的 `export_to_excel()` 生成结果 Excel
- 返回文件流下载，用 `after_this_request` 清理临时文件

### 2. 前端改为 el-tabs 双 Tab 页

文件：`templates/index.html` + `static/js/app.js`

**Tab1「图片识别」**：
- 保留现有上传 → 识别 → 表格展示逻辑
- 移除「导出 Excel」按钮

**Tab2「批量导出」**：
- 上传区域仅接受 `.xlsx` 文件，单文件上传
- 点击「开始处理」→ 显示进度 → 自动触发浏览器下载结果 Excel
- 展示处理状态：提取了多少张图片、成功/失败数

### 3. 不涉及的文件

- `config.py`、`services/image_processor.py`、`services/ocr_service.py`、`services/invoice_parser.py`、`services/excel_exporter.py` — 均复用现有逻辑，无需改动

## 验证

1. Tab1：上传图片 → 识别 → 页面展示结果（无导出按钮）
2. Tab2：上传含内嵌图片的 xlsx → 点击处理 → 浏览器自动下载结果 Excel
