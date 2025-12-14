# Copilot AI Instructions — Anomaly Detection Suite (ADS)

This guidance is for AI coding agents working in the Anomaly Detection Suite repository. It focuses on how the app is organized, important files and APIs, developer workflows, and project-specific conventions and gotchas.

## Overview
- Purpose: A NiceGUI-based Python UI for detecting anomalies in large device/wifi logs using regex-based rules.
- Architecture: Single-process NiceGUI web server (`app.py`) exposing a UI composed of modular UI pages:
  - `app.py` — NiceGUI entry point (page `/`) and `ui.run()` host options.
  - `anomaly_detector/ui_main.py` — main page wiring tabs and header/footer.
  - `anomaly_detector/ui_live.py` — live analysis UI and manual test input.
  - `anomaly_detector/ui_offline.py` — offline, folder-based analysis with a thread-pool.
  - `anomaly_detector/ui_display_offline_results.py` — detailed viewer and dialog UI for offline results.
  - `anomaly_detector/core.py` — anomaly detection engine (patterns, compilation, detection), exposes `ANOMALY_DETECTOR` singleton.

## Key Concepts & Data Flow
- `ANOMALY_DETECTOR` is a global singleton; prefer the API exposed there rather than creating new detectors.
  - Public/important methods: `load_pattern_file(file_path) -> (bool, message)`, `detect_anomalies(log_text)`, `categorize_anomalies(...)`.
  - Internal methods used by UIs: `_compile_patterns()`, `_detect_from_lines(lines)`.

- Pattern management:
  - Defaults live in `DEFAULT_ANOMALY_PATTERNS` in `core.py`.
  - Custom patterns tracked in `ANOMALY_DETECTOR.custom_patterns` and merged into `ANOMALY_DETECTOR.patterns`.
  - Use `load_pattern_file()` to load patterns from a .py file that sets `exception_patterns` dictionary.

- Live path:
  - Manual log testing calls `ANOMALY_DETECTOR.detect_anomalies(log_text)` (String input).
  - Pattern UI in live tab updates `ANOMALY_DETECTOR.custom_patterns` and calls `_compile_patterns()` to refresh.

- Offline path:
  - `create_offline_anomaly_tab()` enumerates logs in a folder and runs file analysis in parallel using `ThreadPoolExecutor` and `asyncio.run_in_executor` to avoid blocking the event loop.
  - Per-file analysis calls `ANOMALY_DETECTOR._detect_from_lines(file_handle)` for streaming detection.
  - Results are displayed via `display_offline_results()` and saved with `save_anomalies_to_json()` (note: the code sets a default path to `C:/Amomaly_logs` with fallback to current dir).

## Developer Workflows (Run / Debug / Dev)
- Setup:
  - Create a venv and install deps: `python -m venv .venv` then on Windows: `.venv\Scripts\activate`; `pip install -r requirements.txt`.
- Quick run:
```powershell
python app.py
# open http://localhost:8080/
```
- Development tips:
  - To enable auto-reload while developing set `ui.run(reload=True, show=True)` in `app.py` (or via code changes). Be mindful of concurrency during reloads.
  - Use `print()` and `ui.notify()` for quick debugging messages displayed either in console or in UI.
  - For heavy CPU-bound operations, keep them off the main event loop — use `run_in_executor` or ProcessPool, as `ui_offline` demonstrates.

## UI/Browser Patterns / Conventions
- UI functions follow a simple pattern: `create_..._tab()` and `create_main_ui()` build UI content; they should return None and modify the UI via NiceGUI `ui` objects.
- Table events typically use emitted events with `props.row` and handle payloads using `e.args` or `e.args/hasattr` guards.
- Upload handlers use `get_uploaded_content(e)` (defined in `ui_offline.py`) to support multiple NiceGUI upload event shapes (versions vary).
- Dialogs use generated IDs `anomaly-dialog-{uuid}`; event JS hooks expect these ids — preserve this pattern when adding dialogs.

## Patterns & Performance
- Regex patterns are compiled with `re.IGNORECASE` and combined optimizations are used (grouped combined regex in core to speed batch matching). Keep those performance optimizations intact when modifying detection code.
- Streaming file reads: offline analysis uses `open(file, 'r', encoding='utf-8', errors='ignore')` and passes file object into `_detect_from_lines` — maintain streaming approach for memory efficiency.
- Parallelism: offline uses `max_workers = min(cpu_count * 3, len(log_files), 16)` to limit concurrency — follow similar throttle rules for new concurrent tasks.

## Common Modifications Examples
- Add a custom pattern programmatically:
```python
from anomaly_detector.core import ANOMALY_DETECTOR
ANOMALY_DETECTOR.custom_patterns[r"MyError|FAILURE"] = "MY_ERROR"
ANOMALY_DETECTOR.patterns[ r"MyError|FAILURE"] = "MY_ERROR"
ANOMALY_DETECTOR._compile_patterns()
```
- Analyze a single file programmatically (offline-like):
```python
with open('some.log','r',encoding='utf-8',errors='ignore') as fh:
    anomalies = ANOMALY_DETECTOR._detect_from_lines(fh)
```
- Use the API instead of editing UI state directly: `ANOMALY_DETECTOR.detect_anomalies(log_text)`.

## Project-Specific Gotchas & TODOs
- Missing imports: Some files use `json` or `Optional` without imports (e.g., `ui_live.py`, `ui_display_offline_results.py`, `ui_offline.py` uses `json` in `save_anomalies_to_json`). If adding code that references these, ensure you import the correct modules.
- Hard-coded paths: `save_anomalies_to_json()` defaults to `C:/Amomaly_logs` — change to cross-platform, user-controlled path if adding cross-OS features.
- Guard against UI state references like `if 'pattern_table' in locals():` — they are fragile. Prefer storing references in outer scope variables if you need to reuse them.
- Use `hasattr(e, 'args')`/`e.content` for robust uploaded file support across NiceGUI versions.

## Tests & CI
- There are no tests or CI present. Recommended test additions (small, low-friction):
  - Unit tests for `AnomalyDetector.detect_anomalies()` and `categorize_anomalies()`.
  - Small integration tests to verify `load_pattern_file()` success/error paths with a temp file.
- If you add pytest, include `pytest` in `requirements.txt`.

## When Creating Pull Requests
- Keep UI changes small and incremental.
- For performance changes, add a benchmark test to compare performance with `DEFAULT_ANOMALY_PATTERNS` to avoid regressions.
- When updating patterns: prefer adding to `ANOMALY_DETECTOR.custom_patterns` in runtime; changes to `DEFAULT_ANOMALY_PATTERNS` should be deliberate and documented in PR.

## Files to Inspect When Making Changes
- `app.py` — entrypoint
- `anomaly_detector/core.py` — detection logic (patterns, compilation)
- `anomaly_detector/ui_main.py` — layout and tabs
- `anomaly_detector/ui_live.py` — live UI and manual analyzer
- `anomaly_detector/ui_offline.py` — folder scan, concurrency, and pattern upload
- `anomaly_detector/ui_display_offline_results.py` — results viewer and dialog UI

---
If anything is unclear or you want a risk-assessed PR checklist (e.g., run vsel/debug steps, performance tests to add, or where to add type annotations), tell me and I'll refine this file with examples and tasks. Thank you!