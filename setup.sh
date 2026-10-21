#!/bin/bash
set -e

echo "=========================================="
echo "  PDF Editor Assistant - Setup"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Python
echo -e "${YELLOW}[1/4] Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo -e "${RED}Python not found. Please install Python 3.6+${NC}"
    exit 1
fi
echo -e "${GREEN}  Found: $($PYTHON --version)${NC}"

# Check pip
echo -e "${YELLOW}[2/4] Checking pip...${NC}"
if $PYTHON -m pip --version &> /dev/null; then
    PIP="$PYTHON -m pip"
else
    echo -e "${RED}pip not found. Please install pip${NC}"
    exit 1
fi
echo -e "${GREEN}  Found: $($PIP --version)${NC}"

# Check conversion backends (the app prepares the bridge by itself)
echo -e "${YELLOW}[3/4] Checking conversion backends...${NC}"
if $PYTHON -c "import pywpsrpc" &> /dev/null \
   && { [ -e /opt/kingsoft/wps-office/office6/librpcwpsapi_sysqt5.so ] \
        || [ -e /usr/lib/office6/librpcwpsapi_sysqt5.so ] \
        || [ -e /opt/apps/cn.wps.wps-office/files/kingsoft/wps-office/office6/librpcwpsapi_sysqt5.so ]; } \
   && command -v xvfb-run &> /dev/null; then
    echo -e "${GREEN}  WPS 静默后端可用${NC}"
else
    echo -e "${YELLOW}  WPS 转换支持未就绪（应用会自动补上，不用你编译）${NC}"
fi
if command -v soffice &> /dev/null; then
    echo -e "${GREEN}  LibreOffice 后端可用${NC}"
else
    echo -e "${YELLOW}  LibreOffice 未安装（应用内选择时会提示安装）${NC}"
fi
echo "  办公套件不随应用安装；应用里选 WPS 还是 LibreOffice 后，会自动配上对应的转换支持。"

# Install Python dependencies
echo -e "${YELLOW}[4/4] Installing Python dependencies...${NC}"
$PIP install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
echo -e "${GREEN}  Done${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}  Setup complete!${NC}"
echo "=========================================="
echo ""
echo "To run:"
echo "  python main.py"
echo ""
echo "To open a specific file:"
echo "  python main.py document.pdf"
echo ""
