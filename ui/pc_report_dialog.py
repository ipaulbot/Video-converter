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
    QGridLayout,
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

        header = QHBoxLayout()
        header.setSpacing(14)
        # The heart sits under the monitor logo's transparent cut-out and pulses
        # while a report runs (restored from the pre-343d9c1 dialog).
        logo_stack = QGridLayout()
        logo_stack.setContentsMargins(0, 0, 0, 0)
        self.heart_label = QLabel()
        self.heart_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.heart_label.setAlignment(Qt.AlignCenter)
        self.heart_effect = QGraphicsOpacityEffect(self.heart_label)
        self.heart_effect.setOpacity(0.0)
        self.heart_label.setGraphicsEffect(self.heart_effect)
        self.heart_label.hide()
        self.heart_anim = None
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        logo_stack.addWidget(self.heart_label, 0, 0, Qt.AlignCenter)
        logo_stack.addWidget(self.logo_label, 0, 0, Qt.AlignCenter)
        self.logo_width = theme.metrics().pc_report_logo_w
        self._set_logo()
        header.addLayout(logo_stack, 0)

        intro = QVBoxLayout()
        intro.setSpacing(2)
        title = QLabel(_tr("PC Report"))
        title.setStyleSheet(theme.tab_title_style())
        intro.addWidget(title)
        description = QLabel(_tr("Collects system details for support. Redaction is always on."))
        description.setStyleSheet(theme.qss("color: $text_body; font-size: 9pt;"))
        intro.addWidget(description)

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
        intro.addLayout(actions)
        header.addLayout(intro, 1)
        layout.addLayout(header)

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
        try:
            from PyQt5.QtGui import QPixmap

            from utils.resources import resource_path
            if self.locked:
                logo, heart = "graphics/GRAYSCALEPCREPORT.png", "graphics/PCREPORTHEART.png"
            elif self.converting:
                logo, heart = "graphics/GREENPCREPORT.png", "graphics/GREENPCREPORTHEART.png"
            else:
                logo, heart = "graphics/PCREPORT.png", "graphics/PCREPORTHEART.png"
            for label, rel in ((self.logo_label, logo), (self.heart_label, heart)):
                path = resource_path(rel)
                if os.path.exists(path):
                    label.setPixmap(
                        QPixmap(path).scaledToWidth(self.logo_width, Qt.SmoothTransformation)
                    )
        except Exception:
            logger.debug("PCReportWidget._set_logo: suppressed error", exc_info=True)

    def _apply_tier_styles(self):
        self.btn_run.setStyleSheet(theme.compact_button_style())
        for link in (self.btn_open, self.btn_folder, self.btn_admin):
            link.setStyleSheet(theme.link_button_style())

    def apply_layout_mode(self, metrics):
        self.logo_width = metrics.pc_report_logo_w
        self._set_logo()

    @staticmethod
    def is_elevated():
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def relaunch_elevated(self):
        """Ask UAC to start a second NVC as administrator, then quit this one."""
        try:
            if getattr(sys, "frozen", False):
                exe, params = sys.executable, ""
            else:
                exe, params = sys.executable, subprocess.list2cmdline(sys.argv)
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
        self._settle_heart(success=True)
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
