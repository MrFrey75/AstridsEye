


# AstridsEye

<!-- Badges -->
![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)

[**User Guide**](USER_GUIDE.md) | [**Developer Guide**](DEVELOPER_GUIDE.md)
[**Contributing**](CONTRIBUTING.md) | [**MIT License**](LICENSE)

A small Tkinter GUI that calls a local Ollama server to generate images from prompts.

This repository assumes you have a local Ollama server running on `localhost:11434`.

## Quick start

1. Create and activate a Python virtual environment (if you haven't already):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python ./src/app.py
```

## Pre-run steps: pull an image-capable model

Before you run the app you should make sure you have an image-capable model available locally in Ollama. Not all models return raw image bytes; some return only text or different response shapes. Follow these steps to pull and verify a model:

1. Install the Ollama CLI (if you haven't) and authenticate per Ollama's docs.

2. Pull a recommended image-capable model. Example model names vary by registry. Two commonly-used examples you can try are `moondream` and `bakllava` (if available):

```bash
ollama pull llava
# or
ollama pull moondream
# or
ollama pull bakllava
```

3. Verify the model is available locally:

```bash
ollama list
# or query the local server's models endpoint:
curl http://localhost:11434/api/models
curl http://localhost:11434/models
```

4. Check the Ollama server is running and reachable:

```bash
curl http://localhost:11434/
curl http://localhost:11434/api/version
```

If you see the server version and the model appears in the list, you're ready to run the app.

## Model payload notes

Different Ollama models may expect slightly different JSON payloads. The app probes and uses common endpoints, and will try a small hint `{"response_format": "image"}` for models that are known to accept it. If a model you pulled returns text instead of images, try one of these options:

- Use a different model (one listed by `ollama list` that is known to be image-capable).
- Consult the model's README to see required payload keys (for example some models expect `response_format: "image"`, others expect `format: "png"` or a multipart flow).
- Share the `curl http://localhost:11434/api/models` output here and I can suggest the exact payload and update the app.

## Quick troubleshooting

- If `Detect endpoint` fails, open the terminal and run a sample POST to common endpoints to see which one responds:

```bash
curl -v -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d '{"model":"moondream","prompt":"ping","stream":false}'
```

- If the server returns JSON with a `choices` or `response` field but no `images` array, the model is returning text. Try a different model or ask me to adapt the app for that model's response format.


## Which Ollama model to use for images

Not all Ollama models produce raw image bytes by default. Some models return textual descriptions or require a different API/payload to generate images. The following guidance will help you pick and configure a model that produces image bytes:

- Popular image-capable models (examples):
  - `moondream` (if available in your Ollama registry)
  - `bakllava` / `llava` variants configured for image output

Note: Model names and availability depend on your local Ollama installation and the model repository you used.

## Pulling a model with the Ollama CLI

If you have the Ollama CLI installed, you can usually pull a model by running something like:

```bash
ollama pull <model-name>
```

Example:

```bash
ollama pull moondream
```

After pulling the model, verify it's available:

```bash
curl http://localhost:11434/api/version
curl http://localhost:11434/api/models || curl http://localhost:11434/models
```

## App configuration tips

- Use the "Ollama API URL" field to point the app at your Ollama server (e.g., `http://localhost:11434`).
- Click "Detect endpoint" to let the app probe common generate endpoints and set the correct one for you.
- If the model returns text instead of images, try a different model or consult the model's documentation for image-generation payloads.

## If you need help

Tell me which model you pulled (output of `ollama list` or `curl http://localhost:11434/api/models`) and I can suggest the exact payload to use and update the app accordingly.
