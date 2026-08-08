#!/bin/bash
# ============================================
# 发票识别系统 - Mac 启动脚本
# 使用方法：./start_mac.sh
# ============================================
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "❌ 未找到虚拟环境，请先运行 ./setup_mac.sh 完成安装"
    exit 1
fi

# 避免 paddle 与 torch 的 libomp 冲突导致段错误
export KMP_DUPLICATE_LIB_OK=TRUE

echo "正在启动发票识别系统..."
echo "首次启动会自动下载 OCR 模型（约 200MB），请耐心等待"
echo "启动成功后，浏览器访问: http://localhost:8080"
echo "按 Ctrl+C 停止服务"
echo ""
.venv/bin/python app.py
