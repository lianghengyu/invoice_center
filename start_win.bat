@echo off
chcp 65001 >nul
REM ============================================
REM 发票识别系统 - Windows 启动脚本
REM 使用方法：双击本文件
REM ============================================
cd /d "%~dp0"

if not exist .venv (
    echo [错误] 未找到虚拟环境，请先双击 setup_win.bat 完成安装
    pause
    exit /b 1
)

REM 避免 paddle 与 torch 的 OpenMP 运行库冲突
set KMP_DUPLICATE_LIB_OK=TRUE

echo 正在启动发票识别系统...
echo 首次启动会自动下载 OCR 模型（约 200MB），请耐心等待
echo 启动成功后，浏览器访问: http://localhost:8080
echo 关闭本窗口即可停止服务
echo.
.venv\Scripts\python.exe app.py
pause
