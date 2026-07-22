# 发票识别系统

一个本地运行的发票识别工具，上传发票图片或 PDF，自动识别发票关键信息（发票号码、日期、金额、购销方等），支持批量处理和 Excel 导出。

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| OCR 引擎 | **PaddleOCR 3.7.0** | 百度开源 OCR，使用 PP-OCRv6 模型，中文识别精度最高 |
| 图像处理 | **OpenCV** | 图片倾斜检测与校正（霍夫变换），提升 OCR 识别率 |
| PDF 解析 | **pypdfium2** | 将 PDF 每页渲染为图片，再交给 OCR 处理 |
| 字段提取 | **Python 正则表达式 (re)** | 从 OCR 文本中匹配发票号码、金额、日期、购销方等字段 |
| 后端框架 | **Flask** | 提供 REST API（上传识别、Excel 导出） |
| Excel 处理 | **openpyxl** | 读取 Excel 内嵌图片、生成带样式的 .xlsx 导出文件 |
| 前端 | **Vue 3 + Element Plus** | CDN 引入，无需 Node.js 构建环境 |

### 识别流程

```
上传图片/PDF
    │
    ▼
OpenCV 倾斜校正（PDF 先转图片）
    │
    ▼
PaddleOCR 文字识别（PP-OCRv6 模型）
    │
    ▼
正则表达式提取发票字段
    │
    ▼
返回结构化 JSON → 前端表格展示 / Excel 导出
```

### 识别字段

| 字段 | 匹配方式 |
|------|---------|
| 发票类型 | 关键词匹配（增值税普通/专用/电子/全电发票） |
| 发票代码 | `发票代码：(\d{10,12})` |
| 发票号码 | `发票号码：(\d{8,20})` |
| 开票日期 | `(\d{4})年(\d{1,2})月(\d{1,2})日` |
| 购买方/销售方 | "名称"关键词后的文本 + 区域分段 |
| 纳税人识别号 | `[0-9A-Z]{15,20}` 格式匹配 |
| 金额/税额/价税合计 | `¥` 符号 + 金额格式，结合上下文关键词定位 |
| 校验码 | `校验码：(\d{20})` |

---

## 功能说明

### 图片识别（Tab1）
- 上传发票图片（JPG / PNG / BMP / TIFF）或 PDF 文件
- 支持批量上传多张
- 左右布局：左侧文件列表带缩略图预览，右侧展示识别结果表格
- 展开表格行可查看完整字段和 OCR 原始文本

### 批量导出（Tab2）
- 上传一个包含发票图片的 Excel 文件（.xlsx）
- 系统自动提取 Excel 中嵌入的所有图片
- 逐张识别后生成新的 Excel 文件，自动下载

---

## 环境准备

### 1. 安装 Python

本项目需要 **Python 3.9 或以上版本**。

**检查是否已安装：**

打开「终端」（在启动台搜索"终端"，或按 `Command + 空格` 输入 `terminal`），输入：

```bash
python3 --version
```

如果显示类似 `Python 3.13.12` 就说明已安装，可跳过下一步。

**如果未安装：**

1. 打开浏览器访问 https://www.python.org/downloads/
2. 点击黄色的 「Download Python」按钮，下载安装包
3. 双击安装包，一路点「继续」直到安装完成

---

## 运行项目

以下所有命令都在「终端」中执行。

### 第一步：进入项目目录

```bash
cd /path/to/invoice_python
```

> 请将 `/path/to/invoice_python` 替换为项目实际所在的路径。

### 第二步：创建虚拟环境（仅首次需要）

```bash
python3 -m venv .venv
```

### 第三步：安装依赖（仅首次需要）

```bash
.venv/bin/pip install -r requirements.txt
```

> 这一步会下载约 500MB 的依赖包，请确保网络畅通，耐心等待几分钟。
>
> 如果下载速度很慢，可以使用国内镜像源：
> ```bash
> .venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
> ```

### 第四步：启动服务

```bash
.venv/bin/python app.py
```

启动后会看到类似输出：

```
正在预加载 OCR 模型...
OCR 模型加载完成，启动服务...
 * Running on http://127.0.0.1:8080
```

> 首次启动会自动下载 OCR 识别模型（约 100MB），需要等待一两分钟。后续启动会使用缓存，速度更快。

### 第五步：打开浏览器使用

在浏览器地址栏输入：

```
http://localhost:8080
```

即可看到发票识别系统的页面。

---

## 日常使用

每次使用只需要执行两条命令：

```bash
cd /path/to/invoice_python
.venv/bin/python app.py
```

然后浏览器打开 `http://localhost:8080`。

**关闭服务：** 在终端按 `Ctrl + C`。

---

## 使用方法

### 图片识别

1. 打开页面，默认在「图片识别」Tab
2. 在左侧上传区域点击或拖拽，选择一张或多张发票图片/PDF
3. 左侧会显示文件列表和缩略图预览
4. 点击「开始识别」按钮
5. 等待识别完成，右侧展示统计卡片和结果表格
6. 点击表格行左侧的展开箭头，可查看完整信息和 OCR 原始文本

### 批量导出

1. 切换到「批量导出」Tab
2. 上传一个包含发票图片的 .xlsx 文件（图片需要插入在 Excel 单元格中）
3. 点击「开始处理并导出」
4. 处理完成后，浏览器会自动下载一个包含识别结果的 Excel 文件

---

## 支持的发票类型

- 增值税普通发票
- 增值税专用发票
- 增值税电子普通发票
- 增值税电子专用发票
- 全电发票（数电票）

## 支持的文件格式

- 图片：JPG、PNG、BMP、TIFF
- 文档：PDF
- 批量导出：XLSX（内嵌图片）

---

## 常见问题

### Q：启动时报错 `No module named 'xxx'`
重新安装依赖：
```bash
.venv/bin/pip install -r requirements.txt
```

### Q：启动时端口被占用
修改 `app.py` 最后一行的端口号（如改为 9090）：
```python
app.run(host='0.0.0.0', port=9090, debug=True, use_reloader=False)
```

### Q：识别结果不准确
- 确保图片清晰、不模糊
- 图片尽量正向拍摄，避免大角度倾斜
- PDF 格式的电子发票识别效果最好

### Q：页面打不开
- 确认终端中服务正在运行（没有报错）
- 确认浏览器地址是 `http://localhost:8080`（注意是 http 不是 https）

---

## 项目结构

```
invoice_python/
├── app.py                  # 应用入口，Flask 服务启动 + OCR 模型预加载
├── config.py               # 配置文件（上传目录、文件大小限制）
├── requirements.txt        # Python 依赖清单
├── routes/
│   └── invoice_routes.py   # API 接口（识别、批量导出）
├── services/
│   ├── image_processor.py  # OpenCV 图像预处理（倾斜校正）
│   ├── ocr_service.py      # PaddleOCR 封装（模型加载、文字识别）
│   ├── invoice_parser.py   # 正则表达式提取发票字段
│   └── excel_exporter.py   # openpyxl 生成 Excel 导出文件
└── static/
    └── index.html          # 前端页面（Vue 3 + Element Plus）
```
