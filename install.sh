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
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

if [ "$(id -u)" -eq 0 ]; then
    TARGET_USER="${SUDO_USER:-$USER}"
    TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
    SUDO=""
else
    TARGET_USER="$USER"
    TARGET_HOME="$HOME"
    SUDO="sudo"
fi

run_as_user() {
    if [ "$(id -u)" -eq 0 ]; then
        sudo -u "$TARGET_USER" env HOME="$TARGET_HOME" "$@"
    else
        "$@"
    fi
}

echo -e "${YELLOW}[1/5] 安装系统依赖...${NC}"
if command -v apt-get &> /dev/null; then
    PKG="apt-get"
elif command -v dnf &> /dev/null; then
    PKG="dnf"
elif command -v pacman &> /dev/null; then
    PKG="pacman"
else
    echo -e "${RED}无法检测包管理器，请手动安装: python3 python3-tk python3-pip xdg-utils${NC}"
    exit 1
fi

if [ "$PKG" = "apt-get" ]; then
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq python3 python3-tk python3-pip \
        xdg-utils desktop-file-utils
elif [ "$PKG" = "dnf" ]; then
    $SUDO dnf install -y python3 python3-tkinter python3-pip \
        xdg-utils desktop-file-utils
else
    $SUDO pacman -S --noconfirm python tk python-pip \
        xdg-utils desktop-file-utils
fi
echo -e "${GREEN}  系统依赖已安装（不包含 WPS / LibreOffice）${NC}"

echo -e "${YELLOW}[2/5] 安装 Python 依赖...${NC}"
PIP_ARGS="-q -r $SCRIPT_DIR/requirements.txt -i $PIP_MIRROR"
if ! run_as_user python3 -m pip install --user $PIP_ARGS 2>/dev/null; then
    run_as_user python3 -m pip install --user --break-system-packages $PIP_ARGS
fi
echo -e "${GREEN}  Python 依赖已安装${NC}"
echo "  转换后端不随应用安装，首次选择缺失的后端时应用会提示下载。"

echo -e "${YELLOW}[3/5] 安装程序到 ${INSTALL_DIR}...${NC}"
$SUDO mkdir -p "$INSTALL_DIR"
$SUDO cp -r "$SCRIPT_DIR"/{main.py,core,gui,requirements.txt} "$INSTALL_DIR/"
[ -f "$SCRIPT_DIR/requirements-wps.txt" ] && \
    $SUDO cp "$SCRIPT_DIR/requirements-wps.txt" "$INSTALL_DIR/"
[ -f "$SCRIPT_DIR/README.md" ] && $SUDO cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/"
[ -f "$SCRIPT_DIR/README_CN.md" ] && $SUDO cp "$SCRIPT_DIR/README_CN.md" "$INSTALL_DIR/"
$SUDO chmod -R a+rX "$INSTALL_DIR"
echo -e "${GREEN}  程序已安装${NC}"

echo -e "${YELLOW}[4/5] 创建启动器和桌面项...${NC}"
$SUDO tee /usr/local/bin/pdf-editor > /dev/null << EOF
#!/bin/bash
cd ${INSTALL_DIR} || exit 1
exec python3 main.py "\$@"
EOF
$SUDO chmod +x /usr/local/bin/pdf-editor

# 独立批量打印：同一套界面，不启动页面管理
$SUDO tee /usr/local/bin/pdf-print > /dev/null << EOF
#!/bin/bash
cd ${INSTALL_DIR} || exit 1
exec python3 main.py --print "\$@"
EOF
$SUDO chmod +x /usr/local/bin/pdf-print

DESKTOP_FILE=$(mktemp)
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PDF 内嵌编辑助手
Name[zh_CN]=PDF 内嵌编辑助手
Comment=打开PDF，在任意位置插入Word/图片并实时预览
Comment[zh_CN]=打开PDF，在任意位置插入Word/图片并实时预览
Exec=/usr/local/bin/pdf-editor %U
TryExec=/usr/local/bin/pdf-editor
Icon=application-pdf
Terminal=false
Categories=Office;
MimeType=application/pdf;
StartupNotify=true
EOF

PRINT_DESKTOP_FILE=$(mktemp)
cat > "$PRINT_DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=批量打印
Name[zh_CN]=批量打印
Comment=把一批文件按各自参数打印出来
Comment[zh_CN]=把一批文件按各自参数打印出来
Exec=/usr/local/bin/pdf-print
TryExec=/usr/local/bin/pdf-print
Icon=application-pdf
Terminal=false
Categories=Office;
StartupNotify=true
EOF

$SUDO install -m 644 "$DESKTOP_FILE" /usr/share/applications/pdf-editor.desktop
$SUDO install -m 644 "$PRINT_DESKTOP_FILE" \
    /usr/share/applications/pdf-print.desktop
mkdir -p "$TARGET_HOME/.local/share/applications"
install -m 644 "$DESKTOP_FILE" "$TARGET_HOME/.local/share/applications/pdf-editor.desktop"
install -m 644 "$PRINT_DESKTOP_FILE" \
    "$TARGET_HOME/.local/share/applications/pdf-print.desktop"
rm -f "$DESKTOP_FILE" "$PRINT_DESKTOP_FILE"

if [ "$(id -u)" -eq 0 ]; then
    chown "$TARGET_USER:$TARGET_USER" \
        "$TARGET_HOME/.local/share/applications/pdf-editor.desktop" \
        "$TARGET_HOME/.local/share/applications/pdf-print.desktop"
fi
if command -v restorecon &> /dev/null; then
    $SUDO restorecon \
        "$TARGET_HOME/.local/share/applications/pdf-editor.desktop" \
        2>/dev/null || true
fi

$SUDO update-desktop-database /usr/share/applications/ 2>/dev/null || true
run_as_user update-desktop-database \
    "$TARGET_HOME/.local/share/applications/" 2>/dev/null || true
run_as_user xdg-mime default pdf-editor.desktop application/pdf 2>/dev/null || true

echo -e "${GREEN}  快捷方式已创建，并已注册到 PDF 的“打开方式”${NC}"

echo -e "${YELLOW}[5/5] 检查安装结果...${NC}"
if command -v desktop-file-validate &> /dev/null; then
    desktop-file-validate /usr/share/applications/pdf-editor.desktop || true
fi
echo "  PDF 默认打开方式: $(run_as_user xdg-mime query default application/pdf 2>/dev/null)"
run_as_user env PYTHONPATH="$INSTALL_DIR" python3 - << 'PYEOF' 2>/dev/null || true
from core.converter import backend_status
for b in backend_status():
    print('  后端 {}: {} {}'.format(
        b['name'], '可用' if b['available'] else '未安装',
        '' if b['available'] else '- ' + b['reason']))
PYEOF

echo ""
echo "=========================================="
echo -e "${GREEN}  安装成功！${NC}"
echo "=========================================="
echo ""
echo "使用方法："
echo "  1. 开始菜单搜索 “PDF 内嵌编辑助手”"
echo "  2. 右键 PDF → 打开方式 → PDF 内嵌编辑助手"
echo "  3. 命令行: pdf-editor 文件.pdf"
echo ""
echo "提示：WPS / LibreOffice 不随应用安装。在应用中选择未安装的"
echo "      后端时，会提示下载安装，安装完成后可立即重启生效。"
echo ""
