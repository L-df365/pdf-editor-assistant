#!/bin/bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /home/user:/home/user \
  pdf-editor-assistant python /home/user/pdf-insert/main.py "$@"
