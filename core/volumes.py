"""可移动磁盘（U 盘、移动硬盘）的探测。

系统把 U 盘挂在 /media、/run/media、/mnt 这些标准位置下，
名字一般就是磁盘卷标（udisks2 挂载时用的名字）。
界面上的"常用位置"要把它们列出来，用户才能直接选到。
"""

import glob
import os

#: U 盘可能挂载的位置
MOUNT_PATTERNS = (
    '/media/*',
    '/media/*/*',
    '/run/media/*',
    '/run/media/*/*',
    '/mnt/*',
    '/mnt/*/*',
    '/run/user/*/gvfs/*',
)


def _readable(path):
    try:
        if not os.path.isdir(path):
            return False
        if not os.access(path, os.R_OK | os.X_OK):
            return False
        os.listdir(path)          # 挂载了但读不了（空/未授权）就跳过
        return True
    except OSError:
        return False


def list_volumes():
    """列出挂载着的可移动磁盘，返回 [(显示名, 路径)]。

    只列目录里确实有东西的挂载点：没插 U 盘时不会多出空条目。
    父目录（比如 /media/用户名）不算磁盘，会被去掉。
    """
    paths = []
    seen = set()
    for pattern in MOUNT_PATTERNS:
        for path in sorted(glob.glob(pattern)):
            path = os.path.normpath(path)
            if path in seen or not _readable(path):
                continue
            seen.add(path)
            paths.append(path)

    # 去掉"父目录"：/media/xxx 只是挂载点容器，不是磁盘本身
    volumes = []
    for path in paths:
        if any(other != path and other.startswith(path + os.sep)
               for other in paths):
            continue
        volumes.append((_label(path), path))
    return volumes


def _label(path):
    """磁盘的显示名：优先用挂载点的卷标名。"""
    name = os.path.basename(path.rstrip(os.sep))
    parent = os.path.basename(os.path.dirname(path.rstrip(os.sep)))
    if not name:
        name = parent or path
    return name


def volume_signature():
    """当前挂载的可移动磁盘的指纹（用来判断"是不是变了"）。"""
    return tuple(sorted(path for _, path in list_volumes()))
