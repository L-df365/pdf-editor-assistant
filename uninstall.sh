#!/bin/bash
echo "卸载 PDF 内嵌编辑助手..."

sudo rm -rf /opt/pdf-editor-assistant
sudo rm -f /usr/local/bin/pdf-editor
sudo rm -f /usr/share/applications/pdf-editor.desktop
rm -f ~/.local/share/applications/pdf-editor.desktop

# 更新桌面数据库
update-desktop-database /usr/share/applications/ 2>/dev/null || true
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

echo "卸载完成！"
