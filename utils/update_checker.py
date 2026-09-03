import requests
import json
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from utils.version import APP_VERSION

# Replace with your actual version file URL
UPDATE_URL = "https://raw.githubusercontent.com/yourusername/NVC/main/version.json"

class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str) # version, url
    error_occurred = pyqtSignal(str)
    no_update = pyqtSignal()

    def check_for_updates(self):
        try:
            # In a real scenario, you would uncomment this network request
            # response = requests.get(UPDATE_URL, timeout=5)
            # response.raise_for_status()
            # data = response.json()
            
            # Mock response for demonstration
            data = {"version": "2.1", "url": "https://github.com/yourusername/NVC/releases"}
            
            latest_version = data.get("version")
            download_url = data.get("url")

            if self._is_newer(latest_version, APP_VERSION):
                self.update_available.emit(latest_version, download_url)
            else:
                self.no_update.emit()
                
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _is_newer(self, latest, current):
        try:
            l_parts = [int(x) for x in latest.split('.')]
            c_parts = [int(x) for x in current.split('.')]
            return l_parts > c_parts
        except:
            return False

class UpdateWorker(QThread):
    def __init__(self, checker):
        super().__init__()
        self.checker = checker

    def run(self):
        self.checker.check_for_updates()

