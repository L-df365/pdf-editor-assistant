"""配置与最近文件。

配置放在 ~/.config/pdf-editor-assistant/ 下：
- config.json   记当前用的转换后端
- recent.json   最近打开过的文件
"""

import json
import os
import tempfile

RECENT_LIMIT = 8

#: XDG_CONFIG_HOME 可能被设成空串，这时要退回默认路径，
#: 否则配置目录会变成相对路径（跟着当前目录跑）。
_CONFIG_HOME = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
CONFIG_DIR = os.path.join(_CONFIG_HOME, 'pdf-editor-assistant')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
RECENT_PATH = os.path.join(CONFIG_DIR, 'recent.json')


def load_backend():
    """读出上次选的后端；配置损坏时返回 None（而不是崩掉）。"""
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get('backend')
    return value if isinstance(value, str) else None


def load_recent(limit=RECENT_LIMIT):
    """最近使用的文件（最近的在最前）。"""
    try:
        with open(RECENT_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    items = data.get('recent') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [p for p in items if isinstance(p, str)][:limit]


def push_recent(path):
    """记入最近使用（去重，最多 RECENT_LIMIT 条）。"""
    if not path:
        return
    tmp_path = None
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        items = [p for p in load_recent(limit=50) if p != path]
        items.insert(0, path)
        items = items[:RECENT_LIMIT]
        fd, tmp_path = tempfile.mkstemp(prefix='.recent-', suffix='.json',
                                        dir=CONFIG_DIR)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'recent': items}, f, ensure_ascii=False)
        os.replace(tmp_path, RECENT_PATH)
        tmp_path = None
    except OSError:
        pass
    finally:
        # 写失败会留下临时文件，顺手清掉
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def save_backend(name):
    """记下当前使用的后端。写不了就当没存（不影响使用）。"""
    if not name:
        return
    tmp_path = None
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix='.config-', suffix='.json', dir=CONFIG_DIR)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'backend': name}, f, ensure_ascii=False)
        os.replace(tmp_path, CONFIG_PATH)
        tmp_path = None
    except OSError:
        pass
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
