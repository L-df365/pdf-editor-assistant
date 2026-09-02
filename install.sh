#!/bin/bash
set -e

echo "=========================================="
echo "  PDF 内嵌编辑助手 - 安装程序"
echo "=========================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="/opt/pdf-editor-assistant"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 安装依赖
echo -e "${YELLOW}[1/4] 安装依赖...${NC}"

# 检测包管理器
if command -v apt-get &> /dev/null; then
    PKG="apt-get"
elif command -v dnf &> /dev/null; then
    PKG="dnf"
elif command -v pacman &> /dev/null; then
    PKG="pacman"
else
    echo -e "${RED}无法检测包管理器，请手动安装: python3 python3-tk python3-pip libreoffice-core libreoffice-writer libreoffice-calc${NC}"
    exit 1
fi

# 安装系统依赖
echo -e "  安装 Python3 和 LibreOffice..."
if [ "$PKG" = "apt-get" ]; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-tk python3-pip libreoffice-core libreoffice-writer libreoffice-calc
    # 隐藏 LibreOffice 开始菜单项（只用内核，不要 UI）
    sudo rm -f /usr/share/applications/libreoffice*.desktop
    sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true
elif [ "$PKG" = "dnf" ]; then
    sudo dnf install -y python3 python3-tkinter python3-pip libreoffice-core libreoffice-writer libreoffice-calc
    sudo rm -f /usr/share/applications/libreoffice*.desktop
elif [ "$PKG" = "pacman" ]; then
    sudo pacman -S --noconfirm python python-tk python-pip libreoffice-fresh
    sudo rm -f /usr/share/applications/libreoffice*.desktop
fi
echo -e "${GREEN}  系统依赖已安装${NC}"

# 安装 Python 依赖
echo -e "  安装 Python 包..."
pip3 install -q -r "$SCRIPT_DIR/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null || \
pip3 install -q -r "$SCRIPT_DIR/requirements.txt" --break-system-packages 2>/dev/null || \
pip3 install -q -r "$SCRIPT_DIR/requirements.txt"
echo -e "${GREEN}  Python 依赖已安装${NC}"

# 安装程序
echo -e "${YELLOW}[2/4] 安装程序...${NC}"
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$SCRIPT_DIR"/{main.py,core,gui,requirements.txt} "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/main.py"
echo -e "${GREEN}  程序已安装到 ${INSTALL_DIR}${NC}"

# 创建启动命令
echo -e "${YELLOW}[3/4] 创建启动器...${NC}"
sudo tee /usr/local/bin/pdf-editor > /dev/null << EOF
#!/bin/bash
cd ${INSTALL_DIR}
python3 main.py "\$@"
EOF
sudo chmod +x /usr/local/bin/pdf-editor

# 创建桌面快捷方式
sudo tee /usr/share/applications/pdf-editor.desktop > /dev/null << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PDF 内嵌编辑助手
Name[zh_CN]=PDF 内嵌编辑助手
Comment=打开PDF，在任意位置插入Word/图片并实时预览
Comment[zh_CN]=打开PDF，在任意位置插入Word/图片并实时预览
Exec=python3 ${INSTALL_DIR}/main.py %U
Icon=application-pdf
Terminal=false
Categories=Office;Utility;
MimeType=application/pdf;
EOF

mkdir -p "$HOME/.local/share/applications"
cp /usr/share/applications/pdf-editor.desktop "$HOME/.local/share/applications/"
chown -R $USER:$USER "$HOME/.local/share/applications/pdf-editor.desktop"

# 注册为 PDF 默认应用
su - $USER -c "xdg-mime default pdf-editor.desktop application/pdf" 2>/dev/null || true

update-desktop-database /usr/share/applications/ 2>/dev/null || true
su - $USER -c "update-desktop-database ~/.local/share/applications/" 2>/dev/null || true
echo -e "${GREEN}  快捷方式已创建${NC}"

# 完成
echo -e "${YELLOW}[4/4] 安装完成！${NC}"
echo ""
echo "=========================================="
echo -e "${GREEN}  安装成功！${NC}"
echo "=========================================="
echo ""
echo "使用方法："
echo "  1. 从开始菜单搜索 'PDF 内嵌编辑助手'"
echo "  2. 右键 PDF 文件 → 打开方式 → PDF 内嵌编辑助手"
echo "  3. 命令行: pdf-editor 文件.pdf"
echo ""
