# 发票识别系统

一个本地运行的发票识别工具：上传发票图片或 PDF，自动识别发票关键信息（发票号码、日期、金额、购销方等），支持双 OCR 引擎切换、批量处理和 Excel 导出。

---

## 🚀 快速开始（傻瓜式安装）

> 整个过程只需要做 3 件事：**装 Python → 双击安装脚本 → 双击启动脚本**。
> 全程需要联网，依赖包约 1GB，首次启动还会自动下载约 200MB 的 OCR 模型，请耐心等待。

### 🍎 Mac 版

#### 第一步：安装 Python（已装可跳过）

1. 打开「终端」（按 `Command + 空格`，输入 `终端` 回车）
2. 输入以下命令检查是否已安装：
   ```bash
   python3 --version
   ```
3. 如果显示 `Python 3.10.x` 以上版本，跳到第二步
4. 如果没有：浏览器打开 https://www.python.org/downloads/ ，点黄色「Download Python」按钮下载，双击安装包一路「继续」装完

#### 第二步：一键安装（仅首次需要）

在终端中执行（把路径换成项目实际位置）：

```bash
cd /path/to/invoice_python
chmod +x setup_mac.sh start_mac.sh
./setup_mac.sh
```

> 💡 小技巧：输入 `cd `（注意有空格）后，把项目文件夹直接**拖进终端窗口**，路径会自动填好，然后回车。

脚本会自动完成：检查 Python 版本 → 创建虚拟环境 → 用国内镜像安装全部依赖。
看到 `🎉 安装完成！` 就成功了。

#### 第三步：启动服务

```bash
./start_mac.sh
```

看到 `Running on http://127.0.0.1:8080` 后，打开浏览器访问：

```
http://localhost:8080
```

**停止服务**：在终端按 `Ctrl + C`。
以后每次使用，只需重复第三步。

---

### 🪟 Windows 版

#### 第一步：安装 Python（已装可跳过）

1. 浏览器打开 https://www.python.org/downloads/ ，点「Download Python」下载（3.10 以上版本）
2. 双击安装包，**⚠️ 关键：第一个界面务必勾选底部的 `Add Python to PATH`**，再点「Install Now」
3. 验证：按 `Win + R`，输入 `cmd` 回车，在黑窗口中输入 `python --version`，能显示版本号即成功

> 如果提示"不是内部或外部命令"，说明没勾选 `Add Python to PATH`，请卸载 Python 重装一遍。

#### 第二步：一键安装（仅首次需要）

用文件管理器打开项目文件夹，**双击 `setup_win.bat`**。

脚本会自动完成：检查 Python 版本 → 创建虚拟环境 → 用国内镜像安装全部依赖。
看到 `安装完成！` 就成功了（窗口按任意键关闭）。

#### 第三步：启动服务

**双击 `start_win.bat`**。

看到 `Running on http://127.0.0.1:8080` 后，打开浏览器访问：

```
http://localhost:8080
```

**停止服务**：直接关闭黑窗口。
以后每次使用，只需双击 `start_win.bat`。

> 💪 进阶（可选）：如果你的 Windows 电脑有 NVIDIA 显卡并已安装 CUDA 13.0，可以在安装完成后额外执行以下命令启用 GPU 加速：
> ```bat
> .venv\Scripts\pip.exe install -r requirements-gpu.txt --extra-index-url https://download.pytorch.org/whl/cu130
> ```

---

## 环境要求汇总

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS / Windows 10+ / Linux |
| Python | **3.10 及以上**（本项目在 3.13 上开发验证） |
| 内存 | 建议 8GB 以上 |
| 磁盘空间 | 约 3GB（依赖包 ~1GB + OCR 模型 ~300MB） |
| 网络 | 首次安装和首次启动需联网（下载依赖和模型） |
| GPU | 不需要。CPU 即可运行；Windows + NVIDIA 显卡可选装 GPU 版加速 |

依赖清单见 [requirements.txt](requirements.txt)（通用 CPU 版）和 [requirements-gpu.txt](requirements-gpu.txt)（Windows NVIDIA 可选）。

模型文件在首次启动时自动下载并缓存到项目的 `model/` 目录：
- PaddleOCR：PP-OCRv6 检测/识别/方向分类 3 个模型（国内百度源）
- EasyOCR：craft_mlt_25k / english_g2 / zh_sim_g2 3 个模型（国内 ModelScope 源）

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| OCR 引擎 | **PaddleOCR 3.7.0**（默认） | 百度开源 OCR，PP-OCRv6 模型，中文识别精度最高 |
| OCR 引擎 | **EasyOCR 1.7.2**（备选） | 基于 PyTorch，页面上可一键切换对比识别效果 |
| 图像处理 | **OpenCV** | 图片倾斜检测与校正（霍夫变换），提升 OCR 识别率 |
| PDF 解析 | **pypdfium2** | 将 PDF 每页渲染为图片，再交给 OCR 处理 |
| 字段提取 | **Python 正则表达式 (re)** | 从 OCR 文本中匹配发票号码、金额、日期、购销方等字段 |
| 后端框架 | **Flask** | 提供 REST API（上传识别、引擎切换、Excel 导出） |
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
OCR 文字识别（PaddleOCR / EasyOCR 可切换）
    │
    ▼
正则表达式 + 坐标锚点提取发票字段
    │
    ▼
返回结构化 JSON → 前端展示 / Excel 导出
```

### 识别字段

发票类型、发票代码、发票号码、开票日期、购买方名称/税号、销售方名称/税号、不含税金额、税额、价税合计、校验码。

---

## 功能说明

### 图片识别
- 上传发票图片（JPG / PNG / BMP / TIFF）或 PDF 文件，支持批量
- 左侧原图预览，右侧结构化字段展示，缺失字段高亮标注
- 可查看 OCR 原始识别文本
- 顶部可切换 PaddleOCR / EasyOCR 引擎对比识别效果
- 识别结果可一键保存为 Excel

### 导出识别结果
- 查看/下载/删除已保存的 Excel 结果文件
- 支持上传内嵌发票图片的 Excel 批量识别导出

---

## 常见问题（FAQ）

### Q：pip 安装依赖很慢或超时
安装脚本已默认使用阿里云镜像。如果仍然慢，手动执行：
```bash
# Mac
.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
# Windows
.venv\Scripts\pip.exe install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### Q：启动时报错 `No module named 'xxx'`
依赖没装全，重新运行一遍安装脚本（`setup_mac.sh` / `setup_win.bat`）即可，已装过的包会自动跳过。

### Q：Mac 上切换引擎后服务崩溃 / 报 segmentation fault
项目代码已内置修复（设置 `KMP_DUPLICATE_LIB_OK=TRUE` 规避 paddle 与 torch 的 libomp 冲突）。请确保使用 `start_mac.sh` 启动，不要绕过脚本手动启动。

### Q：Mac 上不要安装 requirements-gpu.txt
`requirements-gpu.txt` 里是 CUDA 版依赖，Mac 没有 NVIDIA 显卡装不上。Mac 用默认的 `requirements.txt` 即可，EasyOCR 会自动使用 Apple 芯片的 MPS 加速。

### Q：启动时端口 8080 被占用
修改 `app.py` 最后一行的端口号（如改为 9090）：
```python
app.run(host='0.0.0.0', port=9090, debug=True, use_reloader=False)
```

### Q：首次启动卡在下载模型
首次启动需下载约 200MB 模型（Paddle + EasyOCR），网速慢时可能需要几分钟，请勿关闭窗口。下载完成后会缓存到 `model/` 目录，之后启动都是秒开。

### Q：Windows 双击 .bat 窗口一闪而过
说明报错了。右键 `setup_win.bat` → 编辑，确认无误后：按 `Win + R` 输入 `cmd`，把 bat 文件拖入黑窗口回车执行，即可看到具体错误信息。

### Q：识别结果不准确
- 确保图片清晰、不模糊，尽量正向拍摄
- PDF 格式的电子发票识别效果最好
- 可尝试切换另一个 OCR 引擎对比（PaddleOCR 对中文发票效果通常更好）

### Q：页面打不开
- 确认终端/黑窗口中服务正在运行（没有报错、没被关闭）
- 确认地址是 `http://localhost:8080`（是 http 不是 https）

---

## 项目结构

```
invoice_python/
├── app.py                  # 应用入口：预加载 OCR 引擎 + 启动 Flask（端口 8080）
├── config.py               # 配置：上传目录、大小限制、默认 OCR 引擎
├── requirements.txt        # 通用依赖（CPU 版，Mac/Windows 通用）
├── requirements-gpu.txt    # GPU 版依赖（仅 Windows/Linux + NVIDIA 可选）
├── setup_mac.sh            # Mac 一键安装脚本
├── start_mac.sh            # Mac 启动脚本
├── setup_win.bat           # Windows 一键安装脚本（双击运行）
├── start_win.bat           # Windows 启动脚本（双击运行）
├── routes/
│   └── invoice_routes.py   # API 接口（识别、引擎切换、结果保存/导出）
├── services/
│   ├── image_processor.py  # OpenCV 图像预处理（倾斜校正、PDF 转图）
│   ├── ocr_manager.py      # 双引擎统一调度（加载/释放/切换）
│   ├── ocr_service.py      # PaddleOCR 封装（模型自动下载、识别）
│   ├── easyocr_service.py  # EasyOCR 封装（模型自动下载、识别）
│   ├── invoice_parser.py   # 发票字段解析（正则 + 坐标锚点定位）
│   └── excel_exporter.py   # openpyxl 生成 Excel 导出文件
├── static/
│   └── index.html          # 前端页面（Vue 3 + Element Plus，CDN 引入）
├── model/                  # OCR 模型缓存目录（首次启动自动下载生成）
├── uploads/                # 上传临时目录（自动清理）
└── saved_results/          # 已保存的识别结果 Excel
```

## 支持的发票类型

增值税普通发票 / 增值税专用发票 / 增值税电子普通发票 / 增值税电子专用发票 / 全电发票（数电票）

## 支持的文件格式

- 图片：JPG、PNG、BMP、TIFF
- 文档：PDF（多页自动逐页识别）
- 批量导出：XLSX（内嵌图片）
