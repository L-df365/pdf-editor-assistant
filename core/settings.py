import json
import os
import tempfile

CONFIG_DIR = os.path.join(
    os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
    'pdf-editor-assistant',
)
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')


def load_backend():
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    value = data.get('backend')
    return value if isinstance(value, str) else None


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
