import os
import yaml


def default_config_path():
    """Return absolute path to .astridseye.yaml in the project root (one level up from src)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.astridseye.yaml'))


def load_config(path=None):
    path = path or default_config_path()
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
            return cfg
        return {}
    except Exception:
        return {}


def save_config(cfg: dict, path=None):
    path = path or default_config_path()
    try:
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)
        with open(path, 'w') as f:
            yaml.safe_dump(cfg, f)
        return True
    except Exception:
        return False
