from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any

import asyncio
import concurrent.futures
import os
import time

from nicegui import ui

from .core import DEFAULT_ANOMALY_PATTERNS, ANOMALY_DETECTOR
from .ui_display_offline_results import display_offline_results


def get_uploaded_content(e) -> bytes:
    """
    Robustly extract uploaded file bytes from NiceGUI upload event across versions.
    Tries multiple attributes: .content, .file, .files, .args.
    """
    # direct content on event
    if hasattr(e, "content") and e.content is not None:
        try:
            return e.content.read()
        except Exception:
            pass

    # single file attribute
    if hasattr(e, "file") and e.file is not None:
        try:
            return e.file.read()
        except Exception:
            pass

    # list of files
    if hasattr(e, "files") and e.files:
        f = e.files[0]
        try:
            if hasattr(f, "content") and f.content is not None:
                return f.content.read()
            if hasattr(f, "file") and f.file is not None:
                return f.file.read()
            if hasattr(f, "read"):
                return f.read()
        except Exception:
            pass

    # args dict fallback
    if hasattr(e, "args") and isinstance(e.args, dict):
        a = e.args

        c = a.get("content")
        if c is not None:
            try:
                return c.read()
            except Exception:
                pass

        f = a.get("file")
        if f is not None:
            try:
                return f.read()
            except Exception:
                pass

        files = a.get("files")
        if isinstance(files, list) and files:
            f = files[0]
            try:
                if hasattr(f, "read"):
                    return f.read()
            except Exception:
                pass

    raise AttributeError("Upload event does not contain file content")



def create_offline_anomaly_tab() -> None:
    """Create the Offline Anomaly detection tab"""

    with ui.column().classes('w-full q-gutter-md'):
        ui.label('Offline Anomaly Detection').classes('text-h6 text-weight-bold')
        ui.label('Analyze existing log files for anomalies').classes(
            'text-body2 text-grey-7'
        )

        # ---------------------------
        # Pattern management section
        # ---------------------------
        with ui.card().classes('w-full q-pa-md') as pattern_card:
            ui.label('Pattern Management').classes(
                'text-subtitle1 text-weight-bold q-mb-sm'
            )
            ui.label(
                'Manage anomaly detection patterns - upload files or edit patterns directly'
            ).classes('text-caption text-grey-7 q-mb-md')

            pattern_status = ui.label(
                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
            ).classes('text-positive')

            with ui.tabs().classes('w-full') as offline_pattern_tabs:
                upload_tab = ui.tab('Upload File', icon='upload_file')
                edit_tab = ui.tab('Edit Patterns', icon='edit')
                export_tab = ui.tab('Export', icon='download')

            # -------------------------------------------------
            # Upload / Edit / Export tab panels
            # -------------------------------------------------
            with ui.tab_panels(offline_pattern_tabs, value=upload_tab).classes('w-full'):
                # ----------------- Upload tab ------------------
                with ui.tab_panel(upload_tab):
                    ui.label('Upload Exception Pattern File').classes(
                        'text-body2 text-weight-bold q-mb-sm'
                    )
                    ui.label(
                        'Upload a .py file containing exception patterns'
                    ).classes('text-caption text-grey-7 q-mb-md')

                    def handle_offline_pattern_upload(e) -> None:
                        try:
                            content = get_uploaded_content(e)
                            temp_path = 'temp_offline_exception_patterns.py'
                            with open(temp_path, 'wb') as f:
                                f.write(content)

                            success, message = ANOMALY_DETECTOR.load_pattern_file(
                                temp_path
                            )
                            if success:
                                pattern_status.text = f'✅ {message}'
                                pattern_status.classes('text-positive')
                                ui.notify(message, type='positive')
                                if 'offline_pattern_table' in locals():
                                    refresh_offline_pattern_table()
                            else:
                                pattern_status.text = f'❌ {message}'
                                pattern_status.classes('text-negative')
                                ui.notify(message, type='negative')

                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                        except Exception as ex:
                            msg = f'⚠️ Error: {str(ex)}'
                            pattern_status.text = msg
                            pattern_status.classes('text-negative')
                            ui.notify(msg, type='negative')

                    ui.upload(
                        label='Upload Exception Pattern .py File',
                        on_upload=handle_offline_pattern_upload,
                        auto_upload=True,
                    ).props('accept=.py').classes('w-full')

                # ----------------- Edit tab --------------------
                with ui.tab_panel(edit_tab):
                    ui.label('Pattern Editor').classes(
                        'text-body2 text-weight-bold q-mb-sm'
                    )
                    ui.label(
                        'Add, edit, or delete anomaly detection patterns'
                    ).classes('text-caption text-grey-7 q-mb-md')

                    # --- Add new pattern section
                    with ui.expansion('Add New Pattern', icon='add').classes(
                        'w-full q-mb-md'
                    ):
                        with ui.row().classes('w-full items-end q-gutter-sm'):
                            offline_new_pattern_input = ui.input(
                                'Regex Pattern',
                                placeholder=r'e.g., ERROR|FAIL|exception',
                            ).classes('flex-grow')
                            offline_new_category_input = ui.input(
                                'Category',
                                placeholder='e.g., ERROR_GENERAL',
                            ).classes('w-48')

                        def offline_add_new_pattern() -> None:
                            pattern = offline_new_pattern_input.value.strip()
                            category = offline_new_category_input.value.strip()
                            if not pattern or not category:
                                ui.notify(
                                    'Both pattern and category are required',
                                    type='warning',
                                )
                                return
                            try:
                                re.compile(pattern, re.IGNORECASE)
                            except re.error as ex:
                                ui.notify(
                                    f'Invalid regex pattern: {str(ex)}',
                                    type='negative',
                                )
                                return

                            ANOMALY_DETECTOR.custom_patterns[pattern] = category
                            ANOMALY_DETECTOR.patterns[pattern] = category
                            ANOMALY_DETECTOR._compile_patterns()  # re-compile

                            offline_new_pattern_input.value = ''
                            offline_new_category_input.value = ''

                            pattern_status.text = (
                                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                            )
                            refresh_offline_pattern_table()
                            ui.notify(
                                f'Added pattern: {pattern} -> {category}',
                                type='positive',
                            )

                        ui.button(
                            'Add Pattern',
                            icon='add',
                            on_click=offline_add_new_pattern,
                        ).props('color=primary')

                    # --- Pattern table definition
                    offline_pattern_columns = [
                        {
                            'name': 'pattern',
                            'label': 'Regex Pattern',
                            'field': 'pattern',
                            'align': 'left',
                        },
                        {
                            'name': 'category',
                            'label': 'Category',
                            'field': 'category',
                            'align': 'left',
                        },
                        {
                            'name': 'type',
                            'label': 'Type',
                            'field': 'type',
                            'align': 'left',
                        },
                        {
                            'name': 'actions',
                            'label': 'Actions',
                            'field': 'pattern',
                            'align': 'left',
                        },
                    ]

                    def get_offline_pattern_rows() -> List[Dict[str, Any]]:
                        rows: List[Dict[str, Any]] = []
                        # defaults
                        for pattern, category in DEFAULT_ANOMALY_PATTERNS.items():
                            rows.append(
                                {
                                    'pattern': pattern,
                                    'category': category,
                                    'type': 'Default',
                                    'is_default': True,
                                }
                            )
                        # customs
                        for pattern, category in ANOMALY_DETECTOR.custom_patterns.items():
                            rows.append(
                                {
                                    'pattern': pattern,
                                    'category': category,
                                    'type': 'Custom',
                                    'is_default': False,
                                }
                            )
                        return rows

                    offline_pattern_table = ui.table(
                        columns=offline_pattern_columns,
                        rows=get_offline_pattern_rows(),
                        row_key='pattern',
                    ).classes('w-full')

                    # slot for edit / delete / copy buttons
                    offline_pattern_table.add_slot('body-cell-actions',r"""
                        <q-td :props="props" auto-width>
                        <q-btn dense flat color="primary" icon="edit"
                                @click.stop.prevent="$parent.$emit('edit-pattern', props.row)"
                                title="Edit Pattern" />
                        <q-btn dense flat color="negative" icon="delete"
                                @click.stop.prevent="$parent.$emit('delete-pattern', props.row)"
                                title="Delete Pattern" />
                        <q-btn v-if="!props.row.is_default" dense flat color="secondary" icon="content_copy"
                                @click.stop.prevent="$parent.$emit('copy-pattern', props.row)"
                                title="Copy to Custom" />
                        </q-td>
                        """)

                    # --- helpers to refresh table
                    def refresh_offline_pattern_table() -> None:
                        offline_pattern_table.rows = get_offline_pattern_rows()
                        offline_pattern_table.update()

                    # --- edit dialog and handlers
                    offline_edit_dialog = ui.dialog()

                    def show_offline_edit_dialog(pattern_data: Dict[str, Any]) -> None:
                        offline_edit_dialog.clear()
                        with offline_edit_dialog:
                            with ui.card().classes('w-96 q-pa-md'):
                                ui.label('Edit Pattern').classes(
                                    'text-h6 text-weight-bold q-mb-md'
                                )
                                edit_pattern_input = ui.input(
                                    'Regex Pattern',
                                    value=pattern_data['pattern'],
                                ).classes('w-full q-mb-sm')
                                edit_category_input = ui.input(
                                    'Category',
                                    value=pattern_data['category'],
                                ).classes('w-full q-mb-md')
                                with ui.row().classes("w-full justify-end q-gutter-sm"):
                                    ui.button("Cancel", on_click=offline_edit_dialog.close).props("flat")
                                    def save_edit() -> None:
                                        old_pattern = pattern_data['pattern']
                                        new_pattern = edit_pattern_input.value.strip()
                                        new_category = edit_category_input.value.strip()
                                        is_default = pattern_data.get('is_default', False)

                                        if not new_pattern or not new_category:
                                            ui.notify(
                                                'Both pattern and category are required',
                                                type='warning',
                                            )
                                            return
                                        try:
                                            re.compile(new_pattern, re.IGNORECASE)
                                        except re.error as ex:
                                            ui.notify(
                                                f'Invalid regex pattern: {str(ex)}',
                                                type='negative',
                                            )
                                            return

                                        if is_default:
                                            # update global default patterns
                                            global DEFAULT_ANOMALY_PATTERNS
                                            DEFAULT_ANOMALY_PATTERNS = dict(
                                                DEFAULT_ANOMALY_PATTERNS
                                            )
                                            if old_pattern in DEFAULT_ANOMALY_PATTERNS:
                                                del DEFAULT_ANOMALY_PATTERNS[old_pattern]
                                            DEFAULT_ANOMALY_PATTERNS[new_pattern] = (
                                                new_category
                                            )
                                        else:
                                            # custom pattern update
                                            if old_pattern in ANOMALY_DETECTOR.custom_patterns:
                                                del ANOMALY_DETECTOR.custom_patterns[
                                                    old_pattern
                                                ]
                                            ANOMALY_DETECTOR.custom_patterns[
                                                new_pattern
                                            ] = new_category

                                        ANOMALY_DETECTOR.patterns = {
                                            **DEFAULT_ANOMALY_PATTERNS,
                                            **ANOMALY_DETECTOR.custom_patterns,
                                        }
                                        ANOMALY_DETECTOR._compile_patterns()
                                        pattern_status.text = (
                                            f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                            f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                            f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                                        )
                                        refresh_offline_pattern_table()
                                        ui.notify(
                                            f'Edited pattern: {new_pattern} -> {new_category}',
                                            type='positive',
                                        )
                                        offline_edit_dialog.close()
                                    ui.button('Save',on_click=save_edit,).props('color=primary')                           
                                    
                        offline_edit_dialog.open()
                    def handle_offline_edit_pattern(e):
                        row_data = e.args if hasattr(e, 'args') else None
                        if row_data:
                            show_offline_edit_dialog(row_data)
                    def handle_offline_delete_pattern(e):
                        row_data = e.args if hasattr(e, 'args') else None
                        if row_data: 
                            pattern = row_data['pattern']
                            is_default = row_data.get('is_default', False)
                            if is_default:
                                global DEFAULT_ANOMALY_PATTERNS
                                DEFAULT_ANOMALY_PATTERNS = dict(DEFAULT_ANOMALY_PATTERNS)
                                if pattern in DEFAULT_ANOMALY_PATTERNS:
                                    del DEFAULT_ANOMALY_PATTERNS[pattern]
                            else:
                                if pattern in ANOMALY_DETECTOR.custom_patterns:
                                    del ANOMALY_DETECTOR.custom_patterns[pattern]
                                if pattern in ANOMALY_DETECTOR.patterns:
                                    del ANOMALY_DETECTOR.patterns[pattern]
                                ui.notify(f'Deleted pattern: {pattern}', type='positive')
                            ANOMALY_DETECTOR._compile_patterns()
                            pattern_status.text = (
                                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                            )
                            refresh_offline_pattern_table()                        
                    def handle_offline_copy_pattern(e) -> None:
                        row_data = e.args if hasattr(e, 'args') else None
                        if row_data:
                            pattern = row_data['pattern']
                            category = row_data['category']
                            ANOMALY_DETECTOR.custom_patterns[pattern] = category
                            ANOMALY_DETECTOR.patterns[pattern] = category
                            ANOMALY_DETECTOR._compile_patterns()
                            pattern_status.text = (
                                f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                                f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                                f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                            )
                            refresh_offline_pattern_table()
                            ui.notify(
                                f'Copied pattern to custom: {pattern}', type='positive'
                            )

                    offline_pattern_table.on('edit-pattern', handle_offline_edit_pattern)
                    offline_pattern_table.on('delete-pattern', handle_offline_delete_pattern)
                    offline_pattern_table.on('copy-pattern', handle_offline_copy_pattern)

                # ----------------- Export tab ------------------
                with ui.tab_panel(export_tab):
                    ui.label("Export Patterns").classes("text-body2 text-weight-bold q-mb-sm")
                    ui.label("Export current patterns to a Python file").classes("text-caption text-grey-7 q-mb-md")
                    def export_patterns():
                        try:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f'exception_patterns_{timestamp}.py'

                            content = (
                                '# Generated on '
                                + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                + '\n\n'
                                'exception_patterns = {\n'
                            )
                            for pattern, category in sorted(
                                ANOMALY_DETECTOR.patterns.items()
                            ):
                                escaped_pattern = (
                                    pattern.replace('\\', '\\\\')
                                    .replace('"', '\\"')
                                    .replace("'", "\\'")
                                )
                                content += (
                                    f"    r'{escaped_pattern}': '{category}',\n"
                                )
                            content += '}\n'

                            ui.download(
                                content.encode('utf-8'), filename=filename
                            )
                            ui.notify(
                                f'Exported {len(ANOMALY_DETECTOR.patterns)} '
                                f'patterns to {filename}',
                                type='positive',
                            )
                        except Exception as e:
                            ui.notify(
                                f'Export failed: {str(e)}', type='negative'
                            )
                    def export_custom_only():
                        try:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f'custom_patterns_{timestamp}.py'

                            content = (
                                '# Generated on '
                                + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                + '\n\n'
                                'exception_patterns = {\n'
                            )
                            for pattern, category in sorted(
                                ANOMALY_DETECTOR.custom_patterns.items()
                            ):
                                escaped_pattern = (
                                    pattern.replace('\\', '\\\\')
                                    .replace('"', '\\"')
                                    .replace("'", "\\'")
                                )
                                content += (
                                    f"    r'{escaped_pattern}': '{category}',\n"
                                )
                            content += '}\n'

                            ui.download(
                                content.encode('utf-8'), filename=filename
                            )
                            ui.notify(
                                f'Exported {len(ANOMALY_DETECTOR.custom_patterns)} '
                                f'custom patterns to {filename}',
                                type='positive',
                            )
                        except Exception as e:
                            ui.notify(
                                f'Export failed: {str(e)}', type='negative'
                            )

                    with ui.row().classes('q-gutter-sm'):
                        ui.button(
                            'Export All Patterns',
                            icon='download',
                            on_click=export_patterns,
                        ).props('color=primary')
                        ui.button(
                            'Export Custom Only',
                            icon='download',
                            on_click=export_custom_only,
                        ).props('outline')

                    ui.separator().classes('q-my-md')

                    ui.label('Reset Patterns').classes(
                        'text-body2 text-weight-bold q-mb-sm'
                    )
                    ui.label('Reset patterns to default state').classes(
                        'text-caption text-grey-7 q-mb-md'
                    )

                    def reset_to_defaults() -> None:
                        ANOMALY_DETECTOR.custom_patterns.clear()
                        ANOMALY_DETECTOR.patterns = DEFAULT_ANOMALY_PATTERNS.copy()
                        ANOMALY_DETECTOR._compile_patterns()
                        pattern_status.text = (
                            f"Using {len(ANOMALY_DETECTOR.patterns)} patterns "
                            f"({len(DEFAULT_ANOMALY_PATTERNS)} default + "
                            f"{len(ANOMALY_DETECTOR.custom_patterns)} custom)"
                        )
                        refresh_offline_pattern_table()
                        ui.notify(
                            'Reset to default patterns', type='positive'
                        )

                    ui.button(
                        'Reset to Defaults',
                        icon='restore',
                        on_click=reset_to_defaults,
                    ).props('color=negative outline')

        # -------------------------------------------------
        # Folder selection and offline analysis
        # -------------------------------------------------
        with ui.card().classes('w-full q-pa-md'):
            ui.label('Log Folder Selection').classes(
                'text-subtitle1 text-weight-bold q-mb-sm'
            )
            ui.label(
                'Enter the path to a folder containing device log files, '
                'e.g., C:/logs or /var/log/devices'
            ).classes('text-caption text-grey-7 q-mb-md')

            folder_input = ui.input(
                'Folder Path', placeholder='C:/logs or /var/log/devices'
            ).classes('w-full')

            progress_container = ui.column().classes('w-full')

            # track analysis state
            analysis_state = {'running': False, 'should_abort': False}

            def analyze_folder():
                folder_path = folder_input.value
                if not folder_path or not os.path.exists(folder_path):
                    ui.notify(
                        'Please enter a valid folder path', type='warning'
                    )
                    return

                progress_container.clear()
                with progress_container:
                    progress = ui.linear_progress(0.0).props(
                        'color=primary'
                    ).classes('w-full')
                    progress_label = ui.label(
                        'Scanning for log files...'
                    ).classes('text-caption')

                # find all log files recursively
                log_files: List[str] = []
                for root, dirs, files in os.walk(folder_path):
                    for f in files:
                        if f.lower().endswith(('.log', '.txt', '.out')):
                            log_files.append(os.path.join(root, f))

                if not log_files:
                    progress_container.clear()
                    ui.notify(
                        'No log files found in the specified folder',
                        type='warning',
                    )
                    return

                progress_label.text = (
                    f'Found {len(log_files)} log files. '
                    'Analyzing in parallel...'
                )

                # set analysis state
                analysis_state['running'] = True
                analysis_state['should_abort'] = False
                async def analyze_async():
                    """Async worker for offline log analysis"""
                    import asyncio
                    import concurrent.futures
                    loop = asyncio.get_running_loop()   
                    # helper for single file
                    def _analyze_file(log_file: str):
                        if analysis_state['should_abort']:
                            return []

                        import time as _time
                        start_time = _time.time()
                        try:
                            # network path check (for perf message)
                            is_network_path = log_file.startswith('\\\\') or log_file.startswith('//')

                            size_start = _time.time()
                            file_size = os.path.getsize(log_file)
                            size_time = _time.time() - size_start

                            file_info = (
                                f"Analyzing {log_file} (file_size = {file_size / 1024 / 1024:.1f} MB)"
                            )
                            print(file_info)

                            # STREAMING read + analysis in one pass
                            analyze_start = _time.time()
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                if analysis_state['should_abort']:
                                    print(f"Aborted before analyzing {os.path.basename(log_file)}")
                                    return [], None, None

                                # use streaming line iterator
                                anomalies = ANOMALY_DETECTOR._detect_from_lines(f)
                            analyze_time = _time.time() - analyze_start
                            read_time = 0.0  # merged into analyze_time

                            for anomaly in anomalies:
                                anomaly['file'] = os.path.basename(log_file)
                                anomaly['full_path'] = log_file
                                anomaly['device'] = extract_device_name(log_file)

                            total_time = _time.time() - start_time
                            perf_info = None
                            if total_time > 5:
                                net = '[NETWORK]' if is_network_path else '[LOCAL]'
                                perf_info = (
                                    f"{net} {os.path.basename(log_file)} "
                                    f"(file_size {file_size / 1024 / 1024:.1f} MB) "
                                    f"total={total_time:.2f}s, analyze={analyze_time:.2f}s"
                                )
                                print(perf_info)

                            return anomalies, file_info, perf_info
                        except Exception as e:
                            elapsed = time.time() - start_time
                            error_msg = f"Error analyzing {log_file} after {elapsed:.2f}s: {e}"
                            print(error_msg)
                            return [], None, error_msg
                            

                    # ------------- concurrent execution setup -------------
                    cpu_count = os.cpu_count() or 2
                    max_workers = min(cpu_count * 3, len(log_files), 16)
                    completed = 0
                    all_anomalies: List[Dict[str, Any]] = []
                    batch_size = 5  # reduced for more frequent UI updates

                    client_disconnected = False
                    last_successful_update = 0
                    perf_msg = None

                    loop = asyncio.get_running_loop()

                    try:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                            pending_tasks= []
                            file_index = 0

                            # initial batch submission
                            initial_batch = min(max_workers * 2, len(log_files))
                            for _ in range(initial_batch):
                                if not analysis_state['should_abort'] and file_index < len(log_files):
                                    task = loop.run_in_executor(ex, _analyze_file, log_files[file_index])
                                    pending_tasks.append(task)
                                    file_index += 1

                            while pending_tasks:
                                done, pending_tasks = await asyncio.wait(
                                    pending_tasks,
                                    return_when=asyncio.FIRST_COMPLETED,
                                    #timeout=60.0
                                )

                                # process completed tasks
                                for task in done:
                                    file_msg = None
                                    perf_msg = None
                                    try:
                                        result = await task
                                        if isinstance(result, tuple) and len(result) == 3:
                                            anomalies_list, file_msg, perf_msg = result
                                            all_anomalies.extend(anomalies_list)
                                        else:
                                            all_anomalies.extend(result or [])
                                    except asyncio.TimeoutError:
                                        print(f'Timeout analyzing file at position {completed}')
                                    except Exception as ex:
                                        print(f'Error in task: {ex}')

                                    completed += 1

                                # submit next file
                                if not analysis_state['should_abort'] and file_index < len(log_files):
                                    task = loop.run_in_executor(ex, _analyze_file, log_files[file_index])
                                    pending_tasks.append(task)
                                    file_index += 1
                                elif analysis_state['should_abort'] and file_index < len(
                                    log_files
                                ):
                                    print(
                                        f'Abort: stopping at {completed}/{len(log_files)} files, '
                                        f'{len(pending_tasks)} tasks still running'
                                    )

                                # -------- progress / status update per file --------
                                try:
                                    if hasattr(progress, 'client') and hasattr(
                                        progress.client, 'has_socket_connection'
                                    ):
                                        if progress.client.has_socket_connection:
                                            new_value = completed / len(log_files)
                                            progress.value = new_value
                                            progress.update()

                                            current_msg = (
                                                f'Analyzed {completed}/{len(log_files)} files '
                                                f'({len(all_anomalies)} anomalies)'
                                            )
                                            if perf_msg:
                                                current_msg = perf_msg
                                            progress_label.text = current_msg
                                            last_successful_update = completed
                                            await asyncio.sleep(0)
                                        else:
                                            if not client_disconnected:
                                                print(
                                                    f'Client disconnected at '
                                                    f'{completed}/{len(log_files)} files '
                                                    f'- continuing analysis in background'
                                                )
                                                client_disconnected = True
                                    else:
                                        if not client_disconnected:
                                            print(
                                                'Client object not available, assume '
                                                f'disconnected at {completed}/{len(log_files)} '
                                                'files - continuing analysis in background'
                                            )
                                            client_disconnected = True
                                except (RuntimeError, AttributeError):
                                    if not client_disconnected:
                                        print(
                                            f'Client disconnected at {completed}/{len(log_files)} '
                                            'files - continuing analysis in background'
                                        )
                                        client_disconnected = True
                    except Exception as ex:
                        print(f'Error in analysis loop: {ex}')

                    finally:
                        # mark analysis as complete
                        analysis_state['running'] = False
                        if client_disconnected:
                            print(
                                f"Analysis completed in background: "
                                f"{len(all_anomalies)} anomalies found in "
                                f"{completed}/{len(log_files)} files"
                            )
                            print(
                                f"Last successful UI update was at "
                                f"{last_successful_update}/{len(log_files)} files"
                            )
                        if analysis_state['should_abort']:
                            print(f"Analysis aborted: Processed {completed} /{len(all_anomalies)} files, found {len(all_anomalies)} anomalies")

                    # always show results, even if client disconnected / aborted
                    try:
                        if progress.client.has_socket_connection:
                            progress.value = 1.0
                            progress.update()
                            await asyncio.sleep(0)

                        with progress_container:
                            progress_container.clear()
                        with results_container:
                            display_offline_results(all_anomalies, results_container)

                            # save anomalies JSON (helper assumed existing)
                            save_path = save_anomalies_to_json(all_anomalies)
                            try:
                                with open(save_path, 'rb') as fh:
                                    ui.download(fh.read(), filename=os.path.basename(save_path))
                            except Exception:
                                pass

                            status_msg = (
                                f'Analysis complete. Found {len(all_anomalies)} anomalies in '
                                f'{completed}/{len(log_files)} files. Saved: {save_path}'
                            )
                            if analysis_state.get('should_abort'):
                                status_msg = (
                                    f'Analysis stopped. Found {len(all_anomalies)} anomalies in '
                                    f'{completed}/{len(log_files)} files. Saved: {save_path}'
                                )
                            ui.notify(status_msg, type='positive' if not analysis_state.get(
                                'should_abort'
                            ) else 'warning')
                    except (RuntimeError, AttributeError):
                        # client is gone; just save results
                        print(
                            f'Client disconnected. Analysis completed: '
                            f'{len(all_anomalies)} anomalies found in {completed} files'
                        )
                        save_anomalies_to_json(all_anomalies)
                # kick off async analysis
                import asyncio as _asyncio
                _asyncio.create_task(analyze_async())

            def abort_analysis():
                if analysis_state['running']:
                    analysis_state['should_abort'] = True
                    ui.notify(
                        'Aborting analysis...', type='info'
                    )
                else:
                    ui.notify(
                        'No analysis is currently running', type='warning'
                    )

            with ui.row().classes('q-gutter-sm q-mt-md'):
                ui.button(
                    'Analyze Folder',
                    on_click=analyze_folder,
                    icon='search',
                ).props('color=primary')
                ui.button(
                    'Abort Analysis',
                    on_click=abort_analysis,
                    icon='stop',
                ).props('color=negative outline')

        # results container (shared)
        results_container = ui.column().classes('w-full')
    
    # end of create_offline_anomaly_tab
    


def extract_device_name(file_path: str) -> str:
    """Extract device name from file path."""
    basename = os.path.basename(file_path)
    name = os.path.splitext(basename)[0]
    return name



def save_anomalies_to_json(anomalies: List[Dict[str, Any]]) -> str:
    """Save anomalies to a JSON file on disk and return the path."""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Ensure logs directory exists
        #out_dir = os.path.join('logs')
        out_dir = "C:/Amomaly_logs"
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            # fallback to current directory
            out_dir = '.'

        filename = f'offline_anomalies_{timestamp}.json'
        path = os.path.join(out_dir, filename)
        with open(path, 'w', encoding='utf-8') as out:
            json.dump(anomalies, out, indent=2)
        return os.path.abspath(path)
    except Exception as e:
        # If saving fails, return a placeholder path
        return f"save_failed: {e}"

# ---------------------------------------------------------
# MAIN PAGE
# ---------------------------------------------------------


