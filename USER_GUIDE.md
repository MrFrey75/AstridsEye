# AstridsEye User Guide

## What is AstridsEye?
AstridsEye is a desktop app for generating and saving images using a local Ollama server. It provides a simple graphical interface to send prompts, select models, and view/save generated images.

## Getting Started

### Prerequisites
- Python 3.10+
- Ollama server running locally (see [Ollama documentation](https://ollama.com/))
- Image-capable Ollama model (e.g., moondream, llava, bakllava)
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Running the App
- From your project root:
  ```bash
  python3 ./src/app.py
  ```
- Or as a package:
  ```bash
  python3 -m src.app
  ```

### Main Features
- **API URL**: Set the Ollama server endpoint. Use "Detect endpoint" to auto-discover.
- **Model Selector**: Choose from available models (auto-discovered if possible).
- **Prompt Entry**: Type your image prompt and press Enter or click "Generate Image".
- **Save Path**: Choose where generated images are saved.
- **Raw Data Pane**: View raw payloads sent to the server and raw responses received.
- **Image Display**: See the generated image and save it with a timestamped filename.

### Troubleshooting
- If you see errors about missing models or no images returned, ensure your Ollama server is running and you have pulled an image-capable model.
- If you see API errors, check the API URL and server status.
- For advanced diagnostics, inspect the raw data pane for payloads and responses.

## FAQ
- **How do I add a new model?**
  - Pull it with `ollama pull <modelname>` and restart the app.
- **Where is my config saved?**
  - In `.astridseye.yaml` at the project root.
- **How do I reset settings?**
  - Delete `.astridseye.yaml` and restart the app.

---
For more help, see the [Developer Guide](DEVELOPER_GUIDE.md) or open an issue on GitHub.
