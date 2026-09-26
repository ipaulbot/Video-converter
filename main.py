#!/usr/bin/env python3
import logging
import os
import sys

from PyQt5.QtCore import QCoreApplication, QSharedMemory, QSystemSemaphore, Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox

from ui.command_server import CommandServer, send_command
from ui.main_window import VideoConverterApp
from ui.media_player_support import prefer_windows_media_foundation
from utils.command_line import HelpRequested, ParseError, parse_command_switches, startup_action
from utils.localization import initialize_localization
from utils.logger import logger
from utils.resources import resource_path
from utils.retention import process_pending_deletions


def _tr(source: str) -> str:
    """Translate this module's strings under the stable "Startup" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("Startup", source)

logging.basicConfig(level=logging.INFO)

def main():
    # Qt's DirectShow backend cannot demux MP4/MOV/MKV on stock Windows 10; Media
    # Foundation can. Decide before any QMediaPlayer exists (the plugin is chosen once).
    prefer_windows_media_foundation()
    app = QApplication(sys.argv)

    # Install the saved language before anything builds a widget: NVC's widgets
    # set their text once at construction, so a translator installed later
    # would only affect strings created after it.
    app.language_manager = initialize_localization(app)

    # MRCmd-style switches (/E /R /S /X /C= /B=), see utils/command_line.py.
    try:
        request = parse_command_switches(sys.argv[1:])
    except HelpRequested as help_text:
        print(help_text)
        QMessageBox.information(None, _tr('NVC'), str(help_text))
        sys.exit(0)
    except ParseError as error:
        print(error, file=sys.stderr)
        QMessageBox.warning(None, _tr('NVC'), str(error))
        sys.exit(2)

    # Single-instance guard
    semaphore = QSystemSemaphore('NVC_Semaphore', 1)
    semaphore.acquire()
    shared = QSharedMemory('NVC_SingleInstance')
    already_running = False
    if shared.attach():
        already_running = True
    else:
        shared.create(1)
    semaphore.release()
    # The PC Report tab releases this before relaunching NVC as administrator.
    app.single_instance_memory = shared
    action = startup_action(request, already_running)
    if action == "send":
        # Hand the switches to the running NVC; this process is just the messenger.
        ok, message = send_command(request)
        print(message, file=sys.stdout if ok else sys.stderr)
        logger.info("command-line request %s -> %s: %s", request, "ok" if ok else "error", message)
        sys.exit(0 if ok else 1)
    if action == "nothing":
        # /S or /X with no NVC running: nothing to stop or close.
        print("NVC is not running.")
        sys.exit(0)
    if already_running:
        # Themed single-instance dialog using INFO icon and app icon
        try:
            icon_path = resource_path('graphics/INFO.ico')
            pm = QPixmap(icon_path) if os.path.exists(icon_path) else None
            msg = QMessageBox()
            msg.setWindowTitle(_tr('NVC'))
            # Apply title/icon for dialog
            try:
                app_icon = resource_path('graphics/TEALNVCLOGO.ico')
                if os.path.exists(app_icon):
                    msg.setWindowIcon(QIcon(app_icon))
            except Exception:
                logger.debug("main: suppressed error", exc_info=True)
            if pm:
                msg.setIconPixmap(pm.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                msg.setIcon(QMessageBox.Information)
            msg.setText(_tr('NVC is already running.'))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        except Exception:
            QMessageBox.information(None, _tr('NVC'), _tr('NVC is already running.'))
        sys.exit(0)
    # Check for required resource files using absolute paths.
    required_files = [
        'ffmpeg.exe',
        'ffprobe.exe',
        'graphics/NVCLOGO.ico',
        'graphics/TEALNVCLOGO.ico',
        'graphics/GRAYSCALELOCK.ico',
        'graphics/UNLOCK.ico',
        'graphics/BROOM.ico',
        'graphics/GRAYSCALEBROOM.ico',
        'graphics/GRAYSCALEBURGER.ico',
        'graphics/INFO.ico',
        'graphics/HELP.ico',
        'graphics/GEAR.ico',
    ]
    missing_files = [f for f in required_files if not os.path.exists(resource_path(f))]
    if missing_files:
        QMessageBox.critical(
            None,
            _tr("Missing Resources"),
            "The following required files are missing:\n" + "\n".join(missing_files)
        )
        sys.exit(1)

    window = VideoConverterApp()
    # Process any overdue pending deletions from previous sessions
    try:
        process_pending_deletions(log_cb=lambda m: None)
    except Exception:
        # Overdue files the user scheduled for deletion stay on disk.
        logger.exception("Could not process pending deletions from a previous session.")
    window.show()
    # Listen for `NVC.exe /R` and friends for as long as this instance runs.
    app.command_server = CommandServer(window.run_command_request, parent=app)
    app.command_server.start()
    if request.has_commands():
        # Applied once the window is up and the event loop has had a moment to
        # restore the saved recorder settings.
        window._schedule(1000, lambda: window.run_command_request(request))
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
