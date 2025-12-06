from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any

import os
import re
from nicegui import ui

from .core import DEFAULT_ANOMALY_PATTERNS, ANOMALY_DETECTOR
from .ui_offline import get_uploaded_content  # reuse the shared helper


def create_live_anomaly_tab():

    # Create the Live Anomaly Detection Tab
    with ui.column().classes("w-full q-gutter-md"):
        ui.label("Live Anomaly Detection").classes("text-h6 text-weight-bold")
        ui.label(
            "Monitor real-time device logs for anomalies during test execution"
        ).classes("text-body2 text-grey-7")

    # ---------------------------------------------------------------------
    # Pattern Management Section
    # ---------------------------------------------------------------------
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Pattern Management").classes(
                "text-subtitle1 text-weight-bold q-mb-sm"
            )
            ui.label(
                "Manage anomaly detection patterns – upload files or edit patterns directly"
            ).classes("text-caption text-grey-7 q-mb-md")

            pattern_status = ui.label(
                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
            ).classes("text-positive")

            # Pattern management tabs
            with ui.tabs().classes("w-full") as pattern_tabs:
                upload_tab = ui.tab("Upload File", icon="upload_file")
                edit_tab = ui.tab("Edit Patterns", icon="edit")
                export_tab = ui.tab("Export", icon="download")
            # ---------------------------------------------------------------------
            # Upload Tab
            # ---------------------------------------------------------------------
            with ui.tab_panels(pattern_tabs,value=upload_tab).classes("w-full"):
                with ui.tab_panel(upload_tab):
                    ui.label("Upload Exception Pattern File").classes("text-body2 text-weight-bold q-mb-sm")
                    ui.label("Upload a .py file containing exception patterns").classes("text-caption text-grey-7 q-mb-md")
                    def handle_pattern_upload(e):
                        try:
                            # Save uploaded file temporarily
                            content = get_uploaded_content(e)
                            temp_path = "temp_exception_patterns.py"

                            with open(temp_path, "wb") as f:
                                f.write(content)

                            # Load patterns
                            success, message = ANOMALY_DETECTOR.load_pattern_file(temp_path)

                            if success:
                                pattern_status.text = f"✔ {message}"
                                pattern_status.classes("text-positive")

                                ui.notify(message, type="positive")

                                # Refresh pattern editor if it exists
                                if "pattern_table" in locals():
                                    refresh_pattern_table()
                            else:
                                pattern_status.text = f"✘ {message}"
                                pattern_status.classes("text-negative")
                                ui.notify(message, type="negative")

                            # Clean up temp file
                            try:
                                os.remove(temp_path)
                            except:
                                pass

                        except Exception as ex:
                            pattern_status.text = f"✘ Error: {str(ex)}"
                            pattern_status.classes("text-negative")
                            ui.notify(f"Error: {str(ex)}", type="negative")

                    ui.upload(
                        label="Upload Exception Pattern .py File",
                        on_upload=handle_pattern_upload,
                        auto_upload=True,
                    ).props("accept=.py").classes("w-full")
                with ui.tab_panel(edit_tab):
                    ui.label("Pattern Editor").classes("text-body2 text-weight-bold q-mb-sm")
                    ui.label("Add, edit, or delete anomaly detection patterns").classes("text-caption text-grey-7 q-mb-md")
                    # Add new pattern section
                    with ui.expansion("Add New Pattern", icon="add").classes("w-full q-mb-md"):
                        with ui.row().classes("w-full items-end q-gutter-sm"):
                            new_pattern_input = ui.input(
                                "Regex Pattern",
                                placeholder="e.g., error|fail|exception",
                            ).classes("flex-grow")

                            new_category_input = ui.input(
                                "Category",
                                placeholder="e.g., ERROR_GENERAL",
                            ).classes("w-48")

                            def add_new_pattern():
                                pattern = (new_pattern_input.value or "").strip()
                                category = (new_category_input.value or "").strip()

                                if not pattern or not category:
                                    ui.notify(
                                        "Both pattern and category are required",
                                        type="warning",
                                    )
                                    return

                                # Test if pattern is valid regex
                                try:
                                    re.compile(pattern, re.IGNORECASE)
                                except re.error as ex:
                                    ui.notify(
                                        f"Invalid regex pattern: {str(ex)}",
                                        type="negative",
                                    )
                                    return

                                # Add to custom patterns
                                ANOMALY_DETECTOR.custom_patterns[pattern] = category
                                ANOMALY_DETECTOR.patterns[pattern] = category
                                ANOMALY_DETECTOR._compile_patterns()

                                # Clear inputs
                                new_pattern_input.value = ""
                                new_category_input.value = ""

                                # Refresh displays
                                pattern_status.text = (
                                    f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                    f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                    f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                                )
                                refresh_pattern_table()

                                ui.notify(
                                    f"Added pattern: {pattern} -> {category}",
                                    type="positive",
                                )

                            ui.button(
                                "Add Pattern",
                                icon="add",
                                on_click=add_new_pattern,
                            ).props("color=primary")

                    # Pattern table columns
                    pattern_columns = [
                        {"name": "pattern", "label": "Regex Pattern", "field": "pattern", "align": "left"},
                        {"name": "category", "label": "Category", "field": "category", "align": "left"},
                        {"name": "type", "label": "Type", "field": "type", "align": "left"},
                        {"name": "actions", "label": "Actions", "field": "pattern", "align": "left"},
                    ]

                    def get_pattern_rows():
                        rows = []

                        # Add default patterns
                        for pattern, category in DEFAULT_ANOMALY_PATTERNS.items():
                            rows.append({
                                "pattern": pattern,
                                "category": category,
                                "type": "Default",
                                "is_default": True,
                            })

                        # Add custom patterns
                        for pattern, category in ANOMALY_DETECTOR.custom_patterns.items():
                            rows.append({
                                "pattern": pattern,
                                "category": category,
                                "type": "Custom",
                                "is_default": False,
                            })
                        return rows
                    pattern_table = ui.table(
                    columns=pattern_columns,
                    rows=get_pattern_rows(),
                    row_key="pattern").classes("w-full")

                    # Add action buttons to pattern table - allow editing of all patterns
                    pattern_table.add_slot("body-cell-actions", r"""
                        <q-td :props="props" auto-width>
                            <q-btn dense flat color='primary' icon='edit'
                                @click.stop.prevent="$parent.$emit('edit-pattern', props.row)" 
                                title="Edit Patern" />
                            <q-btn dense flat color='negative' icon='delete'
                                @click.stop.prevent="$parent.$emit('delete-pattern', props.row)" 
                                title="Delete Patern"/>
                            <q-btn v-if="!props.row.is_default" dense flat color='secondary' icon='content_copy'
                                @click.stop.prevent="$parent.$emit('copy-pattern', props.row)" 
                                title="Copy to Custom"/>
                        </q-td>
                    """)

                    def refresh_pattern_table():
                        pattern_table.rows = get_pattern_rows()
                        pattern_table.update()

                    # Edit pattern dialog
                    edit_dialog = ui.dialog()

                    def show_edit_dialog(pattern_data):
                        edit_dialog.clear()
                        with edit_dialog:
                            with ui.card().classes("w-96 q-pa-md"):
                                ui.label("Edit Pattern").classes("text-h6 text-weight-bold q-mb-md")

                                edit_pattern_input = ui.input(
                                    "Regex Pattern",
                                    value=pattern_data["pattern"],
                                ).classes("w-full q-mb-sm")

                                edit_category_input = ui.input(
                                    "Category",
                                    value=pattern_data["category"],
                                ).classes("w-full q-mb-md")

                                with ui.row().classes("w-full justify-end q-gutter-sm"):
                                    ui.button(
                                        "Cancel",
                                        on_click=edit_dialog.close,
                                    ).props("flat")

                                    def save_edit():
                                        old_pattern = pattern_data["pattern"]
                                        new_pattern = edit_pattern_input.value.strip()
                                        new_category = edit_category_input.value.strip()

                                        if not new_pattern or not new_category:
                                            ui.notify(
                                                "Both pattern and category are required",
                                                type="warning",
                                            )
                                            return

                                        # Test if pattern is valid regex
                                        try:
                                            re.compile(new_pattern, re.IGNORECASE)
                                        except re.error as ex:
                                            ui.notify(
                                                f"Invalid regex pattern: {str(ex)}",
                                                type="negative",
                                            )
                                            return

                                        # Add / update as custom pattern
                                        if old_pattern in ANOMALY_DETECTOR.custom_patterns:
                                            del ANOMALY_DETECTOR.custom_patterns[old_pattern]
                                        if old_pattern in ANOMALY_DETECTOR.patterns:
                                            del ANOMALY_DETECTOR.patterns[old_pattern]

                                        ANOMALY_DETECTOR.custom_patterns[new_pattern] = new_category
                                        ANOMALY_DETECTOR.patterns[new_pattern] = new_category

                                        ANOMALY_DETECTOR._compile_patterns()

                                        # Refresh displays
                                        pattern_status.text = (
                                            f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                            f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                            f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                                        )
                                        refresh_pattern_table()
                                        ui.notify(
                                            f"Saved pattern: {new_pattern} ({new_category})",
                                            type="positive",
                                        )
                                        edit_dialog.close()

                                    ui.button(
                                        "Save",
                                        on_click=save_edit,
                                    ).props("color=primary")
                        edit_dialog.open()
                    def handle_edit_pattern(e):
                        row_data = e.args if hasattr(e, "args") else None
                        if row_data:
                            def show_full_edit_dialog(pattern_data):
                                edit_dialog.clear()
                                with edit_dialog:
                                    with ui.card().classes("w-96 q-pa-md"):
                                        ui.label("Edit Pattern").classes("text-h6 text-weight-bold q-mb-md")

                                        edit_pattern_input = ui.input(
                                            "Regex Pattern", value=pattern_data["pattern"]
                                        ).classes("w-full q-mb-sm")

                                        edit_category_input = ui.input(
                                            "Category", value=pattern_data["category"]
                                        ).classes("w-full q-mb-md")

                                        with ui.row().classes("w-full justify-end q-gutter-sm"):
                                            ui.button(
                                                "Cancel",
                                                on_click=edit_dialog.close
                                            ).props("flat")

                                            def save_edit():
                                                old_pattern = pattern_data["pattern"]
                                                new_pattern = edit_pattern_input.value.strip()
                                                new_category = edit_category_input.value.strip()
                                                is_default = pattern_data.get("is_default", False)

                                                if not new_pattern or not new_category:
                                                    ui.notify(
                                                        "Both pattern and category are required",
                                                        type="warning"
                                                    )
                                                    return

                                                # Test if pattern is valid regex
                                                try:
                                                    re.compile(new_pattern, re.IGNORECASE)
                                                except re.error as ex:
                                                    ui.notify(
                                                        f"Invalid regex pattern: {str(ex)}",
                                                        type="negative"
                                                    )
                                                    return

                                                if is_default:
                                                    # Editing a default pattern
                                                    global DEFAULT_ANOMALY_PATTERNS
                                                    DEFAULT_ANOMALY_PATTERNS = dict(DEFAULT_ANOMALY_PATTERNS)

                                                    if old_pattern in DEFAULT_ANOMALY_PATTERNS:
                                                        del DEFAULT_ANOMALY_PATTERNS[old_pattern]

                                                    DEFAULT_ANOMALY_PATTERNS[new_pattern] = new_category

                                                    # Sync detector patterns
                                                    ANOMALY_DETECTOR.patterns = {
                                                        **DEFAULT_ANOMALY_PATTERNS,
                                                        **ANOMALY_DETECTOR.custom_patterns
                                                    }

                                                    ui.notify(
                                                        f"Edited default pattern: {new_pattern} ({new_category})",
                                                        type="positive"
                                                    )

                                                else:
                                                    # Editing a custom pattern
                                                    if old_pattern in ANOMALY_DETECTOR.custom_patterns:
                                                        del ANOMALY_DETECTOR.custom_patterns[old_pattern]

                                                    if old_pattern in ANOMALY_DETECTOR.patterns:
                                                        del ANOMALY_DETECTOR.patterns[old_pattern]

                                                    ANOMALY_DETECTOR.custom_patterns[new_pattern] = new_category
                                                    ANOMALY_DETECTOR.patterns[new_pattern] = new_category

                                                    ui.notify(
                                                        f"Edited custom pattern: {new_pattern} ({new_category})",
                                                        type="positive"
                                                    )

                                                ANOMALY_DETECTOR._compile_patterns()

                                                pattern_status.text = (
                                                    f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                                    f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                                    f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                                                )

                                                refresh_pattern_table()
                                                edit_dialog.close()

                                            ui.button(
                                                "Save",
                                                on_click=save_edit
                                            ).props("color=primary")

                                edit_dialog.open()
                            show_full_edit_dialog(row_data)
                        # Bind table event
                        # pattern_table.on("edit-pattern", handle_edit_pattern)
                    def handle_delete_pattern(e):
                        row_data = e.args if hasattr(e, "args") else None
                        if  row_data:
                            pattern = row_data["pattern"]
                            is_default = row_data.get("is_default", False)

                            if is_default:
                                # Delete from the defaults
                                global DEFAULT_ANOMALY_PATTERNS
                                DEFAULT_ANOMALY_PATTERNS = dict(DEFAULT_ANOMALY_PATTERNS)
                                if pattern in DEFAULT_ANOMALY_PATTERNS:
                                    del DEFAULT_ANOMALY_PATTERNS[pattern]

                                # Update detector patterns as well
                                ANOMALY_DETECTOR.patterns = {
                                    **DEFAULT_ANOMALY_PATTERNS,
                                    **ANOMALY_DETECTOR.custom_patterns,
                                }
                                ui.notify(
                                    f"Deleted default pattern: {pattern}",
                                    type="positive",
                                )
                            else:
                                # Remove from custom patterns
                                if pattern in ANOMALY_DETECTOR.custom_patterns:
                                    del ANOMALY_DETECTOR.custom_patterns[pattern]
                                if pattern in ANOMALY_DETECTOR.patterns:
                                    del ANOMALY_DETECTOR.patterns[pattern]

                                ui.notify(
                                    f"Deleted custom pattern: {pattern}",
                                    type="positive",
                                )

                            ANOMALY_DETECTOR._compile_patterns()
                            pattern_status.text = (
                                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                            )
                            refresh_pattern_table()

                    def handle_copy_pattern(e):
                        row_data = e.args if hasattr(e, "args") else None
                        if  row_data:
                            pattern = row_data["pattern"]
                            category = row_data["category"]

                            # Add to custom patterns
                            ANOMALY_DETECTOR.custom_patterns[pattern] = category
                            ANOMALY_DETECTOR._compile_patterns()

                            # Refresh displays
                            pattern_status.text = (
                                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                            )
                            refresh_pattern_table()
                            ui.notify(
                                f"Copied pattern to custom: {pattern}",
                                type="positive",
                            )

                    pattern_table.on("edit-pattern", handle_edit_pattern)
                    pattern_table.on("delete-pattern", handle_delete_pattern)
                    pattern_table.on("copy-pattern", handle_copy_pattern)

                with ui.tab_panel(export_tab):
                    ui.label("Export Patterns").classes("text-body2 text-weight-bold q-mb-sm")
                    ui.label("Export current patterns to a Python file").classes("text-caption text-grey-7 q-mb-md")

                    def export_patterns():
                        try:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"exception_patterns_{timestamp}.py"

                            content = "# Anomaly Detection Patterns\n\n"
                            content += (
                                "# Generated on "
                                + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                + "\n\n"
                            )
                            content += "exception_patterns = {\n"
                            for pattern, category in sorted(ANOMALY_DETECTOR.patterns.items()):
                                escaped_pattern = pattern.replace("\\", "\\\\").replace('"', '\\"')
                                content += f'    r"{escaped_pattern}": "{category}",\n'
                            content += "}\n"

                            ui.download(content.encode("utf-8"), filename=filename)
                            ui.notify(
                                f"Exported {len(ANOMALY_DETECTOR.patterns)} patterns to {filename}",
                                type="positive",
                            )
                        except Exception as e:
                            ui.notify(f"Export failed: {str(e)}", type="negative")

                    def export_custom_only():
                        try:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"custom_patterns_{timestamp}.py"

                            content = "# Custom Anomaly Detection Patterns\n\n"
                            content += (
                                "# Generated on "
                                + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                + "\n\n"
                            )
                            content += "exception_patterns = {\n"
                            for pattern, category in sorted(ANOMALY_DETECTOR.custom_patterns.items()):
                                escaped_pattern = pattern.replace("\\", "\\\\").replace('"', '\\"')
                                content += f'    r"{escaped_pattern}": "{category}",\n'
                            content += "}\n"

                            ui.download(content.encode("utf-8"), filename=filename)
                            ui.notify(
                                f"Exported {len(ANOMALY_DETECTOR.custom_patterns)} custom patterns "
                                f"to {filename}",
                                type="positive",
                            )
                        except Exception as e:
                            ui.notify(f"Export failed: {str(e)}", type="negative")

                    with ui.row().classes("q-gutter-sm"):
                        ui.button("Export All Patterns", icon="download",
                                  on_click=export_patterns).props("color=primary")
                        ui.button("Export Custom Only", icon="download",
                                  on_click=export_custom_only).props("outline")

                    ui.separator().classes("q-my-md")

                    ui.label("Reset Patterns") \
                        .classes("text-body2 text-weight-bold q-mb-sm")
                    ui.label("Reset patterns to default state") \
                        .classes("text-caption text-grey-7 q-mb-md")

                    def reset_to_defaults():
                        ANOMALY_DETECTOR.custom_patterns.clear()
                        ANOMALY_DETECTOR.patterns = DEFAULT_ANOMALY_PATTERNS.copy()
                        ANOMALY_DETECTOR._compile_patterns()
                        pattern_status.text = (
                            f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                            f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                            f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                        )
                        if "pattern_table" in locals():
                            refresh_pattern_table()
                        ui.notify("Reset to default patterns", type="positive")

                    ui.button("Reset to Defaults", icon="restore",
                              on_click=reset_to_defaults).props("color=negative outline")
        # ------------------------------------------------------------------
        # Live anomaly display / manual log testing
        # ------------------------------------------------------------------
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Detected anomalies").classes(
                "text-subtitle1 text-weight-bold q-mb-sm"
            )
            ui.label(
                "Anomalies will appear here when detected in log files"
            ).classes("text-caption text-grey-7 q-mb-md")

            # Expansion panel for manual log testing
            with ui.expansion(
                "Test with Log Input", icon="text_snippet"
            ).classes("w-full q-mb-md"):

                ui.label("Paste log text to test anomaly detection").classes(
                    "text-caption text-grey-7 q-mb-sm"
                )

                log_input = ui.textarea(
                    "Log Text",
                    placeholder="Paste log text here...",
                ).classes("w-full").props("rows=4")

                def analyze_log_text():
                    log_text = log_input.value or ""
                    if not log_text.strip():
                        ui.notify(
                            "Please enter log text to analyze", type="warning"
                        )
                        return

                    anomalies = ANOMALY_DETECTOR.detect_anomalies(log_text)

                    if not anomalies:
                        ui.notify(
                            "No anomalies detected in the provided log text",
                            type="info",
                        )
                        return

                    # Format anomalies for display
                    formatted_anomalies = []
                    for anomaly in anomalies:
                        formatted_anomalies.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "testplan": "Manual Test",
                            "testcase": "Log Analysis",
                            "device": "Manual Input",
                            "category": anomaly.get("category"),
                            "line": anomaly["line"],
                        })

                    # Update the table
                    anomaly_table.rows = formatted_anomalies
                    anomaly_table.update()

                    ui.notify(
                        f"Detected {len(anomalies)} anomalies", type="positive"
                    )

                ui.button(
                    "Analyze Log",
                    icon="search",
                    on_click=analyze_log_text,
                ).props("color=primary")

            # ------------------------------------------------------------------
            # Anomaly table columns
            # ------------------------------------------------------------------
            anomaly_columns = [
                {"name": "timestamp", "label": "Timestamp",
                "field": "timestamp", "align": "left"},
                {"name": "testplan", "label": "Testplan",
                "field": "testplan", "align": "left"},
                {"name": "testcase", "label": "Testcase",
                "field": "testcase", "align": "left"},
                {"name": "device", "label": "Device",
                "field": "device", "align": "left"},
                {"name": "category", "label": "Category",
                "field": "category", "align": "left"},
                {"name": "line", "label": "Log Line",
                "field": "line", "align": "left"},
                {"name": "actions", "label": "Actions",
                "field": "actions", "align": "left"},
            ]
            anomaly_table = ui.table(
                columns=anomaly_columns,
                rows=[],
                row_key="timestamp"
            ).classes("w-full")

            # Add view button to emit row payload
            anomaly_table.add_slot("body-cell-actions", """
                <q-td :props="props" auto-width>
                    <q-btn dense flat color='primary' icon='visibility' label='View'
                        @click="$parent.$emit('view-anomaly', props.row)" />
                </q-td>
            """)

            # Handle the view-anomaly event
            def handle_live_view_anomaly(e):
                """Handle view anomaly button clicks for live anomalies"""
                try:
                    import uuid

                    # Get row data from event
                    row_data = e.args if hasattr(e, 'args') else None

                    if not isinstance(row_data, dict):
                        ui.notify("Unable to open anomaly details - no row data.", type="warning")
                        return

                    # Extract fields
                    line = row_data.get("line")
                    category = row_data.get("category")
                    device = row_data.get("device")
                    timestamp = row_data.get("timestamp")
                    dialog_id = str(uuid.uuid4())

                    # Create dialog with unique identifier
                    detail_dialog = ui.dialog().props(f"persistent seamless id=anomaly-dialog-{dialog_id}")

                    with detail_dialog:
                        card = ui.card().classes("w-[700px] max-w-[95vw] q-pa-md").style(
                            "z-index:1000; cursor: move; position: fixed; top: 50px; left: 50px;"
                        )

                        with card:
                            ui.label("Anomaly Detail").classes("text-h6 text-weight-bold q-mb-md")

                            with ui.column().classes("w-full q-gutter-sm"):
                                with ui.row().classes("items-center"):
                                    ui.icon("event").classes("q-mr-xs")
                                    ui.label(f"Timestamp: {timestamp}").classes("text-body2")

                                with ui.row().classes("items-center"):
                                    ui.icon("schedule").classes("q-mr-xs")
                                    ui.label(f"Category: {category}").classes("text-body2")

                                with ui.row().classes("items-center"):
                                    ui.icon("devices").classes("q-mr-xs")
                                    ui.label(f"Device: {device}").classes("text-body2")
                                ui.separator()
                                ui.label("Log Line:").classes("text-body2 text-weight-bold")
                                with ui.card().classes("q-pa-sm bg-grey-2"):
                                    ui.label(line).classes("text-body2 text-mono")
                            with ui.row().classes("justify-end q-mt-md"):
                                ui.button("Close", on_click=detail_dialog.close).props("color=primary")

                    ui.run_javascript(f'''  
                    (function() {{
                        const dialog = document.getElementById('anomaly-dialog');
                        if (!dialog) return;

                        const card = dialog.querySelector('.q-card');
                        if (!card) return;

                        let isDragging = false;
                        let currentX = 0;
                        let currentY = 0;
                        let initialX = 0;
                        let initialY = 0;
                        let xOffset = 50;
                        let yOffset = 50;

                        function dragStart(e) {{
                            if (e.target.closest('.q-btn') || 
                                e.target.closest('input') || 
                                e.target.closest('textarea')) {{
                                return;
                            }}

                            if (e.type === 'touchstart') {{
                                initialX = e.touches[0].clientX - xOffset;
                                initialY = e.touches[0].clientY - yOffset;
                            }} else {{
                                initialX = e.clientX - xOffset;
                                initialY = e.clientY - yOffset;
                            }}

                            if (e.target === card || e.target.closest('.text-h6')) {{
                                isDragging = true;
                                card.style.cursor = 'grabbing';
                            }}
                        }}

                        function dragEnd(e) {{
                            initialX = currentX;
                            initialY = currentY;
                            isDragging = false;
                            card.style.cursor = 'move';
                        }}

                        function drag(e) {{
                            if (!isDragging) return;
                            e.preventDefault();

                            if (e.type === 'touchmove') {{
                                currentX = e.touches[0].clientX - initialX;
                                currentY = e.touches[0].clientY - initialY;
                            }} else {{
                                currentX = e.clientX - initialX;
                                currentY = e.clientY - initialY;
                            }}

                            xOffset = currentX;
                            yOffset = currentY;

                            // Keep dialog within viewport bounds
                            const maxX = window.innerWidth - card.offsetWidth;
                            const maxY = window.innerHeight - card.offsetHeight;

                            xOffset = Math.max(0, Math.min(xOffset, maxX));
                            yOffset = Math.max(0, Math.min(yOffset, maxY));

                            card.style.left = xOffset + "px";
                            card.style.top = yOffset + "px";
                        }}

                        card.addEventListener('mousedown', dragStart, false);
                        card.addEventListener('mouseup', dragEnd, false);
                        card.addEventListener('mousemove', drag, false);

                        card.addEventListener('touchstart', dragStart, false);
                        card.addEventListener('touchend', dragEnd, false);
                        card.addEventListener('touchmove', drag, false);
                    }})();
                ''')

                # Open detailed dialog
                    detail_dialog.open()
                except Exception as e:
                    ui.notify(f"Error opening anomaly details: {e}", type="negative")

            # Bind the event for the table
            anomaly_table.on("view-anomaly", handle_live_view_anomaly)
# ---------------------------------------------------------------------
# Main page + NiceGUI app bootstrap
# ---------------------------------------------------------------------


