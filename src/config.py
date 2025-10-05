import os
import yaml

def default_config_path():
    """
    Returns the absolute path to the AstridsEye YAML config file.
    The config is stored as `.astridseye.yaml` in the project root (one level up from src).

    Returns:
        str: Absolute path to the config file.
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.astridseye.yaml'))

def load_config(path=None):
    """
    Loads configuration from a YAML file.

    Args:
        path (str, optional): Path to the YAML config file. Defaults to project config path.

    Returns:
        dict: Configuration dictionary. Returns empty dict if file does not exist or is invalid.

    Example:
        cfg = load_config()
        api_url = cfg.get('api_url')
    """
    path = path or default_config_path()
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
            return cfg
        # Config file does not exist; return empty config
        return {}
    except Exception as e:
        # Log or handle error as needed
        return {}

def save_config(cfg: dict, path=None):
    """
    Saves configuration dictionary to a YAML file.

    Args:
        cfg (dict): Configuration dictionary to save.
        path (str, optional): Path to the YAML config file. Defaults to project config path.

    Returns:
        bool: True if save succeeded, False otherwise.

    Example:
        cfg = {'api_url': 'http://localhost:11434/api/generate', 'last_model': 'llava'}
        save_config(cfg)
    """
    path = path or default_config_path()
    try:
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)
        with open(path, 'w') as f:
            yaml.safe_dump(cfg, f)
        return True
    except Exception as e:
        # Log or handle error as needed
        return False
