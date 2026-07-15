#!/bin/bash
set -e

# 进入脚本所在目录
cd "$(dirname "$0")"

echo "========================================"
echo "  Invoice OCR - Build macOS App"
echo "========================================"
echo ""
echo "This script requires Python 3.10+"
echo "First build needs network, about 10-30 minutes."
echo "Output: dist/发票识别/发票识别.app"
echo ""

# 1. 检测 Python（优先 python3，校验版本 >= 3.10）
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    if python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" &> /dev/null; then
        PYTHON_CMD="python3"
    fi
fi
if [ -z "$PYTHON_CMD" ] && command -v python &> /dev/null; then
    if python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" &> /dev/null; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "[ERROR] Python 3.10+ not found."
    echo ""
    echo "Please install Python 3.10+ from:"
    echo "  https://www.python.org/downloads/"
    echo ""
    echo "Then open a new terminal and run this script again."
    exit 1
fi

echo "Using: $PYTHON_CMD"
$PYTHON_CMD --version
echo ""

PIP_OPTS="-i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --timeout 120 --retries 10"

# 2. 创建/激活虚拟环境
if [ ! -f ".venv/bin/python3" ]; then
    echo "[1/5] Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
else
    echo "[1/5] Virtual environment already exists."
fi

source .venv/bin/activate

# 3. 安装依赖
echo "[2/5] Installing dependencies..."
python -m pip install $PIP_OPTS --upgrade pip
python -m pip install $PIP_OPTS -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    echo ""
    echo "This is usually a network timeout while downloading packages."
    echo "Please try again, or switch to another network / hotspot."
    exit 1
fi

# 4. 预热 OCR 模型
echo "[3/5] Preparing OCR models..."
python -c "from invoice_core import warmup_ocr_engine; warmup_ocr_engine(print); print('models ready')" || echo "[WARN] Model warmup failed. Build continues."

# 5. 清理旧构建
echo "[4/5] Cleaning old build..."
rm -rf build/invoice_app_macos dist/发票识别

# 6. 打包
echo "[5/5] Building macOS App, please wait..."
python -m PyInstaller --noconfirm invoice_app_macos.spec
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Build failed. Please send the error text above."
    exit 1
fi

echo ""
echo "========================================"
echo "  BUILD OK"
echo "========================================"
echo ""
echo "App path:"
echo "  $(pwd)/dist/发票识别/发票识别.app"
echo ""
echo "How to use:"
echo "  1. Copy the whole folder '发票识别'"
echo "  2. Double-click 发票识别.app"
echo "  3. Users do NOT need Python"
echo ""

if [ -d "dist/发票识别" ]; then
    open "dist/发票识别"
fi
