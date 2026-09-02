#!/bin/bash
echo "$(date) args: $@" >> /tmp/pdf-editor-debug.log
FILE_PATH="$1"
echo "$(date) file: $FILE_PATH" >> /tmp/pdf-editor-debug.log
if [[ "$FILE_PATH" == file://* ]]; then
    FILE_PATH="${FILE_PATH#file://}"
    FILE_PATH=$(python3 -c "import urllib.parse; print(urllib.parse.unquote('$FILE_PATH'))" 2>/dev/null || echo "$FILE_PATH")
fi
echo "$(date) final: $FILE_PATH" >> /tmp/pdf-editor-debug.log
docker run --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /home/user:/home/user \
  pdf-editor-assistant main.py "$FILE_PATH"
