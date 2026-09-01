#!/bin/bash
# 将系统 LibreOffice 打包为便携版到应用目录
# 打包后可以删除系统 LibreOffice

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORTABLE_DIR="$SCRIPT_DIR/libreoffice_portable"

echo "=========================================="
echo "  LibreOffice 便携化工具"
echo "=========================================="
echo ""

# 检查系统 LibreOffice
if ! command -v soffice &> /dev/null; then
    echo "错误: 系统未安装 LibreOffice"
    echo "请先安装: sudo apt install libreoffice-core libreoffice-writer libreoffice-calc"
    exit 1
fi

SYS_LO="/usr/lib/libreoffice"
if [ ! -d "$SYS_LO" ]; then
    echo "错误: 未找到 $SYS_LO"
    exit 1
fi

echo "系统 LibreOffice: $(soffice --version)"
echo "目标目录: $PORTABLE_DIR"
echo ""

# 创建便携目录
echo "[1/3] 复制 LibreOffice 核心文件..."
mkdir -p "$PORTABLE_DIR"

# 复制 program 目录（二进制和库）
echo "  复制 program/ ..."
cp -r "$SYS_LO/program" "$PORTABLE_DIR/"

# 复制 share 目录（过滤器、模板等）
echo "  复制 share/ ..."
cp -r "$SYS_LO/share" "$PORTABLE_DIR/"

# 复制必要的配置文件
echo "  复制配置文件..."
cp -r "$SYS_LO/presets" "$PORTABLE_DIR/" 2>/dev/null || true

echo ""
echo "[2/3] 创建启动脚本..."

# 创建启动脚本
cat > "$PORTABLE_DIR/soffice" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export URE_BOOTSTRAP="file://$SCRIPT_DIR/program/fundamentalrc"
export LibreOffice cmd="--norestore"
exec "$SCRIPT_DIR/program/soffice.bin" "$@"
EOF
chmod +x "$PORTABLE_DIR/soffice"

echo ""
echo "[3/3] 计算便携版大小..."
SIZE=$(du -sh "$PORTABLE_DIR" | cut -f1)
echo "  便携版大小: $SIZE"

echo ""
echo "=========================================="
echo "  完成!"
echo "=========================================="
echo ""
echo "便携版已创建在: $PORTABLE_DIR"
echo ""
echo "要使用便携版，修改 core/converter.py 中的路径:"
echo "  self.soffice = '$PORTABLE_DIR/soffice'"
echo ""
echo "确认便携版可用后，可以删除系统 LibreOffice:"
echo "  sudo apt remove libreoffice-core libreoffice-writer libreoffice-calc"
echo ""
