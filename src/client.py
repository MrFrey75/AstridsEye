import requests
import urllib.parse


class OllamaClient:
    def __init__(self, api_url: str = "http://localhost:11434/api/generate", model: str = "llava"):
        self.api_url = api_url
        self.model = model

    def probe_endpoints(self, timeout=4):
        """Try a small set of common generate endpoints and return the first that doesn't 404."""
        endpoints = ["/api/generate", "/v1/generate", "/api/completions", "/generate"]
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        for p in endpoints:
            url = base + p
            try:
                r = requests.post(url, json={"model": self.model, "prompt": "ping", "stream": False}, timeout=timeout)
                if r.status_code != 404:
                    return url
            except Exception:
                continue

        return None

    def discover_models(self, timeout=4):
        """Attempt to list models from /api/models or /models. Returns list or empty list."""
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        candidates = [f"{base}/api/models", f"{base}/models"]
        for url in candidates:
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict) and 'models' in j:
                        return [m.get('name') if isinstance(m, dict) else m for m in j.get('models')]
                    elif isinstance(j, list):
                        return [m.get('name') if isinstance(m, dict) else m for m in j]
            except Exception:
                continue

        return []

    def generate(self, api_url: str, payload: dict, timeout=300):
        """Post payload to api_url and return (response_json, raw_text, status_code).
        May raise requests.RequestException.
        """
        r = requests.post(api_url, json=payload, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json(), r.text, r.status_code
        except Exception:
            return None, r.text, r.status_code
