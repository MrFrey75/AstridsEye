import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import base64
from io import BytesIO
from PIL import Image, ImageTk
from datetime import datetime
import threading
import os
import json
import urllib.parse

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"


class OllamaImageGeneratorApp:
    """Simple Tkinter GUI for generating images via a local Ollama server."""

    def __init__(self, root):
        self.root = root
        self.root.title("AstridsEye")
        self.root.geometry("900x650")

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Editable API URL (may be replaced by config)
        self.api_url = OLLAMA_API_URL
        self._version_info = None

        # Layout: left controls + image, right raw pane
        left = ttk.Frame(self.root, padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = ttk.Frame(self.root, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)

        # Raw pane (right)
        ttk.Label(right, text="Raw payload / response").pack(anchor=tk.W)
        self.raw_text = tk.Text(right, width=60, wrap=tk.NONE)
        self.raw_text.pack(fill=tk.BOTH, expand=True)
        raw_scroll_y = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.raw_text.yview)
        raw_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.raw_text.configure(yscrollcommand=raw_scroll_y.set)
        self.raw_text.configure(state=tk.DISABLED)

        # Controls (left)
        api_row = ttk.Frame(left)
        api_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(api_row, text="Ollama API URL:").pack(side=tk.LEFT, padx=(0, 8))
        self.api_entry = ttk.Entry(api_row)
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(api_row, text="Detect endpoint", command=self.start_probe_thread).pack(side=tk.LEFT, padx=8)

        prompt_row = ttk.Frame(left)
        prompt_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(prompt_row, text="Prompt:").pack(side=tk.LEFT, padx=(0, 8))
        self.prompt_entry = ttk.Entry(prompt_row)
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.prompt_entry.bind("<Return>", self.start_generation_thread)

        model_row = ttk.Frame(left)
        model_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(model_row, text="Model:").pack(side=tk.LEFT, padx=(0, 8))
        self.model_var = tk.StringVar(value=OLLAMA_MODEL)
        self.model_box = ttk.Combobox(model_row, textvariable=self.model_var, values=["llava", "moondream", "bakllava"])
        self.model_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.model_box.bind("<<ComboboxSelected>>", lambda e: self._save_config())

        save_row = ttk.Frame(left)
        save_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(save_row, text="Save images to:").pack(side=tk.LEFT, padx=(0, 8))
        self.save_var = tk.StringVar()
        self.save_entry = ttk.Entry(save_row, textvariable=self.save_var)
        self.save_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(save_row, text="Browse", command=self.browse_save_path).pack(side=tk.LEFT, padx=8)

        self.generate_button = ttk.Button(left, text="Generate Image", command=self.start_generation_thread)
        self.generate_button.pack(fill=tk.X, pady=6)

        self.image_label = ttk.Label(left, text="Your generated image will appear here.", background="#fff", relief="groove")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        # Config
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.astridseye.json'))
        self._load_config()
        self.api_entry.delete(0, tk.END)
        self.api_entry.insert(0, self.api_url)
        if getattr(self, 'last_model', None):
            self.model_var.set(self.last_model)
        if getattr(self, 'save_path', None):
            self.save_var.set(self.save_path)

        # Start model discovery in background
        threading.Thread(target=self._discover_models, daemon=True).start()

    # ---- UI actions ----
    def browse_save_path(self):
        d = filedialog.askdirectory(title="Select folder to save generated images")
        if d:
            self.save_var.set(d)
            self.save_path = d
            self._save_config()

    def append_raw(self, title, obj):
        """Append a titled JSON/text block to the raw pane (safe to call from main thread)."""
        try:
            self.raw_text.configure(state=tk.NORMAL)
            self.raw_text.insert(tk.END, f"--- {title} ({datetime.utcnow().isoformat()} UTC) ---\n")
            if isinstance(obj, (dict, list)):
                self.raw_text.insert(tk.END, json.dumps(obj, indent=2, ensure_ascii=False) + "\n\n")
            else:
                # string or bytes
                s = obj.decode() if isinstance(obj, (bytes, bytearray)) else str(obj)
                self.raw_text.insert(tk.END, s + "\n\n")
            self.raw_text.see(tk.END)
            self.raw_text.configure(state=tk.DISABLED)
        except Exception:
            pass

    def start_probe_thread(self):
        self.api_url = self.api_entry.get().strip() or self.api_url
        threading.Thread(target=self.probe_endpoints, daemon=True).start()

    def start_generation_thread(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt.")
            return

        self._save_config()
        self.generate_button.config(state=tk.DISABLED)
        self.status_var.set(f"Generating image for: '{prompt}'...")
        threading.Thread(target=self.generate_image, args=(prompt,), daemon=True).start()

    # ---- Network helpers ----
    def probe_endpoints(self):
        endpoints = ["/api/generate", "/v1/generate", "/api/completions", "/generate"]
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        found = None
        for p in endpoints:
            url = base + p
            try:
                resp = requests.post(url, json={"model": OLLAMA_MODEL, "prompt": "ping", "stream": False}, timeout=4)
                if resp.status_code != 404:
                    found = url
                    break
            except Exception:
                continue

        if found:
            self.api_url = found
            self.root.after(0, lambda: self.api_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.api_entry.insert(0, found))
            self.root.after(0, lambda: self.status_var.set(f"Detected API endpoint: {found}"))
            self._save_config()
        else:
            self.root.after(0, lambda: self.status_var.set("No generate endpoint detected (kept configured URL)."))

    def _discover_models(self):
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        candidates = [f"{base}/api/models", f"{base}/models"]
        models = []
        for url in candidates:
            try:
                r = requests.get(url, timeout=4)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict) and 'models' in j:
                        models = [m.get('name') if isinstance(m, dict) else m for m in j.get('models')]
                    elif isinstance(j, list):
                        models = [m.get('name') if isinstance(m, dict) else m for m in j]
                    break
            except Exception:
                continue

        if models:
            self.root.after(0, lambda: self.model_box.configure(values=models))
            last = getattr(self, 'last_model', None)
            if last and last in models:
                self.root.after(0, lambda: self.model_var.set(last))

    # ---- Config persistence ----
    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    cfg = json.load(f)
                self.api_url = cfg.get('api_url', self.api_url)
                self.last_model = cfg.get('last_model', None)
                self.save_path = cfg.get('save_path', None)
            else:
                self.last_model = None
        except Exception:
            self.last_model = None

    def _save_config(self):
        try:
            cfg = {
                'api_url': self.api_entry.get().strip() or self.api_url,
                'last_model': self.model_var.get() if hasattr(self, 'model_var') else None,
                'save_path': getattr(self, 'save_path', None),
            }
            d = os.path.dirname(self.config_path)
            os.makedirs(d, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(cfg, f)
        except Exception:
            pass

    # ---- Generation / response handling ----
    def generate_image(self, prompt):
        try:
            model = self.model_var.get() or OLLAMA_MODEL
            payload = {"model": model, "prompt": f"Please generate a high-quality, detailed image of: {prompt}", "stream": False}

            # Log payload to raw pane
            try:
                self.root.after(0, lambda: self.append_raw("Payload", payload))
            except Exception:
                pass

            resp = requests.post(self.api_url, json=payload, timeout=300)

            try:
                self.root.after(0, lambda: self.append_raw("Response (raw)", resp.text))
            except Exception:
                pass

            resp.raise_for_status()
            data = resp.json()

            images = data.get('images', []) if isinstance(data, dict) else []

            if not images:
                text = None
                if isinstance(data, dict):
                    text = data.get('response') or data.get('text')
                    if not text and 'choices' in data:
                        choices = data.get('choices')
                        if isinstance(choices, list) and choices:
                            first = choices[0]
                            if isinstance(first, dict):
                                text = first.get('text') or first.get('message')
                            elif isinstance(first, str):
                                text = first

                if text:
                    short = (text[:2000] + '...') if len(text) > 2000 else text
                    # show in raw pane and as an info dialog
                    self.root.after(0, lambda: self.append_raw("Text response", text))
                    self.root.after(0, lambda: self.show_error(f"Model returned text instead of an image:\n\n{short}"))
                    return

                try:
                    body = json.dumps(data)
                except Exception:
                    body = resp.text if hasattr(resp, 'text') else '<no body>'

                short = (body[:1000] + '...') if body and len(body) > 1000 else body
                raise ValueError(f"No image data found in the API response. Server response: {short}")

            # Use the first image
            self.root.after(0, lambda: self.update_gui_with_image(images[0]))

        except requests.exceptions.RequestException as e:
            self.root.after(0, lambda: self.show_error(f"API Error: {e}\n\nIs Ollama running?"))
        except (ValueError, KeyError) as e:
            self.root.after(0, lambda: self.show_error(f"Error processing response: {e}"))
        finally:
            self.root.after(0, self.reset_ui)

    def update_gui_with_image(self, image_b64):
        try:
            img_data = base64.b64decode(image_b64)
            buf = BytesIO(img_data)
            img = Image.open(buf)

            w = self.image_label.winfo_width()
            h = self.image_label.winfo_height()
            if w < 2 or h < 2:
                w, h = 512, 512
            img.thumbnail((w, h), Image.Resampling.LANCZOS)

            self.photo_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo_image, text='')
            self.status_var.set('Image generated successfully.')

            # Save image to disk if save_path configured
            save_dir = getattr(self, 'save_path', None) or self.save_var.get()
            if save_dir:
                try:
                    os.makedirs(save_dir, exist_ok=True)
                    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    fmt = (img.format or 'PNG').lower()
                    filename = f"astridseye_{ts}.{fmt}"
                    out_path = os.path.join(save_dir, filename)
                    img.save(out_path)
                    self.status_var.set(f"Saved image to {out_path}")
                    self.root.after(0, lambda: self.append_raw("Saved file", out_path))
                except Exception as e:
                    self.root.after(0, lambda: self.show_error(f"Failed to save image: {e}"))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"Failed to display image: {e}"))

    def show_error(self, message):
        messagebox.showerror('Error', message)
        self.status_var.set('Error. See message box for details.')

    def reset_ui(self):
        try:
            self.generate_button.config(state=tk.NORMAL)
            if 'Error' not in self.status_var.get():
                self.status_var.set('Ready')
        except Exception:
            pass


if __name__ == '__main__':
    root = tk.Tk()
    app = OllamaImageGeneratorApp(root)
    root.mainloop()
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import base64
from io import BytesIO
from PIL import Image, ImageTk
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import base64
from io import BytesIO
from PIL import Image, ImageTk
from datetime import datetime
import threading
import os
import json
import urllib.parse

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"


class OllamaImageGeneratorApp:
    """Simple Tkinter GUI for generating images via a local Ollama server."""

    def __init__(self, root):
        self.root = root
        self.root.title("AstridsEye")
        self.root.geometry("900x650")

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Editable API URL (may be replaced by config)
        self.api_url = OLLAMA_API_URL
        self._version_info = None

        # Layout: left controls + image, right raw pane
        left = ttk.Frame(self.root, padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = ttk.Frame(self.root, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)

        # Raw pane (right)
        ttk.Label(right, text="Raw payload / response").pack(anchor=tk.W)
        self.raw_text = tk.Text(right, width=60, wrap=tk.NONE)
        self.raw_text.pack(fill=tk.BOTH, expand=True)
        raw_scroll_y = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.raw_text.yview)
        raw_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.raw_text.configure(yscrollcommand=raw_scroll_y.set)
        self.raw_text.configure(state=tk.DISABLED)

        # Controls (left)
        api_row = ttk.Frame(left)
        api_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(api_row, text="Ollama API URL:").pack(side=tk.LEFT, padx=(0, 8))
        self.api_entry = ttk.Entry(api_row)
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(api_row, text="Detect endpoint", command=self.start_probe_thread).pack(side=tk.LEFT, padx=8)

        prompt_row = ttk.Frame(left)
        prompt_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(prompt_row, text="Prompt:").pack(side=tk.LEFT, padx=(0, 8))
        self.prompt_entry = ttk.Entry(prompt_row)
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.prompt_entry.bind("<Return>", self.start_generation_thread)

        model_row = ttk.Frame(left)
        model_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(model_row, text="Model:").pack(side=tk.LEFT, padx=(0, 8))
        self.model_var = tk.StringVar(value=OLLAMA_MODEL)
        self.model_box = ttk.Combobox(model_row, textvariable=self.model_var, values=["llava", "moondream", "bakllava"])
        self.model_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.model_box.bind("<<ComboboxSelected>>", lambda e: self._save_config())

        save_row = ttk.Frame(left)
        save_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(save_row, text="Save images to:").pack(side=tk.LEFT, padx=(0, 8))
        self.save_var = tk.StringVar()
        self.save_entry = ttk.Entry(save_row, textvariable=self.save_var)
        self.save_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(save_row, text="Browse", command=self.browse_save_path).pack(side=tk.LEFT, padx=8)

        self.generate_button = ttk.Button(left, text="Generate Image", command=self.start_generation_thread)
        self.generate_button.pack(fill=tk.X, pady=6)

        self.image_label = ttk.Label(left, text="Your generated image will appear here.", background="#fff", relief="groove")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        # Config
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.astridseye.json'))
        self._load_config()
        self.api_entry.delete(0, tk.END)
        self.api_entry.insert(0, self.api_url)
        if getattr(self, 'last_model', None):
            self.model_var.set(self.last_model)
        if getattr(self, 'save_path', None):
            self.save_var.set(self.save_path)

        # Start model discovery in background
        threading.Thread(target=self._discover_models, daemon=True).start()

    # ---- UI actions ----
    def browse_save_path(self):
        d = filedialog.askdirectory(title="Select folder to save generated images")
        if d:
            self.save_var.set(d)
            self.save_path = d
            self._save_config()

    def append_raw(self, title, obj):
        """Append a titled JSON/text block to the raw pane (safe to call from main thread)."""
        try:
            self.raw_text.configure(state=tk.NORMAL)
            self.raw_text.insert(tk.END, f"--- {title} ({datetime.utcnow().isoformat()} UTC) ---\n")
            if isinstance(obj, (dict, list)):
                self.raw_text.insert(tk.END, json.dumps(obj, indent=2, ensure_ascii=False) + "\n\n")
            else:
                # string or bytes
                s = obj.decode() if isinstance(obj, (bytes, bytearray)) else str(obj)
                self.raw_text.insert(tk.END, s + "\n\n")
            self.raw_text.see(tk.END)
            self.raw_text.configure(state=tk.DISABLED)
        except Exception:
            pass

    def start_probe_thread(self):
        self.api_url = self.api_entry.get().strip() or self.api_url
        threading.Thread(target=self.probe_endpoints, daemon=True).start()

    def start_generation_thread(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt.")
            return

        self._save_config()
        self.generate_button.config(state=tk.DISABLED)
        self.status_var.set(f"Generating image for: '{prompt}'...")
        threading.Thread(target=self.generate_image, args=(prompt,), daemon=True).start()

    # ---- Network helpers ----
    def probe_endpoints(self):
        endpoints = ["/api/generate", "/v1/generate", "/api/completions", "/generate"]
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        found = None
        for p in endpoints:
            url = base + p
            try:
                resp = requests.post(url, json={"model": OLLAMA_MODEL, "prompt": "ping", "stream": False}, timeout=4)
                if resp.status_code != 404:
                    found = url
                    break
            except Exception:
                continue

        if found:
            self.api_url = found
            self.root.after(0, lambda: self.api_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.api_entry.insert(0, found))
            self.root.after(0, lambda: self.status_var.set(f"Detected API endpoint: {found}"))
            self._save_config()
        else:
            self.root.after(0, lambda: self.status_var.set("No generate endpoint detected (kept configured URL)."))

    def _discover_models(self):
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        candidates = [f"{base}/api/models", f"{base}/models"]
        models = []
        for url in candidates:
            try:
                r = requests.get(url, timeout=4)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict) and 'models' in j:
                        models = [m.get('name') if isinstance(m, dict) else m for m in j.get('models')]
                    elif isinstance(j, list):
                        models = [m.get('name') if isinstance(m, dict) else m for m in j]
                    break
            except Exception:
                continue

        if models:
            self.root.after(0, lambda: self.model_box.configure(values=models))
            last = getattr(self, 'last_model', None)
            if last and last in models:
                self.root.after(0, lambda: self.model_var.set(last))

    # ---- Config persistence ----
    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    cfg = json.load(f)
                self.api_url = cfg.get('api_url', self.api_url)
                self.last_model = cfg.get('last_model', None)
                self.save_path = cfg.get('save_path', None)
            else:
                self.last_model = None
        except Exception:
            self.last_model = None

    def _save_config(self):
        try:
            cfg = {
                'api_url': self.api_entry.get().strip() or self.api_url,
                'last_model': self.model_var.get() if hasattr(self, 'model_var') else None,
                'save_path': getattr(self, 'save_path', None),
            }
            d = os.path.dirname(self.config_path)
            os.makedirs(d, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(cfg, f)
        except Exception:
            pass

    # ---- Generation / response handling ----
    def generate_image(self, prompt):
        try:
            model = self.model_var.get() or OLLAMA_MODEL
            payload = {"model": model, "prompt": f"Please generate a high-quality, detailed image of: {prompt}", "stream": False}

            # Log payload to raw pane
            try:
                self.root.after(0, lambda: self.append_raw("Payload", payload))
            except Exception:
                pass

            resp = requests.post(self.api_url, json=payload, timeout=300)

            try:
                self.root.after(0, lambda: self.append_raw("Response (raw)", resp.text))
            except Exception:
                pass

            resp.raise_for_status()
            data = resp.json()

            images = data.get('images', []) if isinstance(data, dict) else []

            if not images:
                text = None
                if isinstance(data, dict):
                    text = data.get('response') or data.get('text')
                    if not text and 'choices' in data:
                        choices = data.get('choices')
                        if isinstance(choices, list) and choices:
                            first = choices[0]
                            if isinstance(first, dict):
                                text = first.get('text') or first.get('message')
                            elif isinstance(first, str):
                                text = first

                if text:
                    short = (text[:2000] + '...') if len(text) > 2000 else text
                    # show in raw pane and as an info dialog
                    self.root.after(0, lambda: self.append_raw("Text response", text))
                    self.root.after(0, lambda: self.show_error(f"Model returned text instead of an image:\n\n{short}"))
                    return

                try:
                    body = json.dumps(data)
                except Exception:
                    body = resp.text if hasattr(resp, 'text') else '<no body>'

                short = (body[:1000] + '...') if body and len(body) > 1000 else body
                raise ValueError(f"No image data found in the API response. Server response: {short}")

            # Use the first image
            self.root.after(0, lambda: self.update_gui_with_image(images[0]))

        except requests.exceptions.RequestException as e:
            self.root.after(0, lambda: self.show_error(f"API Error: {e}\n\nIs Ollama running?"))
        except (ValueError, KeyError) as e:
            self.root.after(0, lambda: self.show_error(f"Error processing response: {e}"))
        finally:
            self.root.after(0, self.reset_ui)

    def update_gui_with_image(self, image_b64):
        try:
            img_data = base64.b64decode(image_b64)
            buf = BytesIO(img_data)
            img = Image.open(buf)

            w = self.image_label.winfo_width()
            h = self.image_label.winfo_height()
            if w < 2 or h < 2:
                w, h = 512, 512
            img.thumbnail((w, h), Image.Resampling.LANCZOS)

            self.photo_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo_image, text='')
            self.status_var.set('Image generated successfully.')

            # Save image to disk if save_path configured
            save_dir = getattr(self, 'save_path', None) or self.save_var.get()
            if save_dir:
                try:
                    os.makedirs(save_dir, exist_ok=True)
                    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    fmt = (img.format or 'PNG').lower()
                    filename = f"astridseye_{ts}.{fmt}"
                    out_path = os.path.join(save_dir, filename)
                    img.save(out_path)
                    self.status_var.set(f"Saved image to {out_path}")
                    self.root.after(0, lambda: self.append_raw("Saved file", out_path))
                except Exception as e:
                    self.root.after(0, lambda: self.show_error(f"Failed to save image: {e}"))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"Failed to display image: {e}"))

    def show_error(self, message):
        messagebox.showerror('Error', message)
        self.status_var.set('Error. See message box for details.')

    def reset_ui(self):
        try:
            self.generate_button.config(state=tk.NORMAL)
            if 'Error' not in self.status_var.get():
                self.status_var.set('Ready')
        except Exception:
            pass


if __name__ == '__main__':
    root = tk.Tk()
    app = OllamaImageGeneratorApp(root)
    root.mainloop()
from io import BytesIO
from PIL import Image, ImageTk
from datetime import datetime
import threading
import os
import json
import urllib.parse

# --- Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"


class OllamaImageGeneratorApp:
    """Simple Tkinter GUI for generating images via a local Ollama server."""

    def __init__(self, root):
        self.root = root
        self.root.title("AstridsEye")
        self.root.geometry("550x650")

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Editable API URL (may be replaced by config)
        self.api_url = OLLAMA_API_URL
        self._version_info = None

    # Left main frame (controls + image) and right raw data pane
    main = ttk.Frame(self.root, padding=10)
    main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    raw_frame = ttk.Frame(self.root, padding=6)
    raw_frame.pack(side=tk.RIGHT, fill=tk.BOTH)

    ttk.Label(raw_frame, text="Raw payload / response").pack(anchor=tk.W)
    self.raw_text = tk.Text(raw_frame, width=60, wrap=tk.NONE)
    self.raw_text.pack(fill=tk.BOTH, expand=True)
    raw_scroll_y = ttk.Scrollbar(raw_frame, orient=tk.VERTICAL, command=self.raw_text.yview)
    raw_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
    self.raw_text.configure(yscrollcommand=raw_scroll_y.set)

    # make text read-only by default
    self.raw_text.configure(state=tk.DISABLED)

        # API URL
        api_row = ttk.Frame(main)
        api_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(api_row, text="Ollama API URL:").pack(side=tk.LEFT, padx=(0, 8))
        self.api_entry = ttk.Entry(api_row)
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(api_row, text="Detect endpoint", command=self.start_probe_thread).pack(side=tk.LEFT, padx=8)

        # Prompt
        prompt_row = ttk.Frame(main)
        prompt_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(prompt_row, text="Prompt:").pack(side=tk.LEFT, padx=(0, 8))
        self.prompt_entry = ttk.Entry(prompt_row)
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.prompt_entry.bind("<Return>", self.start_generation_thread)

        # Model selector
        model_row = ttk.Frame(main)
        model_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(model_row, text="Model:").pack(side=tk.LEFT, padx=(0, 8))
        self.model_var = tk.StringVar(value=OLLAMA_MODEL)
        self.model_box = ttk.Combobox(model_row, textvariable=self.model_var, values=["llava", "moondream", "bakllava"])
        self.model_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Save model selection when changed
        self.model_box.bind("<<ComboboxSelected>>", lambda e: self._save_config())

        # Save path selector
        save_row = ttk.Frame(main)
        save_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(save_row, text="Save images to:").pack(side=tk.LEFT, padx=(0, 8))
        self.save_var = tk.StringVar()
        self.save_entry = ttk.Entry(save_row, textvariable=self.save_var)
        self.save_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(save_row, text="Browse", command=self.browse_save_path).pack(side=tk.LEFT, padx=8)

        # Generate button
        self.generate_button = ttk.Button(main, text="Generate Image", command=self.start_generation_thread)
        self.generate_button.pack(fill=tk.X, pady=6)

        # Image display
        self.image_label = ttk.Label(main, text="Your generated image will appear here.", background="#fff", relief="groove")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        # Config file path
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.astridseye.json'))

        # Load config (may update api_url, last_model, save_path)
        self._load_config()

        # Ensure the entries reflect loaded config
        self.api_entry.delete(0, tk.END)
        self.api_entry.insert(0, self.api_url)
        if getattr(self, 'last_model', None):
            self.model_var.set(self.last_model)
        # Fill save path entry from config
        if getattr(self, 'save_path', None):
            self.save_var.set(self.save_path)

        # Start background model discovery (safe after widgets exist)
        threading.Thread(target=self._discover_models, daemon=True).start()

    # ---- UI actions / threads ----
    def start_probe_thread(self):
        # Update api_url from entry then probe common endpoints
        self.api_url = self.api_entry.get().strip() or self.api_url
        t = threading.Thread(target=self.probe_endpoints, daemon=True)
        t.start()

    def start_generation_thread(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt.")
            return

        # Save current model selection and api_url
        self._save_config()

    self.generate_button.config(state=tk.DISABLED)
    self.status_var.set(f"Generating image for: '{prompt}'...")
    t = threading.Thread(target=self.generate_image, args=(prompt,), daemon=True)
    t.start()

    # ---- Network helpers ----
    def probe_endpoints(self):
        endpoints = ["/api/generate", "/v1/generate", "/api/completions", "/generate"]
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        found = None
        for p in endpoints:
            url = base + p
            try:
                resp = requests.post(url, json={"model": OLLAMA_MODEL, "prompt": "ping", "stream": False}, timeout=4)
                if resp.status_code != 404:
                    found = url
                    break
            except Exception:
                continue

        if found:
            self.api_url = found
            self.root.after(0, lambda: self.api_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.api_entry.insert(0, found))
            self.root.after(0, lambda: self.status_var.set(f"Detected API endpoint: {found}"))
            # Persist detected URL
            self._save_config()
        else:
            self.root.after(0, lambda: self.status_var.set("No generate endpoint detected (kept configured URL)."))

    def _discover_models(self):
        """Attempt to query the Ollama server for available models and populate the combobox."""
        try:
            parsed = urllib.parse.urlparse(self.api_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = "http://localhost:11434"

        candidates = [f"{base}/api/models", f"{base}/models"]
        models = []
        for url in candidates:
            try:
                r = requests.get(url, timeout=4)
                if r.status_code == 200:
                    j = r.json()
                    # try common shapes
                    if isinstance(j, dict) and 'models' in j:
                        models = [m.get('name') if isinstance(m, dict) else m for m in j.get('models')]
                    elif isinstance(j, list):
                        models = [m.get('name') if isinstance(m, dict) else m for m in j]
                    break
            except Exception:
                continue

        if models:
            # Update combobox values on main thread
            self.root.after(0, lambda: self.model_box.configure(values=models))
            # If last used model is in models, set it
            last = getattr(self, 'last_model', None)
            if last and last in models:
                self.root.after(0, lambda: self.model_var.set(last))

    def browse_save_path(self):
        d = filedialog.askdirectory(title="Select folder to save generated images")
        if d:
            self.save_var.set(d)
            self.save_path = d
            self._save_config()


    # ---- Config persistence ----
    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    cfg = json.load(f)
                self.api_url = cfg.get('api_url', self.api_url)
                self.last_model = cfg.get('last_model', None)
                self.save_path = cfg.get('save_path', None)
            else:
                self.last_model = None
        except Exception:
            self.last_model = None

    def _save_config(self):
        try:
            cfg = {
                'api_url': self.api_entry.get().strip() or self.api_url,
                'last_model': self.model_var.get() if hasattr(self, 'model_var') else None,
                'save_path': getattr(self, 'save_path', None),
            }
            # Ensure directory exists
            d = os.path.dirname(self.config_path)
            os.makedirs(d, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(cfg, f)
        except Exception:
            # Best-effort persistence; ignore errors
            pass

    # ---- Generation / response handling ----
    def generate_image(self, prompt):
        try:
            model = self.model_var.get() or OLLAMA_MODEL
            payload = {"model": model, "prompt": f"Please generate a high-quality, detailed image of: {prompt}", "stream": False}

            # Log the raw payload in the right pane (thread-safe via after)
            try:
                self.root.after(0, lambda: self.append_raw("Payload", payload))
            except Exception:
                pass

            # Hint for known image models
            if model in {"moondream", "bakllava"}:
                payload["response_format"] = "image"

            resp = requests.post(self.api_url, json=payload, timeout=300)
            # Log raw response text
            try:
                self.root.after(0, lambda: self.append_raw("Response", resp.text))
            except Exception:
                pass
            resp.raise_for_status()

            data = resp.json()
            images = data.get('images', []) if isinstance(data, dict) else []

            if not images:
                # If server returned text describing the image, show that instead.
                text = None
                if isinstance(data, dict):
                    text = data.get('response') or data.get('text')
                    if not text and 'choices' in data:
                        choices = data.get('choices')
                        if isinstance(choices, list) and choices:
                            first = choices[0]
                            if isinstance(first, dict):
                                text = first.get('text') or first.get('message')
                            elif isinstance(first, str):
                                text = first

                if text:
                    short = (text[:2000] + '...') if len(text) > 2000 else text
                    self.root.after(0, lambda: self.show_error(f"Model returned text instead of an image:\n\n{short}"))
                    return

                # Otherwise include a truncated dump of the response for debugging
                try:
                    body = json.dumps(data)
                except Exception:
                    body = resp.text if hasattr(resp, 'text') else '<no body>'

                short = (body[:1000] + '...') if body and len(body) > 1000 else body
                raise ValueError(f"No image data found in the API response. Server response: {short}")

            # Use the first image
            self.root.after(0, lambda: self.update_gui_with_image(images[0]))

        except requests.exceptions.RequestException as e:
            self.root.after(0, lambda: self.show_error(f"API Error: {e}\n\nIs Ollama running?"))
        except (ValueError, KeyError) as e:
            self.root.after(0, lambda: self.show_error(f"Error processing response: {e}"))
        finally:
            self.root.after(0, self.reset_ui)

    def update_gui_with_image(self, image_b64):
        try:
            img_data = base64.b64decode(image_b64)
            buf = BytesIO(img_data)
            img = Image.open(buf)

            w = self.image_label.winfo_width()
            h = self.image_label.winfo_height()
            if w < 2 or h < 2:
                w, h = 512, 512
            img.thumbnail((w, h), Image.Resampling.LANCZOS)

            self.photo_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo_image, text='')
            self.status_var.set('Image generated successfully.')

            # Save image to disk if save_path configured
            save_dir = getattr(self, 'save_path', None) or self.save_var.get()
            if save_dir:
                try:
                    os.makedirs(save_dir, exist_ok=True)
                    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    # infer format from PIL image
                    fmt = (img.format or 'PNG').lower()
                    filename = f"astridseye_{ts}.{fmt}"
                    out_path = os.path.join(save_dir, filename)
                    img.save(out_path)
                    self.status_var.set(f"Saved image to {out_path}")
                except Exception as e:
                    # don't fail the UI if save fails; show a non-blocking status update
                    self.root.after(0, lambda: self.show_error(f"Failed to save image: {e}"))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"Failed to display image: {e}"))

    def show_error(self, message):
        messagebox.showerror('Error', message)
        self.status_var.set('Error. See message box for details.')

    def reset_ui(self):
        self.generate_button.config(state=tk.NORMAL)
        if 'Error' not in self.status_var.get():
            self.status_var.set('Ready')


if __name__ == '__main__':
    root = tk.Tk()
    app = OllamaImageGeneratorApp(root)
    root.mainloop()


