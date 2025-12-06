from __future__ import annotations

from nicegui import ui

from .ui_live import create_live_anomaly_tab
from .ui_offline import create_offline_anomaly_tab


def create_anomaly_page():
    """Create the anomaly detection page with two tabs"""

    with ui.row().classes("w-full items-center justify-between q-mb-lg"):
        with ui.column():
            ui.label("Anomaly Detection").classes("text-h4 text-weight-bold")
            ui.label("Detect and analyze anomalies in device logs").classes("text-subtitle1 text-grey-7")

    # Tabs: Live vs Offline
    with ui.tabs().classes("w-full") as tabs:
        offline_tab = ui.tab("Offline Anomaly", icon="folder_open")
        live_tab = ui.tab("Live Anomaly", icon="sensors")
        

    # Tab Panels
    with ui.tab_panels(tabs, value=live_tab).classes("w-full"):
        # ------------------ OFFLINE TAB ------------------
        with ui.tab_panel(offline_tab):
            create_offline_anomaly_tab()

        # ------------------ LIVE TAB ------------------
        with ui.tab_panel(live_tab):
            #create_live_anomaly_tab()

        


def create_main_ui() -> None:
    """Main page that creates the anomaly detection interface"""

    # Add CSS for styling
    ui.add_head_html("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #F5F5F5;
        }
        .header-title {
            font-weight: 700;
            font-size: 1.5rem;
            color: #0ea5e9;
        }
        .text-caption {
            font-size: 0.75rem;
            color: #666;
        }
    </style>
    """)
    # ----------------------
    # Header
    # ----------------------
    with ui.header().classes("q-pa-md bg-white shadow-1"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Anomaly Detection Tool").classes("header-title")

    # ----------------------
    # Create Anomaly Page
    # ----------------------
    create_anomaly_page()

    # ----------------------
    # Footer
    # ----------------------
    with ui.footer().classes("q-pa-sm bg-white shadow-1"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Anomaly Detection Tool - Standalone Version").classes("text-caption")
            ui.label("Powered by NiceGUI").classes("text-caption")

# ---------------------------------------------------------


