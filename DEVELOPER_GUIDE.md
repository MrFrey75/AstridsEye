# AstridsEye Developer Guide

## Project Structure

```
AstridsEye/
├── requirements.txt
├── README.md
├── USER_GUIDE.md
├── DEVELOPER_GUIDE.md
├── .astridseye.yaml
└── src/
    ├── app.py         # Launcher (entrypoint)
    ├── gui.py         # Tkinter GUI class
    ├── client.py      # Ollama HTTP client
    ├── config.py      # YAML config helpers
```

## How to Run
- As a script:
  ```bash
  python3 ./src/app.py
  ```
- As a package:
  ```bash
  python3 -m src.app
  ```

## Adding Features
- **GUI**: Extend `AstridsEyeGUI` in `src/gui.py`.
- **Network**: Add/modify methods in `OllamaClient` in `src/client.py`.
- **Config**: Use `load_config`/`save_config` in `src/config.py`.

## Testing
- Add unit tests in a `tests/` folder (recommended).
- Use mocks for HTTP requests in `client.py`.
- For GUI, use Tkinter's test utilities or manual testing.

## Packaging & Distribution
- All dependencies are in `requirements.txt`.
- To build a standalone executable, consider using PyInstaller or Briefcase.

## Contributing
- Fork the repo, create a feature branch, and submit a pull request.
- Follow PEP8 style and add docstrings to new functions/classes.
- Document new features in the README and user guide.

## Troubleshooting
- If you see import errors, check your run mode and sys.path setup in `src/app.py`.
- For YAML config issues, ensure PyYAML is installed and `.astridseye.yaml` is valid.
- For network/API issues, verify your Ollama server is running and reachable.

---
For user instructions, see [USER_GUIDE.md](USER_GUIDE.md).
