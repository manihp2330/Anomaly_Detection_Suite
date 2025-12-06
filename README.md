# Anomaly Detector Suite[ADS Log Analysis Tool] (NiceGUI + Python)

A modern, UI-based log analysis tool that detects anomalies in large system or Wi-Fi logs using customizable
regex patterns. Built with **Python**, **NiceGUI**, and multi-threaded parsing, this tool enables fast offline
analysis and live monitoring.

> This repository contains an **open-source-safe** version of the tool.

## 🚀 Features

- **Live log monitoring** – stream logs and see anomalies in near real time.
- **Offline folder scanning** – recursively scan a directory of logs and aggregate anomalies.
- **Customizable anomaly patterns** – add, edit, delete, import, and export regex-based rules.
- **Draggable & resizable dialogs** – inspect full log lines and surrounding context.
- **Fast multi-threaded parsing** – suitable for large logs (100 MB+).
- **JSON export** – export anomaly tables for further analysis or pipelines.

## Project Structure

```text
├── app.py                   # NiceGUI entry point
├── requirements.txt         # Minimal deps
├── LICENSE                  # MIT License
├── README.md                # Project documentation
└── anomaly_detector/
    ├── __init__.py
    ├── core.py
    ├── ui_main.py
    ├── ui_live.py
    ├── ui_offline.py
    └── ui_display_offline_results.py
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python app.py
```

Then open your browser and navigate to:

- http://localhost:8080/

## Custom Anomaly Patterns

- Default patterns are defined in `core.py` (`DEFAULT_ANOMALY_PATTERNS`).
- You can upload a custom `exception_patterns` Python file from either:
  - The **Live** tab (Pattern Management)
  - The **Offline** tab (Pattern Management)

The runtime detector is exposed as `ANOMALY_DETECTOR` in `core.py`.

## License

This project is released under the MIT License. See `LICENSE` for details.
