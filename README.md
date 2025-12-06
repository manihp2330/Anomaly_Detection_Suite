# Anomaly Detector (NiceGUI)

A standalone, NiceGUI-based log anomaly detection tool with support for:

- **Live anomaly detection** during test execution
- **Offline folder analysis** for large log collections
- **Pattern management** (default + custom regexes)
- **Category-based filtering and drill-down dialogs**
- Export of anomalies to **JSON** 


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
