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

# 检查 Docker
echo -e "${YELLOW}[1/5] 检查 Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker 未安装。正在安装...${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo -e "${YELLOW}请注销并重新登录以使 Docker 权限生效，然后重新运行此脚本${NC}"
    exit 1
fi
echo -e "${GREEN}  Docker 已就绪${NC}"

# 构建镜像
echo -e "${YELLOW}[2/5] 构建 Docker 镜像...${NC}"
cd "$SCRIPT_DIR"
docker build -t pdf-editor-assistant . 2>&1 | tail -1
echo -e "${GREEN}  构建完成${NC}"

# 复制文件到安装目录
echo -e "${YELLOW}[3/5] 安装到 ${INSTALL_DIR}...${NC}"
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r . "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/start.sh"
echo -e "${GREEN}  安装完成${NC}"

# 创建启动脚本
echo -e "${YELLOW}[4/5] 创建启动器...${NC}"
sudo tee /usr/local/bin/pdf-editor > /dev/null << 'EOF'
#!/bin/bash
exec /opt/pdf-editor-assistant/start.sh "$@"
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
Exec=/opt/pdf-editor-assistant/start.sh %U
Icon=application-pdf
Terminal=false
Categories=Office;Utility;
MimeType=application/pdf;
EOF

# 复制到用户目录
mkdir -p ~/.local/share/applications
cp /usr/share/applications/pdf-editor.desktop ~/.local/share/applications/

# 注册为 PDF 默认应用
xdg-mime default pdf-editor.desktop application/pdf 2>/dev/null || true

# 更新桌面数据库
update-desktop-database /usr/share/applications/ 2>/dev/null || true
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

echo -e "${GREEN}  快捷方式已创建${NC}"

# 完成
echo -e "${YELLOW}[5/5] 安装完成！${NC}"
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
echo "注意：首次使用请注销并重新登录，使 Docker 权限生效"
echo ""
