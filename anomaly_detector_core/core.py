from __future__ import annotations

from typing import Dict, List, Tuple, Any, Iterable
from datetime import datetime
import re

DEFAULT_ANOMALY_PATTERNS: Dict[str, str] = {
    # Kernel and System Crashes
    r"Kernel panic": "KERNEL_PANIC",
    r"Crashdump magic": "CRASH_DUMP",
    r"Call Trace": "CALL_TRACE",
    r"Segmentation Fault|segfault": "SEGMENTATION_FAULT",
    r"Backtrace": "BACKTRACE",
    r"watchdog bite": "WATCHDOG_BITE",
    r"Oops": "OOPS_TRACE",

    # Memory Issues
    r"page\+allocation\s+failure": "PAGE_ALLOCATION_FAILURE",
    r"Unable to handle kernel NULL pointer dereference": "MEMORY_CORRUPTION",
    r"Unable to handle kernel paging request": "MEMORY_CORRUPTION",
    r"Out of memory: Kill process": "OUT_OF_MEMORY",
    r"ERROR:NBUF alloc failed": "LOW_MEMORY",

    # Device Reboot Loops
    r"Reboot Reason": "DEVICE_REBOOT",
    r"System restart": "DEVICE_REBOOT",
    # Interface Issues
    r"Interface down": "INTERFACE_DOWN",
    r"Link is down": "INTERFACE_DOWN",
    r"carrier lost": "INTERFACE_DOWN",
    r"entered disabled state": "INTERFACE_DISABLED",

    # Authentication Failures
    r"authentication failed": "AUTH_FAILURE",
    r"Authentication timeout": "AUTH_TIMEOUT",
    r"Invalid credentials": "AUTH_INVALID_CREDS",
    r"Access denied": "AUTH_ACCESS_DENIED",

    # Network Issues
    r"Packet loss": "PACKET_LOSS",
    r"High latency": "HIGH_LATENCY",
    r"Connection timeout": "CONNECTION_TIMEOUT",
    r"No route to host": "NO_ROUTE",
    r"Network unreachable": "NETWORK_UNREACHABLE",

    # Configuration Issues
    r"Configuration mismatch": "CONFIG_MISMATCH",
    r"Invalid configuration": "CONFIG_INVALID",
    r"Configuration error": "CONFIG_ERROR",
    # WiFi Specific Issues
    r"vap_down": "VAP_DOWN",
    r"Received CSA": "CHANNEL_SWITCH",
    r"Invalid beacon report": "BEACON_REPORT_ISSUE",

    # Resource Issues
    r"Resource manager crash": "RESOURCE_MANAGER_CRASH",
    # RCU and Timing Issues
    r"timeout waiting": "TIMEOUT",

    # Warnings
    r"CPU:\d+ WARNING": "CPU_WARNING",
}
# -----------------------------------------------------
# Anomaly detector
# -----------------------------------------------------

class AnomalyDetector:
    """Optimized anomaly detection engine with batch processing"""

    def __init__(self):
        self.patterns: Dict[str, str] = DEFAULT_ANOMALY_PATTERNS.copy()
        self.custom_patterns: Dict[str, str] = {}
        self.compiled_patterns: Dict[re.Pattern, str] = {}

        # Cache for combined regex pattern
        self._combined_pattern = None
        self._pattern_map: Dict[str, str] = {}

        # Lazy compilation flag - compile patterns only when needed
        self._patterns_compiled: bool = False

    def load_pattern_file(self, file_path: str) -> Tuple[bool, str]:
        """Load exception patterns from a Python file"""
        try:
            # Read the file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Execute the file to get the exception_patterns dictionary
            local_vars: Dict[str, Any] = {}
            exec(content, {}, local_vars)

            if "exception_patterns" not in local_vars:
                return False, "File does not contain 'exception_patterns' dictionary"

            patterns = local_vars["exception_patterns"]
            if not isinstance(patterns, dict):
                return False, "'exception_patterns' must be a dictionary"

            # Merge with custom patterns
            self.custom_patterns = patterns
            self.patterns = {**DEFAULT_ANOMALY_PATTERNS, **self.custom_patterns}
            self._compile_patterns()

            return True, f"Loaded {len(patterns)} custom patterns"

        except Exception as e:
            return False, f"Error loading pattern file: {str(e)}"

    def _compile_patterns(self) -> None:
        """Compile regex patterns for faster matching with combined pattern optimization"""
        if self._patterns_compiled:
            return  # Already compiled

        compiled: Dict[re.Pattern, str] = {}
        pattern_parts: List[str] = []
        self._pattern_map = {}

        for idx, (pattern, category) in enumerate(self.patterns.items()):
            try:
                compiled[re.compile(pattern, re.IGNORECASE)] = category
                # Create combined pattern for batch matching
                pattern_parts.append(f"(?P<g{idx}>{pattern})")
                self._pattern_map[f"g{idx}"] = category
            except re.error:
                # Skip invalid regex patterns
                continue

        self.compiled_patterns = compiled

        # Create combined pattern for faster batch matching
        if pattern_parts:
            try:
                combined = "|".join(pattern_parts)
                self._combined_pattern = re.compile(combined, re.IGNORECASE)
            except re.error:
                self._combined_pattern = None
        else:
            self._combined_pattern = None

        self._patterns_compiled = True

    def _detect_from_lines(self, lines: Iterable[str]) -> List[Dict[str, Any]]:
        """Core anomaly detection that works on any line iterable (streaming-friendly)."""
        if not self._patterns_compiled:
            self._compile_patterns()

        anomalies: List[Dict[str, Any]] = []
        ts = datetime.now().isoformat()

        # Use combined pattern for faster matching if available
        if self._combined_pattern and self._pattern_map:
            pattern = self._combined_pattern
            group_map = self._pattern_map

            for line_num, line in enumerate(lines, start=1):
                if not line:
                    continue
                stripped = line.strip()
                if not stripped:
                    continue

                match = pattern.search(stripped)
                if match:
                    for group_name, category in group_map.items():
                        if match.group(group_name):
                            anomalies.append(
                                {
                                    "line_number": line_num,
                                    "line": stripped,
                                    "pattern": match.group(group_name),
                                    "category": category,
                                    "timestamp": ts,
                                }
                            )
                            break  # Only record first match per line
        else:
            compiled_patterns = self.compiled_patterns
            for line_num, line in enumerate(lines, start=1):
                if not line:
                    continue
                stripped = line.strip()
                if not stripped:
                    continue

                for pat, category in compiled_patterns.items():
                    if pat.search(stripped):
                        anomalies.append(
                            {
                                "line_number": line_num,
                                "line": stripped,
                                "pattern": pat.pattern,
                                "category": category,
                                "timestamp": ts,
                            }
                        )
                        break  # Only record first match per line

        return anomalies
    def detect_anomalies(self, log_text: str) -> List[Dict[str, Any]]:
        """Backward-compatible API for callers who pass a single string."""
        return self._detect_from_lines(log_text.splitlines())
    
    def categorize_anomalies(
                            self,
                            anomalies: List[Dict[str, Any]],
                            testplan_name: str = None,
                            testcase_name: str = None,
                            device_name: str = None,
                        ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize anomalies by testplan, testcase, and device"""
        categorized: Dict[str, Any] = {
            "testplan": testplan_name or "Unknown",
            "testcase": testcase_name or "Unknown",
            "device": device_name or "Unknown",
            "anomalies": anomalies,
            "count": len(anomalies),
            "categories": {},
        }

        # Group by category
        for anomaly in anomalies:
            category = anomaly["category"]
            if category not in categorized["categories"]:
                categorized["categories"][category] = []
            categorized["categories"][category].append(anomaly)

        return categorized



# Global anomaly detector singleton
ANOMALY_DETECTOR = AnomalyDetector()
