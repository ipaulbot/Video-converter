import datetime
import os
import threading

from PyQt5.QtCore import (
    QCoreApplication,
    Qt,
    QThread,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(14)
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.logo_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self._set_logo()
        header.addWidget(self.logo_label, 0)

        intro = QVBoxLayout()
        title = QLabel(_tr("PC Report"))
        title.setStyleSheet(theme.qss("font-size: 18px; font-weight: bold; color: $accent;"))
        intro.addWidget(title)
        description = QLabel(
            _tr("Generate a detailed support report without leaving this tab. "
            "The report is saved automatically, with redaction enabled for sensitive values.")
        )
        description.setWordWrap(True)
        description.setStyleSheet(theme.qss("color: $text_body; font-size: 10pt;"))
        intro.addWidget(description)
        header.addLayout(intro, 1)
        layout.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.btn_run = QPushButton(_tr("Generate PC Report"))
        self.btn_open = QPushButton(_tr("Open Report"))
        self.btn_folder = QPushButton(_tr("Open Folder"))
        for button in (self.btn_run, self.btn_open, self.btn_folder):
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumWidth(120)
            button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            if button_style:
                button.setStyleSheet(button_style)
        self.btn_open.setEnabled(False)
        self.btn_folder.setEnabled(False)
        controls.addWidget(self.btn_run)
        controls.addWidget(self.btn_open)
        controls.addWidget(self.btn_folder)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self._set_progress_color(
            theme.skin_for_state(locked=locked, active=converting).accent)
        layout.addWidget(self.progress)

        self.status_label = QLabel(_tr("Ready. Reports are saved to your Desktop by default."))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(theme.qss("color: $grey_700;"))
        layout.addWidget(self.status_label)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        except Exception:
            logger.debug("PCReportWidget.__init__: suppressed error", exc_info=True)
        self.output.setPlainText(
            "Press Generate PC Report to collect OS, hardware, driver, codec, NVC dependency, "
            "network, service, process, and security details. The app stays usable while the report runs."
        )
        layout.addWidget(self.output, 1)

        note = QLabel(
            _tr("Tip: the generated HTML is self-contained, so it can be attached to support tickets or opened later.")
        )
        note.setWordWrap(True)
        note.setStyleSheet(theme.qss("color: $grey_650; font-size: 9pt;"))
        layout.addWidget(note)

        self.btn_run.clicked.connect(self.on_run)
        self.btn_open.clicked.connect(self.open_report)
        self.btn_folder.clicked.connect(self.open_report_folder)

    def _set_logo(self):
        try:
            from PyQt5.QtGui import QPixmap

            from utils.resources import resource_path
            if self.locked:
                logo_path = resource_path('graphics/GRAYSCALEPCREPORT.png')
            elif self.converting:
                logo_path = resource_path('graphics/GREENPCREPORT.png')
            else:
                logo_path = resource_path('graphics/PCREPORT.png')
            if os.path.exists(logo_path):
                self.logo_label.setPixmap(QPixmap(logo_path).scaledToWidth(120, Qt.SmoothTransformation))
        except Exception:
            logger.debug("PCReportWidget._set_logo: suppressed error", exc_info=True)

    def _set_progress_color(self, hex_color: str):
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                border-radius: 4px;
                text-align: center;
                height: 16px;
            }}
            QProgressBar::chunk {{
                background-color: {hex_color};
                border-radius: 3px;
                margin: 1px;
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
        self.status_label.setText(_tr("Generating PC report inside this tab..."))
        self.output.clear()
        self.output.appendPlainText(f"Report will be saved to: {self.report_path}")
        self.worker = _PCReportWorker(self._options(), self)
        self.worker.progress.connect(self.output.appendPlainText)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, html, json_text):
        self.progress.hide()
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
        if self.button_style:
            for button in (self.btn_run, self.btn_open, self.btn_folder):
                button.setStyleSheet(self.button_style)
        self._set_progress_color(
            theme.skin_for_state(locked=locked, active=converting).accent)
        self._set_logo()

    def shutdown(self):
        worker = self.worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.requestInterruption()
            worker.wait(5000)
