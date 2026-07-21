# 发票识别系统

一个本地运行的发票识别工具，上传发票图片或 PDF，自动识别发票关键信息（发票号码、日期、金额、购销方等），支持批量处理和 Excel 导出。

---

## 功能说明

### 图片识别（Tab1）
- 上传发票图片（JPG / PNG / BMP / TIFF）或 PDF 文件
- 支持批量上传多张
- 自动识别发票类型、号码、日期、金额、购销方等信息
- 页面表格展示识别结果

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
cd /Users/lianghy/work/zl_project/invoice_python
```

> 如果项目在其他位置，请替换为实际路径。

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
cd /Users/lianghy/work/zl_project/invoice_python
.venv/bin/python app.py
```

然后浏览器打开 `http://localhost:8080`。

**关闭服务：** 在终端按 `Ctrl + C`。

---

## 使用方法

### 图片识别

1. 打开页面，默认在「图片识别」Tab
2. 点击上传区域或拖拽文件，选择一张或多张发票图片/PDF
3. 点击「开始识别」按钮
4. 等待识别完成，结果会展示在下方表格中
5. 点击表格行左侧的展开箭头，可查看完整信息和 OCR 原始文本

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
├── app.py                  # 应用入口
├── config.py               # 配置文件
├── requirements.txt        # Python 依赖
├── routes/
│   └── invoice_routes.py   # API 接口
├── services/
│   ├── image_processor.py  # 图像预处理
│   ├── ocr_service.py      # OCR 识别引擎
│   ├── invoice_parser.py   # 发票字段解析
│   └── excel_exporter.py   # Excel 导出
└── static/
    └── index.html          # 前端页面
```
