#!/bin/bash
FILE_PATH="$1"
# 处理 file:// URI 格式
if [[ "$FILE_PATH" == file://* ]]; then
    FILE_PATH="${FILE_PATH#file://}"
    FILE_PATH=$(python3 -c "import urllib.parse; print(urllib.parse.unquote('$FILE_PATH'))" 2>/dev/null || echo "$FILE_PATH")
fi
docker run --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /home/user:/home/user \
  pdf-editor-assistant main.py "$FILE_PATH"
