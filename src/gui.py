import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from io import BytesIO
import base64
from PIL import Image, ImageTk
import threading
import os

from .config import load_config, save_config
from .client import OllamaClient


class AstridsEyeGUI:
    def __init__(self, root):
        # Path for YAML log file
        self.log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'astridseye_log.yaml'))
        self.root = root
        self.root.title("AstridsEye")
        self.root.geometry("900x650")

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        self.client = OllamaClient()

        # UI split: left controls+image, right raw pane
        left = ttk.Frame(self.root, padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(self.root, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)

        ttk.Label(right, text="Raw payload / response").pack(anchor=tk.W)
        self.raw_text = tk.Text(right, width=60, wrap=tk.NONE)
        self.raw_text.pack(fill=tk.BOTH, expand=True)
        raw_scroll_y = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.raw_text.yview)
        raw_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.raw_text.configure(yscrollcommand=raw_scroll_y.set)
        self.raw_text.configure(state=tk.DISABLED)

        # Controls
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
        self.model_var = tk.StringVar(value=self.client.model)
        self.model_box = ttk.Combobox(model_row, textvariable=self.model_var, values=[self.client.model])
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

        # Load config and apply
        cfg = load_config()
        api = cfg.get('api_url')
        if api:
            self.api_entry.insert(0, api)
            self.client.api_url = api
        last = cfg.get('last_model')
        if last:
            self.model_var.set(last)
            self.client.model = last
        savep = cfg.get('save_path')
        if savep:
            self.save_var.set(savep)

        # background model discovery
        threading.Thread(target=self._discover_models, daemon=True).start()

    # UI helpers
    def browse_save_path(self):
        d = filedialog.askdirectory(title="Select folder to save generated images")
        if d:
            self.save_var.set(d)
            self._save_config()

    def append_raw(self, title, obj):
        try:
            self.raw_text.configure(state=tk.NORMAL)
            self.raw_text.insert(tk.END, f"--- {title} ({datetime.utcnow().isoformat()} UTC) ---\n")
            if isinstance(obj, (dict, list)):
                import json
                self.raw_text.insert(tk.END, json.dumps(obj, indent=2, ensure_ascii=False) + "\n\n")
            else:
                s = obj.decode() if isinstance(obj, (bytes, bytearray)) else str(obj)
                self.raw_text.insert(tk.END, s + "\n\n")
            self.raw_text.see(tk.END)
            self.raw_text.configure(state=tk.DISABLED)
        except Exception:
            pass
        # Log prompt and data to YAML file if relevant
        if title.lower().startswith("payload") and isinstance(obj, dict):
            self._log_prompt_yaml(obj)
    def _log_prompt_yaml(self, payload):
        """
        Append prompt and metadata to astridseye_log.yaml in project root.
        """
        import yaml
        import datetime
        log_entry = {
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'model': payload.get('model'),
            'prompt': payload.get('prompt'),
            'stream': payload.get('stream'),
        }
        try:
            # Read existing log
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r') as f:
                    existing = yaml.safe_load(f) or []
            else:
                existing = []
            # Append new entry
            existing.append(log_entry)
            with open(self.log_path, 'w') as f:
                yaml.safe_dump(existing, f)
        except Exception:
            pass

    def start_probe_thread(self):
        self.client.api_url = self.api_entry.get().strip() or self.client.api_url
        threading.Thread(target=self._probe_and_apply, daemon=True).start()

    def _probe_and_apply(self):
        found = self.client.probe_endpoints()
        if found:
            self.client.api_url = found
            self.root.after(0, lambda: self.api_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.api_entry.insert(0, found))
            self.root.after(0, lambda: self.status_var.set(f"Detected API endpoint: {found}"))
            self._save_config()
        else:
            self.root.after(0, lambda: self.status_var.set("No generate endpoint detected (kept configured URL)."))

    def start_generation_thread(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt.")
            return

        self._save_config()
        self.generate_button.config(state=tk.DISABLED)
        self.status_var.set(f"Generating image for: '{prompt}'...")
        threading.Thread(target=self._generate_background, args=(prompt,), daemon=True).start()

    def _discover_models(self):
        models = self.client.discover_models()
        if models:
            self.root.after(0, lambda: self.model_box.configure(values=models))
            last = self.model_var.get()
            if last and last in models:
                self.root.after(0, lambda: self.model_var.set(last))

    def _generate_background(self, prompt):
        model = self.model_var.get() or self.client.model
        payload = {"model": model, "prompt": f"Please generate a high-quality, detailed image of: {prompt}", "stream": False}
        self.root.after(0, lambda: self.append_raw("Payload", payload))
        try:
            data, raw_text, status = self.client.generate(self.client.api_url, payload)
            self.root.after(0, lambda: self.append_raw("Response (raw)", raw_text))

            images = data.get('images', []) if isinstance(data, dict) else []
            if not images:
                text = None
                if isinstance(data, dict):
                    text = data.get('response') or data.get('text')
                if text:
                    self.root.after(0, lambda: self.append_raw("Text response", text))
                    self.root.after(0, lambda: self.show_error(f"Model returned text instead of an image:\n\n{text[:2000]}"))
                    return
                raise ValueError("No image data found in the API response.")

            self.root.after(0, lambda: self.update_gui_with_image(images[0]))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"API Error: {e}\n\nIs Ollama running?"))
        finally:
            self.root.after(0, lambda: self.generate_button.config(state=tk.NORMAL))

    def update_gui_with_image(self, image_b64):
        try:
            img_data = base64.b64decode(image_b64)
            buf = BytesIO(img_data)
            img = Image.open(buf)
            w = self.image_label.winfo_width() or 512
            h = self.image_label.winfo_height() or 512
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo_image, text='')
            self.status_var.set('Image generated successfully.')

            save_dir = self.save_var.get()
            if save_dir:
                try:
                    os.makedirs(save_dir, exist_ok=True)
                    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    fmt = (img.format or 'PNG').lower()
                    filename = f"astridseye_{ts}.{fmt}"
                    out_path = os.path.join(save_dir, filename)
                    img.save(out_path)
                    self.status_var.set(f"Saved image to {out_path}")
                    self.append_raw("Saved file", out_path)
                except Exception as e:
                    self.show_error(f"Failed to save image: {e}")
        except Exception as e:
            self.show_error(f"Failed to display image: {e}")

    def show_error(self, message):
        messagebox.showerror('Error', message)
        self.status_var.set('Error. See message box for details.')

    def _save_config(self):
        cfg = {
            'api_url': self.api_entry.get().strip() or self.client.api_url,
            'last_model': self.model_var.get(),
            'save_path': self.save_var.get() or None,
        }
        save_config(cfg)
