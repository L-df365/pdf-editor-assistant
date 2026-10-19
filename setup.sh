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

# Check conversion backend: WPS (preferred) or LibreOffice
echo -e "${YELLOW}[3/4] Checking conversion backend...${NC}"
if $PYTHON -c "import pywpsrpc" &> /dev/null \
   && { [ -e /opt/kingsoft/wps-office/office6/librpcwpsapi_sysqt5.so ] \
        || [ -e /usr/lib/office6/librpcwpsapi_sysqt5.so ]; }; then
    echo -e "${GREEN}  Found: WPS Office + pywpsrpc (静默转换)${NC}"
    if ! command -v xvfb-run &> /dev/null; then
        echo -e "${YELLOW}  安装 Xvfb（避免转换时闪现 WPS 启动画面）...${NC}"
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq xvfb xauth
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y xorg-x11-server-Xvfb xauth
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm xorg-server-xvfb xorg-xauth
        fi
    fi
elif command -v soffice &> /dev/null; then
    echo -e "${GREEN}  Found: $(soffice --version)${NC}"
else
    echo -e "${YELLOW}  WPS 后端不可用，安装 LibreOffice 作为后备...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq libreoffice-core libreoffice-writer libreoffice-calc
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y libreoffice-core libreoffice-writer libreoffice-calc
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm libreoffice-fresh
    elif command -v brew &> /dev/null; then
        brew install --cask libreoffice
    else
        echo -e "${RED}  Cannot auto-install a backend. Install WPS + pywpsrpc or LibreOffice.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  Installed successfully${NC}"
fi

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
