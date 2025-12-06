from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any

import html
import os
from pathlib import Path

from nicegui import ui


def display_offline_results(anomalies: List[Dict[str, Any]], container: ui.column):
    """Display offline anomaly analysis results"""
    container.clear()

    if not anomalies:
        with container:
            ui.label("No anomalies detected").classes("text-grey-7")
        return

    with container:
        with ui.card().classes("w-full q-pa-md"):
            ui.label(f"Analysis Results: {len(anomalies)} Anomalies Found").classes(
                "text-h6 text-weight-bold q-mb-md"
            )

            # Group by category
            categories = {}
            for anomaly in anomalies:
                cat = anomaly["category"]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(anomaly)
            # Category summary with checkboxes and filtering
            # Keep a reference for the details table to allow dynamic filtering
            details_table = None

            # Build interactive category selection
            with ui.expansion("Category Summary", icon="category").classes("w-full q-mb-md"):
                checkboxes = {}
                selected_categories = set(categories.keys())
                is_programmatic_select_all = False  # guard to avoid recursive event storms

                def apply_filter():
                    """Apply current category selection to details table."""
                    if details_table is None:
                        return
                    filtered = [
                        a for a in anomalies
                        if a.get("category") in selected_categories
                    ]
                    details_table.rows = filtered
                    details_table.update()

                # Select All control
                with ui.row().classes("items-center justify-between w-full q-mb-sm"):
                    select_all_cb = ui.checkbox("Select All", value=True)
                    ui.badge(str(len(anomalies))).props("color-primary")

                def on_select_all(e):
                    nonlocal selected_categories, is_programmatic_select_all
                    # If this change was triggered programmatically from child checkboxes,
                    # do NOT run the full select-all logic again.
                    if is_programmatic_select_all:
                        return

                    # NiceGUI usually passes the new value in e.args or via .value
                    if hasattr(e, "args") and isinstance(e.args, bool):
                        val = e.args
                    elif hasattr(e, "value"):
                        val = e.value
                    else:
                        val = bool(select_all_cb.value)

                    if val:
                        # Select all categories
                        selected_categories = set(categories.keys())
                    else:
                        # Deselect all categories
                        selected_categories.clear()

                    # Sync individual checkboxes
                    for cat, cb in checkboxes.items():
                        is_programmatic_select_all = True
                        cb.value = val
                        cb.update()
                        is_programmatic_select_all = False

                    apply_filter()

                select_all_cb.on("update:model-value", on_select_all)

                # Individual category checkboxes
                for category, items in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("items-center"):
                            cb = ui.checkbox(category, value=True)
                            checkboxes[category] = cb
                        ui.badge(str(len(items))).props("color-negative")

                    def make_handler(cat, cbox):
                        def _on_change(e):
                            nonlocal is_programmatic_select_all

                            # Update selected_categories based on this single checkbox
                            if cbox.value:
                                selected_categories.add(cat)
                            else:
                                selected_categories.discard(cat)

                            # Maintain Select All visual state, but avoid triggering its logic
                            all_selected = len(selected_categories) == len(categories)
                            if select_all_cb.value != all_selected:
                                is_programmatic_select_all = True
                                select_all_cb.value = all_selected
                                select_all_cb.update()
                                is_programmatic_select_all = False

                            apply_filter()
                        return _on_change

                    cb.on("update:model-value", make_handler(category, cb))

            # Detailed table (initially show all anomalies; filtering will adjust rows)
            anomaly_columns = [
                {"name": "file", "label": "File", "field": "file", "align": "left"},
                {"name": "device", "label": "Device", "field": "device", "align": "left"},
                {"name": "line_number", "label": "Line", "field": "line_number", "align": "left"},
                {"name": "category", "label": "Category", "field": "category", "align": "left"},
                {"name": "log_line", "label": "Log Line", "field": "line", "align": "left"},
                {"name": "actions", "label": "Actions", "field": "file", "align": "left"},
            ]

            details_table = ui.table(
                columns=anomaly_columns,
                rows=anomalies,
                row_key="timestamp",
            ).classes("w-full")

            # Add view button to emit row payload
            details_table.add_slot("body-cell-actions", r"""
                <q-td :props="props" auto-width>
                    <q-btn dense flat color="primary" icon="visibility" label="View"
                        @click="$parent.$emit('view-anomaly', props.row)" />
                </q-td>
            """)
            # details_table.add_slot("body-cell-actions", r"""
            #     <q-td props="props" auto-width>
            #         <q-btn dense flat color="primary" icon="visibility" label="View"
            #             @click="() => $parent.emit('view-anomaly', props.row)" />
            #     </q-td>
            # """)
            # Cache to avoid rereads
            _file_cache = {}

            def _get_file_lines(path: str):
                if path not in _file_cache:
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            _file_cache[path] = fh.read().splitlines()
                    except Exception:
                        _file_cache[path] = []
                return _file_cache[path], len(_file_cache[path])

            # Track dialog stacking positions
            _dialog_count = 0
            """Handle view anomaly button clicks (parallel dialog)"""
            def handle_view_anomaly(e):
                nonlocal _dialog_count
                try:
                    # Import uuid
                    import uuid

                    # Get row data from event
                    row_data = e.args if hasattr(e, "args") else None

                    if not isinstance(row_data, dict):
                        ui.notify("Unable to open anomaly details - no row data.", type="warning")
                        return

                    file_path = row_data.get("full_path")
                    line_no = row_data.get("line_number", 1)

                    if not file_path or not os.path.exists(file_path):
                        ui.notify("Original log file not found on disk.", type="negative")
                        return
                    try:
                        line_no = int(line_no)
                    except Exception:
                        line_no = 1

                    # Force unique dialog (parallel)
                    dialog_id = str(uuid.uuid4())
                    offset_x = (_dialog_count * 50) % 300
                    offset_y = (_dialog_count * 40) % 200
                    _dialog_count += 1

                    # Local vars for dialog
                    current_file = file_path
                    lines, total = _get_file_lines(file_path)
                    current_total = total
                    current_target_line = max(1, min(line_no, total if total > 0 else 1))
                    log_html = None
                    go_to_number = None

                    # Create dialog with unique id, non-blocking
                    detail_dialog = ui.dialog().props(f"persistent seamless id=anomaly-dialog-{dialog_id}")

                    # CRITICAL: Define the z-index management function FIRST
                    ui.run_javascript(
                        f"""
                    // CRITICAL FIX: Define global z-index management
                    if (typeof window.lastZIndex === 'undefined') {{
                        window.lastZIndex = 9000;
                    }}

                    function activateDialog(dialogId) {{
                        console.log("Activating dialog: " + dialogId);
                        window.lastZIndex += 100;
                        const dialog = document.getElementById("anomaly-dialog-" + dialogId);
                        if (dialog) {{
                            const card = dialog.querySelector(".q-card");
                            if (card) {{
                                console.log("Setting z-index to: " + window.lastZIndex);
                                card.style.zIndex = window.lastZIndex;
                            }}
                        }}
                    }}

                    // Make it globally available
                    window.activateDialog = activateDialog;

                    // Immediately activate this dialog
                    activateDialog("{dialog_id}");
                    """
                    )
                    # ----------------------------------------------------------------------
                # CONTEXT RENDERING FUNCTION
                # ----------------------------------------------------------------------
                    def _render_context(center_line: int, lines_before: int = 20, lines_after: int = 20, highlight_line: Optional[int] = None):
                        nonlocal log_html, current_file, current_target_line

                        if not current_file:
                            return

                        lines, total = _get_file_lines(current_file)
                        if total <= 0:
                            log_html.set_content("<div class='text-negative'>Failed to read file content.</div>")
                            return
                        clamped=False
                        # Clamp center line
                        if center_line < 1:
                            center_line = 1
                            clamped=True
                        if center_line > total:
                            center_line = total
                            clamped=True
                        start = max(1, center_line - lines_before)
                        end = min(total, center_line + lines_after)
                        current_target_line = center_line                      
                        if go_to_number is not None:
                            # Update go-to max value
                            try:
                                go_to_number.props(f"min=1 max={total} step=1")
                            except:
                                pass
                        from html import escape as _esc
                        parts = []
                        ln_width = len(str(end))

                        # CSS at top of viewer
                        parts.append("""
                        <style>
                        .log-viewer {
                            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
                            white-space: pre;
                            background: #0b0f19;
                            color: #e5e7eb;
                            padding: 12px;
                            border-radius: 8px;
                            max-height: 600px;
                            overflow:auto;
                            border: 1px solid #192937;
                        }
                        .log-ln { display:block; color:#9ca3af; }
                        .log-target { background:#374151; color:#ffebba; }
                        </style>
                        """)

                        # Header info
                        parts.append(
                            f"<div class='text-caption text-grey-5 q-mb-sm'>Showing lines {start}-{end} of {total} "
                            f"({lines_before}/{lines_after} around target)</div>"
                        )

                        parts.append("<div class='log-viewer'>")

                        for idx in range(start - 1, end):
                            text = _esc(lines[idx])
                            num = idx + 1
                            is_target = (highlight_line == num)

                            if is_target:
                                parts.append(
                                    f"<span class='log-ln log-target'><span class='cls'>{num:{ln_width}d}</span> {text}</span>"
                                )
                            else:
                                parts.append(
                                    f"<span class='log-ln'><span class='cls'>{num:{ln_width}d}</span> {text}</span>"
                                )

                        parts.append("</div>")

                        html_content = "\n".join(parts)
                        if log_html:
                            log_html.set_content(html_content)
                        if clamped:
                            ui.notify("Required line out of range;window clamped to file boundaries.", type='info')
                    with detail_dialog:
                        dialog_card = ui.card().classes("w-[1100px] max-w-[95vw] q-pa-md relative").style(
                            f"position: fixed; top: {50 + offset_y}px; left: {50 + offset_x}px; z-index: 9999; cursor: move;"
                        )

                        # ❗CRITICAL: Add click handler to bring dialog to front
                        ui.run_javascript(
                            f"""
                            document.getElementById("anomaly-dialog-{dialog_id}")
                                .querySelector(".q-card")
                                .addEventListener("mousedown", function() {{
                                    window.activateDialog("{dialog_id}");
                                }});
                            """
                        )

                        with dialog_card:
                            with ui.row().classes("items-center justify-between w-full q-mb-sm"):
                                ui.label(f"Anomaly Details: {os.path.basename(current_file)}").classes("text-h6 text-weight-bold")

                                with ui.row().classes("items-center q-gutter-xs"):
                                    ui.button(
                                        icon="minimize",
                                        on_click=lambda: ui.run_javascript(
                                            f'minimizeDialog("{dialog_id}")'
                                        ),
                                    ).props("flat dense round size=sm").tooltip("Minimize")
                                    ui.button(
                                        icon="crop_square",
                                        on_click=lambda: ui.run_javascript(
                                            f'maximizeDialog("{dialog_id}")'
                                        ),
                                    ).props("flat dense round size=sm").tooltip("Maximize/Restore")
                                    ui.button(
                                        icon="close",
                                        on_click=detail_dialog.close,
                                    ).props("flat dense round size=sm color=negative").tooltip("Close")
                            dialog_content = ui.column().classes("w-full")
                            with dialog_content:
                            # File location
                                with ui.row().classes("items-center q-gutter-sm q-mb-xs"):
                                    ui.icon("insert_drive_file").classes("text-grey-7")
                                    ui.label(os.path.basename(file_path)).classes("text-body2")
                                    ui.separator().props("vertical").classes("q-mx-sm")
                                    ui.icon("format_list_numbered").classes("text-grey-7")
                                    ui.label(f"Lines: {total}").classes("text-caption text-grey-7")
                                    ui.separator().props("vertical").classes("q-mx-sm")
                                    ui.icon("my_location")
                                    ui.label(f"Target line: {current_target_line}").classes("text-body2")
                                # Line number navigation
                                with ui.row().classes("items-center q-gutter-sm q-mb-sm"):
                                    ui.label("Go to line").classes("text-caption text-grey-7")

                                    # Input for go-to line
                                    go_to_number = ui.input(label="go to line",value=str(current_target_line)).props("type=number dense outlined")
                                    lines_before_input = (
                                        ui.input("Lines before", value="20")
                                        .props("type=number dense outlined min=0 max=500 step=1")
                                        .classes("w-28")
                                    )

                                    lines_after_input = (
                                        ui.input("Lines after", value="20")
                                        .props("type=number dense outlined min=0 max=500 step=1")
                                        .classes("w-28") )
                                    def _submit_go_to():
                                        nonlocal current_target_line
                                        # Parse and validate line number
                                        val = go_to_number.value if go_to_number is not None else ""
                                        try:
                                            num = int(float(val))
                                        except Exception:
                                            ui.notify("Please enter a valid numeric line number.", type="warning")
                                            return

                                        if current_total <= 0:
                                            ui.notify("Log file is empty or unreadable.", type="warning")
                                            return
                                        clamped_num = max(1, min(num, current_total))
                                        if clamped_num != num:
                                            ui.notify(
                                                f"Target line clamped to {clamped_num} "
                                                "(outside of range).",
                                                type="info",
                                            )

                                        current_target_line = clamped_num
                                        try:
                                            lines_before = int(float(lines_before_input.value or "20"))
                                            lines_after = int(float(lines_after_input.value or "20"))
                                        except ValueError:
                                            lines_before, lines_after = 20, 20
                                        _render_context(current_target_line,lines_before=lines_before,lines_after=lines_after,highlight_line=current_target_line)

                                        # CRITICAL: Update active dialog z-index
                                        ui.run_javascript(f"window.activateDialog('{dialog_id}')")
                                    def _update_content():
                                        try:
                                            lines_before = int(float(lines_before_input.value or "20"))
                                            lines_after = int(float(lines_after_input.value or "20"))
                                        except ValueError:
                                            lines_before, lines_after = 20, 20
                                        _render_context(current_target_line,lines_before=lines_before,lines_after=lines_after,highlight_line=current_target_line)
                                        ui.run_javascript(f"window.activateDialog('{dialog_id}')")
                                    lines_before_input.on('blur',_update_content)
                                    lines_after_input.on('blur',_update_content)
                                    ui.button("Go",icon="play_arrow",on_click=_submit_go_to).props("color=primary")
                                    ui.button("Refresh",icon="refresh",on_click=_update_content).props("outline").tooltip("Update context view")
                                    # HTML Log View
                                log_html = ui.html("",sanitize=False).classes("q-mt-md w-full")
                        ui.run_javascript("""
                        // Define window control functions globally if not already defined
                        if (!window.minimizeDialog) {
                            window.minimizeDialog = function (dialogId) {
                                const dialog = document.getElementById('anomaly-dialog-' + dialogId);
                                if (!dialog) return;

                                const card = dialog.querySelector('.q-card');
                                if (!card) return;

                                // Store current size before minimizing
                                if (!card.dataset.originalHeight) {
                                    card.dataset.originalHeight = card.offsetHeight + 'px';
                                    card.datase
                                    t.originalWidth  = card.offsetWidth  + 'px';
                                }

                                // Toggle minimized state
                                if (card.dataset.minimized === 'true') {
                                    // Restore from minimized
                                    const content = card.querySelectorAll('.q-card > div:not(:first-child)');
                                    content.forEach(el => el.style.display = 'block');

                                    card.style.height = card.dataset.wasMaximized === 'true'
                                        ? '80vh'
                                        : (card.dataset.originalHeight || 'auto');

                                    card.dataset.minimized = 'false';
                                } else {
                                    // Minimize
                                    const content = card.querySelectorAll('.q-card > div:not(:first-child)');
                                    content.forEach(el => el.style.display = 'none');

                                    card.dataset.wasMaximized = card.dataset.maximized || 'false';
                                    card.style.height = '60px';
                                    card.dataset.minimized = 'true';
                                    card.dataset.maximized = 'false';
                                }

                                // CRITICAL: Activate dialog after minimizing
                                window.activateDialog(dialogId);
                            };

                            window.maximizeDialog = function (dialogId) {
                                const dialog = document.getElementById('anomaly-dialog-' + dialogId);
                                if (!dialog) return;

                                const card = dialog.querySelector('.q-card');
                                if (!card) return;

                                // Store original size/position if not already stored
                                if (!card.dataset.originalHeight) {
                                    card.dataset.originalHeight = card.offsetHeight + 'px';
                                    card.dataset.originalWidth  = card.offsetWidth  + 'px';
                                    card.dataset.originalLeft   = card.style.left;
                                    card.dataset.originalTop    = card.style.top;
                                }

                                // Toggle maximized state
                                if (card.dataset.maximized === 'true') {
                                    // Restore from maximized
                                    card.style.width  = card.dataset.originalWidth  || '1100px';
                                    card.style.height = card.dataset.originalHeight || 'auto';
                                    card.style.left   = card.dataset.originalLeft   || '50px';
                                    card.style.top    = card.dataset.originalTop    || '50px';
                                    card.dataset.maximized = 'false';
                                } else {
                                    // Maximize
                                    card.dataset.minimized = 'false';

                                    const content = card.querySelectorAll('.q-card > div:not(:first-child)');
                                    content.forEach(el => el.style.display = 'block');

                                    card.style.width  = '80vw';
                                    card.style.height = '80vh';
                                    card.style.left   = '10vw';
                                    card.style.top    = '10vh';
                                    card.dataset.maximized = 'true';
                                }

                                // CRITICAL: Activate dialog after maximizing
                                window.activateDialog(dialogId);
                            };
                        }
                        """)
                        ui.run_javascript(f"""
                        (function() {{
                            const dialog = document.getElementById('anomaly-dialog-{dialog_id}');
                            if (!dialog) return;
                            const card = dialog.querySelector('.q-card');
                            if (!card) return;

                            if (!window.dialogPositions) window.dialogPositions = {{}};
                            if (!window.dialogPositions['{dialog_id}']) {{
                                window.dialogPositions['{dialog_id}'] = {{x: 50, y: 50}};
                            }}

                            let isDragging = false;
                            let currentX = 0;
                            let currentY = 0;
                            let initialX = 0;
                            let initialY = 0;
                            let xOffset = window.dialogPositions['{dialog_id}'].x;
                            let yOffset = window.dialogPositions['{dialog_id}'].y;

                            // Apply last known position
                            card.style.left = xOffset + "px";
                            card.style.top = yOffset + "px";

                            function dragStart(e) {{
                                if (e.target.closest('.q-btn') ||
                                    e.target.closest('input') ||
                                    e.target.closest('textarea')) {{
                                    return;
                                }}

                                if (e.type === "touchstart") {{
                                    initialX = e.touches[0].clientX - xOffset;
                                    initialY = e.touches[0].clientY - yOffset;
                                }} else {{
                                    initialX = e.clientX - xOffset;
                                    initialY = e.clientY - yOffset;
                                }}

                                if (e.target === card || e.target.closest('.text-h6')) {{
                                    isDragging = true;
                                    card.style.cursor = "grabbing";
                                }}
                            }}

                            function dragEnd(e) {{
                                initialX = currentX;
                                initialY = currentY;
                                isDragging = false;
                                card.style.cursor = "move";
                            }}

                            function drag(e) {{
                                if (!isDragging) return;
                                e.preventDefault();

                                if (e.type === "touchmove") {{
                                    currentX = e.touches[0].clientX - initialX;
                                    currentY = e.touches[0].clientY - initialY;
                                }} else {{
                                    currentX = e.clientX - initialX;
                                    currentY = e.clientY - initialY;
                                }}

                                // Update position
                                const maxX = window.innerWidth - card.offsetWidth;
                                const maxY = window.innerHeight - card.offsetHeight;
                                xOffset = Math.max(0, Math.min(currentX, maxX));
                                yOffset = Math.max(0, Math.min(currentY, maxY));

                                card.style.left = xOffset + "px";
                                card.style.top = yOffset + "px";

                                // CRITICAL: Update our global position variable during drag
                                window.dialogPositions['{dialog_id}'].x = xOffset;
                                window.dialogPositions['{dialog_id}'].y = yOffset;
                            }}

                            card.addEventListener("mousedown", dragStart, false);
                            document.addEventListener("mouseup", dragEnd, false);
                            document.addEventListener("mousemove", drag, false);

                            card.addEventListener("touchstart", dragStart, false);
                            card.addEventListener("touchend", dragEnd, false);
                            card.addEventListener("touchmove", drag, false);
                        }})();
                    """)
                    detail_dialog.open()
                    _render_context(current_target_line,lines_before=20,lines_after=20,highlight_line=current_target_line)
                except Exception as ex:
                    print(f"Error in handle_view_anomaly: {ex}")
                    ui.notify("Error opening anomaly details.", type="negative")
            details_table.on("view-anomaly", handle_view_anomaly)
            # Export button row
            with ui.row().classes("q-mt-md"):
                ui.button(
                    "Export to JSON",
                    on_click=lambda: export_anomalies(details_table.rows),
                    icon="download",
                ).props("outline")
                        



def export_anomalies(anomalies: List[Dict[str, Any]]) -> None:
    """Export anomalies to JSON file."""
    if not anomalies:
        ui.notify('No anomalies to export', type='warning')
        return

    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'anomalies_{timestamp}.json'
        json_data = json.dumps(anomalies, indent=2)
        ui.download(json_data.encode('utf-8'), filename=filename)
        ui.notify(f'Exported {len(anomalies)} anomalies to {filename}', type='positive')
    except Exception as e:
        ui.notify(f'Export failed: {e}', type='negative')



def clear_live_anomalies(table: ui.table) -> None:
    """Clear live anomaly table."""
    table.rows = []
    table.update()
    ui.notify('Anomalies cleared', type='info')


