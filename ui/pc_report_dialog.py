import ctypes
import datetime
import os
import subprocess
import sys
import threading

from PyQt5.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QThread,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pc_report.orchestrator import run_all
from pc_report.privacy import redact_user_paths
from pc_report.render_html import render as render_html
from pc_report.render_json import render as render_json
from pc_report.section import esc
from ui import theme
from ui.glyph_icons import set_link_glyph
from ui.tab_header import TabHeader
from utils.file_naming import get_unique_path
from utils.logger import logger


def _tr(source: str) -> str:
    """Translate this module's strings under the stable "PcReport" context.

    The argument must always be a plain string literal -- never an f-string or
    a variable. See utils/localization.py for why.
    """
    return QCoreApplication.translate("PcReport", source)


class _PCReportWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, str)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.options = options
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            html, json_text = self._generate()
        except Exception as exc:
            logger.exception("PC report failed")
            message = str(exc)
            if self.options.get('redact', True):
                message = redact_user_paths(message)
            self.progress.emit(f"[error] PC report failed: {message}")
            html = ("<!doctype html><html><head><meta charset='utf-8'></head><body>"
                    f"<h1>PC Report Failed</h1><p>{esc(message)}</p></body></html>")
            json_text = ''
        self.finished.emit(html, json_text)

    def _generate(self):
        redact = self.options.get('redact', True)
        include_json = self.options.get('include_json', False)
        # Run modular collectors via orchestrator
        meta, data, errors = run_all(
            self.options,
            progress_cb=lambda title, completed, total: self.progress.emit(f"{title} ({completed}/{total})"),
            cancel=self.cancel_event,
        )
        for name, err in errors.items():
            self.progress.emit(f"[warn] {name}: {err}")
        self.progress.emit('Rendering HTML...')
        meta['redacted'] = redact
        html = render_html(meta, data, {'redact': redact})
        json_text = render_json(meta, data, {'redact': redact}) if include_json else ''
        return html, json_text


class PCReportWidget(QWidget):
    """Embedded PC report generator for the main-window tab."""

    def __init__(self, parent=None, button_style=None, converting=False, locked=False):
        super().__init__(parent)
        self.button_style = button_style
        self.converting = converting
        self.locked = locked
        self.html = ''
        self.json_text = ''
        self.report_path = ''
        self.worker = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # The shared tab header: a monitor glyph, title, description. The heart
        # sits under the glyph's screen and pulses while a report runs
        # (restored from the pre-343d9c1 dialog).
        self.header = TabHeader(
            "pc",
            _tr("PC Report"),
            _tr("Collects system details for support. Redaction is always on."),
        )
        self.heart_label = QLabel()
        self.heart_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.heart_label.setAlignment(Qt.AlignCenter)
        self.heart_effect = QGraphicsOpacityEffect(self.heart_label)
        self.heart_effect.setOpacity(0.0)
        self.heart_label.setGraphicsEffect(self.heart_effect)
        self.heart_label.hide()
        self.heart_anim = None
        self.header.add_layer_under_glyph(self.heart_label)
        self.logo_label = self.header.glyph_label
        self.logo_width = TabHeader.GLYPH_PX
        self._set_logo()
        layout.addWidget(self.header)

        actions = QHBoxLayout()
        actions.setSpacing(14)
        self.btn_run = QPushButton(_tr("Generate PC Report"))
        self.btn_open = QPushButton(_tr("Open report"))
        self.btn_folder = QPushButton(_tr("Open folder"))
        self.btn_admin = QPushButton(_tr("Run as administrator"))
        self.btn_admin.setToolTip(
            _tr(
                "Restart NVC with administrator rights so the report can read TPM, BitLocker, "
                "disk reliability and SMB server details."
            )
        )
        for button in (self.btn_run, self.btn_open, self.btn_folder, self.btn_admin):
            button.setCursor(Qt.PointingHandCursor)
            theme.opt_out_of_button_style(button)
        self.btn_open.setEnabled(False)
        self.btn_folder.setEnabled(False)
        self.btn_admin.setVisible(not self.is_elevated())
        actions.addWidget(self.btn_run)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_folder)
        actions.addStretch(1)
        actions.addWidget(self.btn_admin)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        self._set_progress_color(theme.skin_for_state(locked=locked, active=converting).accent)
        layout.addWidget(self.progress)

        self.status_label = QLabel(_tr("Ready. Reports are saved to your Desktop by default."))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(theme.qss("color: $grey_700; font-size: 9pt;"))
        layout.addWidget(self.status_label)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.output.setPlaceholderText(_tr("Report progress appears here."))
        layout.addWidget(self.output, 1)

        self._apply_tier_styles()
        self.btn_run.clicked.connect(self.on_run)
        self.btn_open.clicked.connect(self.open_report)
        self.btn_folder.clicked.connect(self.open_report_folder)
        self.btn_admin.clicked.connect(self.relaunch_elevated)

    def _set_logo(self):
        """Paint the monitor glyph for the current state and size the heart to sit in its screen."""
        accent = theme.skin_for_state(locked=self.locked, active=self.converting).accent
        self.header.reskin(accent)
        try:
            from PyQt5.QtGui import QPixmap

            from utils.resources import resource_path
            heart = "graphics/GREENPCREPORTHEART.png" if self.converting else "graphics/PCREPORTHEART.png"
            path = resource_path(heart)
            if os.path.exists(path):
                # The heart canvas is the old logo's canvas, so scaled to the glyph
                # size the heart lands where the monitor's screen is.
                self.heart_label.setPixmap(
                    QPixmap(path).scaledToWidth(self.logo_width, Qt.SmoothTransformation)
                )
        except Exception:
            logger.debug("PCReportWidget._set_logo: suppressed error", exc_info=True)

    _LINK_GLYPHS = {"btn_open": "report", "btn_folder": "folder_open", "btn_admin": "shield"}

    def _apply_tier_styles(self):
        self.btn_run.setStyleSheet(theme.compact_button_style())
        accent = theme.skin_for_state(locked=self.locked, active=self.converting).accent
        for attr, glyph in self._LINK_GLYPHS.items():
            link = getattr(self, attr)
            link.setStyleSheet(theme.link_button_style())
            set_link_glyph(link, glyph, accent)

    def apply_layout_mode(self, metrics):
        # The header glyph has one size in both modes (metrics.pc_report_logo_w
        # is no longer applied); the heart keeps in step with it.
        self._set_logo()

    @staticmethod
    def is_elevated():
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def _relaunch_command():
        """(exe, params) that start this same NVC again, frozen or from source."""
        if getattr(sys, "frozen", False):
            return sys.executable, subprocess.list2cmdline(sys.argv[1:])
        return sys.executable, subprocess.list2cmdline(sys.argv)

    def _window_is_busy(self):
        window = self.window()
        if getattr(window, "running", False) or getattr(window, "is_converting", False):
            return True
        recording = getattr(window, "is_recorder_recording", None)
        return bool(callable(recording) and recording())

    def relaunch_elevated(self):
        """Ask UAC to start a second NVC as administrator, then quit this one.

        main.py keeps a QSharedMemory segment as the single-instance guard; it is
        released before the child starts so the elevated copy is not turned away
        with "NVC is already running", and re-created if UAC is refused.
        """
        if self._window_is_busy():
            self.status_label.setText(
                _tr("Stop the current conversion or recording before restarting as administrator.")
            )
            return
        app = QCoreApplication.instance()
        guard = getattr(app, "single_instance_memory", None)
        try:
            exe, params = self._relaunch_command()
            if guard is not None:
                guard.detach()
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, params, None, 1
            )
        except Exception:
            logger.debug(
                "PCReportWidget.relaunch_elevated: suppressed error", exc_info=True
            )
            result = 0
        if result > 32:
            window = self.window()
            quit_fn = getattr(window, "quit_application", None)
            if callable(quit_fn):
                quit_fn()
        else:
            if guard is not None:
                guard.create(1)
            self.status_label.setText(
                _tr(
                    "Elevation was cancelled or refused; the report will run without "
                    "administrator rights."
                )
            )

    def _set_progress_color(self, hex_color: str):
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                border-radius: 3px;
                text-align: center;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {hex_color};
                border-radius: 2px;
                margin: 0px;
            }}
            """
        )

    def default_report_path(self):
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.isdir(desktop):
            desktop = os.path.expanduser('~')
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return get_unique_path(os.path.join(desktop, f'PC_Report_{stamp}.html'))

    def _options(self):
        return {
            'updates': True,
            'programs': True,
            'security': True,
            'redact': True,
            'include_json': False,
            'drivers': True,
            'services': True,
            'processes': True,
            'shares': True,
            'licenses': True,
        }

    def on_run(self):
        if self.worker and self.worker.isRunning():
            return
        self.report_path = self.default_report_path()
        self.html = ''
        self.json_text = ''
        self.btn_run.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_folder.setEnabled(False)
        self.progress.show()
        self._start_heart()
        self.status_label.setText(_tr("Generating PC report inside this tab..."))
        self.output.clear()
        self.output.appendPlainText(f"Report will be saved to: {self.report_path}")
        self.worker = _PCReportWorker(self._options(), self)
        self.worker.progress.connect(self.output.appendPlainText)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _start_heart(self):
        self.heart_label.show()
        if self.heart_anim is not None:
            self.heart_anim.stop()
        anim = QPropertyAnimation(self.heart_effect, b"opacity", self)
        anim.setDuration(2400)
        anim.setKeyValueAt(0.0, 0.2)
        anim.setKeyValueAt(0.5, 1.0)
        anim.setKeyValueAt(1.0, 0.2)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setLoopCount(-1)
        anim.start()
        self.heart_anim = anim

    def _settle_heart(self, success):
        if self.heart_anim is not None:
            self.heart_anim.stop()
        if success:
            self.heart_effect.setOpacity(1.0)
        else:
            self.heart_effect.setOpacity(0.0)
            self.heart_label.hide()

    def _on_worker_finished(self, html, json_text):
        self.progress.hide()
        # The worker reports failure as a stub page with empty JSON.
        self._settle_heart(success=bool(json_text))
        self.btn_run.setEnabled(True)
        self.html = html
        self.json_text = json_text
        try:
            with open(self.report_path, 'w', encoding='utf-8') as f:
                f.write(html)
            if json_text:
                json_path = os.path.splitext(self.report_path)[0] + '.json'
                with open(json_path, 'w', encoding='utf-8') as jf:
                    jf.write(json_text)
            self.status_label.setText(_tr("PC report complete: %(path)s")
                                  % {"path": self.report_path})
            self.output.appendPlainText("")
            self.output.appendPlainText(f"Saved: {self.report_path}")
            self.btn_open.setEnabled(True)
            self.btn_folder.setEnabled(True)
        except Exception as exc:
            self.status_label.setText(_tr("PC report generated, but saving failed."))
            self.output.appendPlainText(f"Failed to save: {exc}")

    def open_report(self):
        if self.report_path and os.path.exists(self.report_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.report_path))

    def open_report_folder(self):
        if self.report_path:
            folder = os.path.dirname(self.report_path)
            if os.path.isdir(folder):
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def update_button_style(self, button_style=None, converting=False, locked=False):
        self.button_style = button_style or self.button_style
        self.converting = converting
        self.locked = locked
        self._set_logo()
        self._apply_tier_styles()
        self._set_progress_color(theme.skin_for_state(locked=locked, active=converting).accent)

    def shutdown(self):
        worker = self.worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.requestInterruption()
            worker.wait(5000)
