import json
import os
import tempfile

CONFIG_DIR = os.path.join(
    os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
    'pdf-editor-assistant',
)
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
RECENT_PATH = os.path.join(CONFIG_DIR, 'recent.json')


def load_backend():
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    value = data.get('backend')
    return value if isinstance(value, str) else None


def load_recent(limit=8):
    """最近使用的文件（按时间倒序）。"""
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
    """记入最近使用（去重，最多 8 条）。"""
    if not path:
        return
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        items = [p for p in load_recent(limit=50) if p != path]
        items.insert(0, path)
        items = items[:8]
        fd, tmp_path = tempfile.mkstemp(prefix='.recent-', suffix='.json',
                                        dir=CONFIG_DIR)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'recent': items}, f, ensure_ascii=False)
        os.replace(tmp_path, RECENT_PATH)
    except OSError:
        pass


def save_backend(name):
    if not name:
        return
    os.makedirs(CONFIG_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix='.config-', suffix='.json', dir=CONFIG_DIR)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'backend': name}, f, ensure_ascii=False)
        os.replace(tmp_path, CONFIG_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
