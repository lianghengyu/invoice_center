@echo off
chcp 65001 >nul
REM ============================================
REM 发票识别系统 - Windows 一键安装脚本
REM 使用方法：双击本文件
REM ============================================
cd /d "%~dp0"

echo ======================================
echo   发票识别系统 - Windows 环境一键安装
echo ======================================

REM 1. 检查 Python
echo.
echo [1/3] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python！
    echo 请先访问 https://www.python.org/downloads/ 下载安装 Python 3.10 以上版本
    echo 安装时务必勾选 "Add Python to PATH" 选项！
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo [错误] Python 版本过低（需要 3.10 以上），请升级后重试
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo [OK] 检测到 %%v

REM 2. 创建虚拟环境
echo.
echo [2/3] 创建虚拟环境...
if exist .venv (
    echo [OK] 虚拟环境已存在，跳过创建
) else (
    python -m venv .venv
    echo [OK] 虚拟环境创建完成
)

REM 3. 安装依赖（使用阿里云镜像加速）
echo.
echo [3/3] 安装依赖包（约 1GB，视网速需 5~15 分钟，请耐心等待）...
.venv\Scripts\python.exe -m pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ -q
.venv\Scripts\pip.exe install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重新运行本脚本
    pause
    exit /b 1
)

echo.
echo ======================================
echo   安装完成！
echo   启动服务请双击: start_win.bat
echo ======================================
pause
