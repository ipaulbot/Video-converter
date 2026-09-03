from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFileDialog, QProgressBar, QPlainTextEdit, QGridLayout, QGraphicsOpacityEffect, QWidget, QSizePolicy
from PyQt5.QtCore import QCoreApplication, Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
import os, json, subprocess, sys, datetime, base64
from pc_report.orchestrator import run_all
from pc_report.render_html import render as render_html
from pc_report.render_json import render as render_json
from utils.file_naming import get_unique_path
from utils.logger import logger
from ui import theme




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

    def run(self):
        try:
            html, json_text = self._generate()
        except Exception as exc:
            self.progress.emit(f"[error] PC report failed: {exc}")
            html = f"<html><body><h1>PC Report Failed</h1><p>{exc}</p></body></html>"
            json_text = ''
        self.finished.emit(html, json_text)

    def _generate(self):
        redact = self.options.get('redact', True)
        include_json = self.options.get('include_json', False)
        # Run modular collectors via orchestrator
        self.progress.emit('Running PC report…')
        meta, data, errors = run_all({
            'operating_system': True,
            'installed_updates': self.options.get('updates', True),
            'installed_programs': self.options.get('programs', True),
            'security': self.options.get('security', True),
            'hardware': True,
            'network': True,
            'services': True,
            'processes': True,
            'licenses': True,
            'environment': True,
            'network_info': True,
            'printers': True,
            'autoruns': True,
            'services_limit': 1000,
            'processes_limit': 1000,
        }, progress_cb=lambda name, completed, total: self.progress.emit(f"{name} ({completed}/{total})"))
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


class PCReportDialog(QDialog):
    def __init__(self, parent=None, button_style=None, converting=False, locked=False):
        super().__init__(parent)
        self.setWindowTitle(_tr('Generate PC Report'))
        self.setModal(True)
        # Start with a compact size; will refine after loading logo
        self.setMinimumSize(300, 260)
        layout = QVBoxLayout(self)
        # Logo header
        from utils.resources import resource_path
        # Container to underlay the heart image behind the main logo
        # We'll build a container to stack heart under the logo
        header_container = QWidget()
        header_container.setStyleSheet("QDialog { background: transparent; border: none; }")
        header_container.setAttribute(Qt.WA_TranslucentBackground, True)
        header_layout = QGridLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        # Heart underlay (hidden until report runs)
        self.heart_label = QLabel()
        self.heart_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.heart_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.heart_label.setAlignment(Qt.AlignHCenter)
        self._heart_effect = QGraphicsOpacityEffect(self.heart_label)
        self._heart_effect.setOpacity(0.0)
        self.heart_label.setGraphicsEffect(self._heart_effect)
        self._heart_anim = None

        heart_path = resource_path('graphics/PCREPORTHEART.png')

        # Main PC Report logo (variant based on app state)
        self.logo_label = QLabel()
        self.logo_label.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.logo_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.logo_label.setAlignment(Qt.AlignHCenter)
        # Select logo path based on state
        if locked:
            logo_path = resource_path('graphics/GRAYSCALEPCREPORT.png')
        elif converting:
            logo_path = resource_path('graphics/GREENPCREPORT.png')
        else:
            logo_path = resource_path('graphics/PCREPORT.png')

        from PyQt5.QtGui import QPixmap
        target_width = 310 - 24
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaledToWidth(target_width, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pix)
            self.logo_label.setMinimumHeight(pix.height() + 8)
            self.logo_label.setMinimumWidth(pix.width())
            # Set fixed window size similar to before
            self.setFixedWidth(310)
            self.setFixedHeight(560)
        if os.path.exists(heart_path):
            heart_pix = QPixmap(heart_path).scaledToWidth(target_width, Qt.SmoothTransformation)
            self.heart_label.setPixmap(heart_pix)
            self.heart_label.setMinimumHeight(heart_pix.height() + 8)
            self.heart_label.setMinimumWidth(heart_pix.width())
        # Add heart first (underlay), then logo (overlay)
        header_layout.addWidget(self.heart_label, 0, 0, Qt.AlignHCenter)
        header_layout.addWidget(self.logo_label, 0, 0, Qt.AlignHCenter)
        # Initially hide heart
        self.heart_label.hide()
        layout.addWidget(header_container)
        # Remove the help '?' button
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        # No options; include all sections, redact by default

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_run = QPushButton(_tr('Generate'))
        self.btn_save = QPushButton(_tr('Save HTML…'))
        # Apply main-window-provided button style so colors match current mode
        if button_style:
            try:
                self.btn_run.setStyleSheet(button_style)
                self.btn_save.setStyleSheet(button_style)
            except Exception:
                logger.debug("PCReportDialog.__init__: suppressed error", exc_info=True)
        # Ensure buttons have enough width and don't overlap
        self.btn_run.setMinimumWidth(140)
        self.btn_save.setMinimumWidth(140)
        self.btn_save.setEnabled(False)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        # Set progress color by app mode: green (monitoring), teal (idle), gray (locked)
        def _set_progress_color(hex_color: str):
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
        # Was another copy of the locked/active/idle chain; the theme owns it.
        _set_progress_color(
            theme.skin_for_state(locked=locked, active=converting).accent)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        # Show inline instructions inside the log area; wrap at widget width
        self.instructions_text = (
            "Press Generate to produce a PC report for your system. "
            "It gathers OS, hardware, security, network, and configuration info into a single HTML file."
        )
        try:
            self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        except Exception:
            logger.debug("PCReportDialog.__init__: suppressed error", exc_info=True)
        self.output.setPlainText(self.instructions_text)
        layout.addWidget(self.output)

        self.html = ''
        self.json_text = ''
        # State for save-button jiggle effect
        self._save_jiggle_anim = None
        self._save_jiggle_timer = None
        self._save_jiggle_count = 0
        self.btn_run.clicked.connect(self.on_run)
        self.btn_save.clicked.connect(self.on_save)

    def on_run(self):
        # In-log status during generation
        try:
            self.output.clear()
            self.output.appendPlainText("Generating…")
        except Exception:
            logger.debug("PCReportDialog.on_run: suppressed error", exc_info=True)
        opts = {
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
        self.progress.show()
        self.output.clear()
        self.btn_run.setEnabled(False)
        self.worker = _PCReportWorker(opts, self)
        self.worker.finished.connect(self.on_finished)
        # Live narration: connect to progress signal
        try:
            self.worker.progress.connect(lambda msg: self.output.appendPlainText(msg))
        except Exception:
            logger.debug("PCReportDialog.on_run: suppressed error", exc_info=True)
        # Start pulsing heart underlay
        try:
            self.heart_label.show()
            if self._heart_anim is not None:
                self._heart_anim.stop()
            self._heart_anim = QPropertyAnimation(self._heart_effect, b"opacity", self)
            # Slower pulse
            self._heart_anim.setDuration(2400)
            self._heart_anim.setKeyValueAt(0.0, 0.2)
            self._heart_anim.setKeyValueAt(0.5, 1.0)
            self._heart_anim.setKeyValueAt(1.0, 0.2)
            try:
                self._heart_anim.setEasingCurve(QEasingCurve.InOutSine)
            except Exception:
                logger.debug("PCReportDialog.on_run: suppressed error", exc_info=True)
            self._heart_anim.setLoopCount(-1)
            self._heart_anim.start()
        except Exception:
            logger.debug("PCReportDialog.on_run: suppressed error", exc_info=True)
        self.worker.start()

    def on_finished(self, html, json_text):
        self.progress.hide()
        self.btn_run.setEnabled(True)
        self.html = html
        self.json_text = json_text
        # Show completion message and prompt user to save
        try:
            self.output.clear()
            self.output.appendPlainText("PC Report complete.")
            self.output.appendPlainText("Click 'Save HTML…' to save your report.")
        except Exception:
            logger.debug("PCReportDialog.on_finished: suppressed error", exc_info=True)
        self.btn_save.setEnabled(True)
        # Emphasize Save button for user action
        try:
            self.btn_save.setAutoDefault(True)
            self.btn_save.setDefault(True)
            self.btn_save.setFocus()
        except Exception:
            logger.debug("PCReportDialog.on_finished: suppressed error", exc_info=True)
        # Start jiggle cycle: once immediately, then every 10s up to 4 times
        try:
            self._run_save_jiggle()
            self._save_jiggle_count = 0
            if self._save_jiggle_timer is None:
                self._save_jiggle_timer = QTimer(self)
                self._save_jiggle_timer.timeout.connect(self._on_jiggle_timeout)
            self._save_jiggle_timer.stop()
            self._save_jiggle_timer.start(10_000)
        except Exception:
            logger.debug("PCReportDialog.on_finished: suppressed error", exc_info=True)
        # Solid heart on completion
        try:
            if self._heart_anim is not None:
                self._heart_anim.stop()
            self._heart_effect.setOpacity(1.0)
            self.heart_label.show()
        except Exception:
            logger.debug("PCReportDialog.on_finished: suppressed error", exc_info=True)

    def _run_save_jiggle(self):
        g = self.btn_save.geometry()
        anim = QPropertyAnimation(self.btn_save, b"geometry", self)
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        anim.setKeyValueAt(0.0, g)
        anim.setKeyValueAt(0.2, QRect(g.x()-6, g.y(), g.width(), g.height()))
        anim.setKeyValueAt(0.5, QRect(g.x()+8, g.y(), g.width(), g.height()))
        anim.setKeyValueAt(0.8, QRect(g.x()-4, g.y(), g.width(), g.height()))
        anim.setKeyValueAt(1.0, g)
        self._save_jiggle_anim = anim
        anim.start()

    def _on_jiggle_timeout(self):
        try:
            self._save_jiggle_count += 1
            if self._save_jiggle_count >= 4:
                self._save_jiggle_timer.stop()
                return
            self._run_save_jiggle()
        except Exception:
            try:
                if self._save_jiggle_timer:
                    self._save_jiggle_timer.stop()
            except Exception:
                logger.debug("PCReportDialog._on_jiggle_timeout: suppressed error", exc_info=True)

    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save HTML Report', os.path.expanduser('~\\Desktop\\PC_Report.html'), 'HTML Files (*.html)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.html)
            if self.json_text:
                json_path = os.path.splitext(path)[0] + '.json'
                with open(json_path, 'w', encoding='utf-8') as jf:
                    jf.write(self.json_text)
            self.output.appendPlainText(f'Saved: {path}')
        except Exception as e:
            self.output.appendPlainText(f'Failed to save: {e}')
        # Stop scheduled jiggles after a successful save interaction
        try:
            if self._save_jiggle_timer:
                self._save_jiggle_timer.stop()
        except Exception:
            logger.debug("PCReportDialog.on_save: suppressed error", exc_info=True)


