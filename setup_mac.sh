#!/bin/bash
# ============================================
# 发票识别系统 - Mac 一键安装脚本
# 使用方法：双击本文件，或在终端执行 ./setup_mac.sh
# ============================================
set -e
cd "$(dirname "$0")"

echo "======================================"
echo "  发票识别系统 - Mac 环境一键安装"
echo "======================================"

# 1. 检查 Python
echo ""
echo "[1/3] 检查 Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3！"
    echo "请先访问 https://www.python.org/downloads/ 下载安装 Python 3.10+，然后重新运行本脚本。"
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ 检测到 Python $PY_VER"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
    echo "❌ Python 版本过低（需要 3.10 以上），请升级后重试。"
    exit 1
}

# 2. 创建虚拟环境
echo ""
echo "[2/3] 创建虚拟环境..."
if [ -d ".venv" ]; then
    echo "✅ 虚拟环境已存在，跳过创建"
else
    python3 -m venv .venv
    echo "✅ 虚拟环境创建完成"
fi

# 3. 安装依赖（使用阿里云镜像加速）
echo ""
echo "[3/3] 安装依赖包（约 1GB，视网速需 5~15 分钟，请耐心等待）..."
.venv/bin/pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ -q
.venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

echo ""
echo "======================================"
echo "  🎉 安装完成！"
echo "  启动服务请运行: ./start_mac.sh"
echo "======================================"
