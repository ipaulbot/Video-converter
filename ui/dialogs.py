import os
from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl

from utils.logger import logger
from utils.resources import resource_path

class EasterEggDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.DISPLAY_DURATION = 120000  # 2 minutes
        self.init_ui()
        self.start_timer()
        self.play_audio()

    def init_ui(self):
        team_image_path = resource_path('team.png')
        if os.path.exists(team_image_path):
            team_pixmap = QPixmap(team_image_path)
        else:
            team_pixmap = QPixmap()
            logger.error(f"Team image not found at {team_image_path}.")
        self.team_label = QLabel()
        self.team_label.setPixmap(team_pixmap)
        self.team_label.setAlignment(Qt.AlignCenter)
        self.team_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.team_label.setScaledContents(True)
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.team_label)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        self.resize(team_pixmap.size())

    def start_timer(self):
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(self.DISPLAY_DURATION)

    def play_audio(self):
        self.media_player = QMediaPlayer(self)
        audio_file_path = resource_path('paradise.mp3')
        if os.path.exists(audio_file_path):
            url = QUrl.fromLocalFile(audio_file_path)
            media_content = QMediaContent(url)
            self.media_player.setMedia(media_content)
            self.media_player.play()
        else:
            logger.error(f"Audio file not found at {audio_file_path}.")

    def closeEvent(self, event):
        if hasattr(self, 'media_player'):
            self.media_player.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

class ConfirmationDialog(QDialog):
    def __init__(self, action, icon_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        # Use new icons from graphics folder
        if action.lower() == 'lock':
            icon_path = resource_path('graphics/LOCK.ico')
        elif action.lower() == 'unlock':
            icon_path = resource_path('graphics/UNLOCK.ico')
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QIcon())
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui(action)

    def init_ui(self, action):
        layout = QVBoxLayout()
        text_label = QLabel(f"Are you sure you want to {action} the application?")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignCenter)
        button_box = QHBoxLayout()
        yes_button = QPushButton("Yes")
        no_button = QPushButton("No")
        yes_button.setCursor(Qt.PointingHandCursor)
        no_button.setCursor(Qt.PointingHandCursor)
        yes_button.clicked.connect(self.accept)
        no_button.clicked.connect(self.reject)
        button_box.addWidget(yes_button)
        button_box.addWidget(no_button)
        button_box.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)
        layout.addLayout(button_box)
        self.setLayout(layout)
        self.setFixedSize(250, 100)

class InfoDialog(QDialog):
    def __init__(self, parent=None, is_converting=False, button_style=None):
        super().__init__(parent)
        self.setWindowTitle("About Video Converter")
        self.setMinimumSize(400, 260)
        self.is_converting = is_converting
        self.button_style = button_style
        
        # Get the appropriate info icon based on parent's state
        if parent and hasattr(parent, 'get_icon_path'):
            icon_path = parent.get_icon_path('INFO')
        else:
            icon_path = resource_path('graphics/INFO.ico')
            
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QIcon(resource_path('graphics/INFO.ico')))
            
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()

    def init_ui(self):
        from PyQt5.QtWidgets import QScrollArea, QLabel, QPushButton
        layout = QVBoxLayout()
        
        # Create horizontal layout for image and text
        content_layout = QHBoxLayout()
        
        # Add dynamic ITSAVIBE image based on application state
        if self.parent() and hasattr(self.parent(), 'locked') and self.parent().locked:
            # Locked state - use grayscale
            itsavibe_image_path = resource_path('graphics/GRAYSCALEITSAVIBE.png')
        elif self.is_converting:
            # Monitoring/converting state - use green
            itsavibe_image_path = resource_path('graphics/GREENITSAVIBE.png')
        else:
            # Default state - use teal
            itsavibe_image_path = resource_path('graphics/TEALITSAVIBE.png')
            
        if os.path.exists(itsavibe_image_path):
            itsavibe_pixmap = QPixmap(itsavibe_image_path)
            itsavibe_label = QLabel()
            itsavibe_label.setPixmap(itsavibe_pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            itsavibe_label.setAlignment(Qt.AlignCenter)
            itsavibe_label.setStyleSheet("background: transparent; border: none;")
            content_layout.addWidget(itsavibe_label)
        
        # Add text on the right
        info_text = QLabel()
        info_text.setText(
            """
            <b>N Video Converter 2.1.160 &nbsp;|&nbsp; Build Date: July 2025</b><br><br>
            NVC is a Python-based utility that monitors a designated source folder for incoming video files and automatically converts them to a specified output format using FFMPEG. Converted files are saved to a destination folder, while original files can be optionally moved to a backup location. The application operates continuously, enabling hands-free, real-time video processing and format standardization.<br><br>
            This application was developed by Paul Hamblin.<br>
            <a href='https://github.com/ipaulbot' style='color:#0077b5;'>GitHub Repository</a> &nbsp;|&nbsp; <a href='https://www.linkedin.com/in/paul-hamblin-69b19595/' style='color:#0077b5;'>LinkedIn Profile</a><br>
            """
        )
        info_text.setWordWrap(True)
        info_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        info_text.setStyleSheet("background-color: transparent; padding: 10px; border: none;")
        info_text.setOpenExternalLinks(True)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_text)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content_layout.addWidget(scroll_area)
        
        layout.addLayout(content_layout)
        ok_button = QPushButton("OK")
        ok_button.setCursor(Qt.PointingHandCursor)
        ok_button.clicked.connect(self.accept)
        
        # Apply button style based on parent's state
        if self.button_style:
            ok_button.setStyleSheet(self.button_style)
            print(f"InfoDialog: Using provided button style")
        elif self.parent() and hasattr(self.parent(), 'locked') and self.parent().locked:
            # Apply grayscale style for locked state
            print(f"InfoDialog: Parent is locked, applying grayscale style")
            ok_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8a8a8a, stop:1 #7f7f7f);
                    color: #ffffff;
                    border: 1px solid #6a6a6a;
                    border-radius: 6px;
                    padding: 8px 16px;
                    min-width: 80px;
                    min-height: 28px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9a9a9a, stop:1 #8a8a8a);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7f7f7f, stop:1 #6a6a6a);
                }
            """)
        else:
            # Default teal style
            print(f"InfoDialog: Parent is not locked, applying teal style")
            ok_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #43a296, stop:1 #3a9284);
                    border: 1px solid #2d7d6f;
                    border-radius: 6px;
                    padding: 8px 16px;
                    min-width: 80px;
                    min-height: 28px;
                    font-weight: bold;
                    color: white;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4bb3a7, stop:1 #43a296);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a9284, stop:1 #2d7d6f);
                }
            """)
            
        layout.addWidget(ok_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)


class LockedSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings Locked")
        self.setFixedSize(400, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # Get the appropriate lock icon based on parent's state
        if parent and hasattr(parent, 'get_icon_path'):
            lock_icon_path = parent.get_icon_path('LOCK')
        else:
            lock_icon_path = resource_path('graphics/LOCK.ico')
            
        if os.path.exists(lock_icon_path):
            self.setWindowIcon(QIcon(lock_icon_path))
        else:
            self.setWindowIcon(QIcon(resource_path('graphics/LOCK.ico')))
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Message text
        message_label = QLabel("Settings are locked and cannot be modified.\n\nUnlock the application first to make changes.")
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
                color: #333333;
                background: transparent;
                border: none;
                padding: 10px;
            }
        """)
        
        # OK button
        ok_button = QPushButton("OK")
        ok_button.setFixedSize(80, 32)
        ok_button.setCursor(Qt.PointingHandCursor)
        ok_button.clicked.connect(self.accept)
        
        # Apply grayscale style for locked state
        ok_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8a8a8a, stop:1 #7f7f7f);
                color: #ffffff;
                border: 1px solid #6a6a6a;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9a9a9a, stop:1 #8a8a8a);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7f7f7f, stop:1 #6a6a6a);
            }
        """)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        
        layout.addWidget(message_label)
        layout.addLayout(button_layout)
        
        # Apply modern styling to the dialog
        self.setStyleSheet("""
            QDialog {
                background: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
            QWidget {
                background: #F5F5F5;
                color: #333333;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 9pt;
            }
        """)
        
        self.setLayout(layout)
