from nicegui import ui

from anomaly_detector_core.ui_main import create_main_ui


@ui.page('/')
def index():
    create_main_ui()


if __name__ == '__main__':
    ui.run(
        title='Anomaly Detection Tool',
        reload=False,
        show=False,
        port=8080,
        favicon=None,
        binding_refresh_interval=0.5,
        reconnect_timeout=300.0,
    )
