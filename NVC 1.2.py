import os
import subprocess
import threading
import json
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from pystray import Icon, MenuItem
from PIL import Image, ImageTk
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

settings_file = 'settings.json'
app_data_folder = os.path.join(os.getenv('APPDATA', os.path.expanduser("~")), 'VideoConverterApp')
os.makedirs(app_data_folder, exist_ok=True)
settings_path = os.path.join(app_data_folder, settings_file)
log_file_path = os.path.join(app_data_folder, 'conversion_log.txt')

last_scan_message_logged = False
last_no_files_message_logged = False

# Set up rotating log file
logger = logging.getLogger('VideoConverterLogger')
logger.setLevel(logging.INFO)
log_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5)  # 5 MB max size, keep 5 backups
formatter = logging.Formatter('%(asctime)s - %(message)s')
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        print(f"Warning: Resource file '{relative_path}' not found at path '{full_path}'.")
    return full_path


def save_settings(source, destination, backup, auto_run):
    with open(settings_path, 'w') as f:
        json.dump({'source_folder': source, 'destination_folder': destination, 'backup_folder': backup, 'auto_run': auto_run}, f)


def load_settings():
    return json.load(open(settings_path)) if os.path.exists(settings_path) else {'source_folder': '', 'destination_folder': '', 'backup_folder': '', 'auto_run': False}


def log_message(message, console_output=None):
    logger.info(message)
    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n"
    if console_output:
        console_output.insert(tk.END, log_entry)
        console_output.see(tk.END)
    else:
        print(log_entry)


def convert_videos(source_folder, destination_folder, backup_folder, stop_event, console_output=None):
    global last_scan_message_logged, last_no_files_message_logged
    new_files = [f for f in os.listdir(source_folder) if f.endswith('.mp4') and not os.path.exists(os.path.join(destination_folder, os.path.splitext(f)[0] + '.mov'))]
    if not new_files:
        if not last_scan_message_logged:
            log_message("Scanning source folder...", console_output)
            last_scan_message_logged = True
        if not last_no_files_message_logged:
            log_message("No new files found.", console_output)
            last_no_files_message_logged = True
        return
    last_scan_message_logged = False
    last_no_files_message_logged = False
    for file_name in new_files:
        if stop_event.is_set():
            log_message("Conversion stopped before completing all files.", console_output)
            return
        source_file = os.path.join(source_folder, file_name)
        mov_file_path = os.path.join(destination_folder, os.path.splitext(file_name)[0] + '.mov')
        command = [resource_path('ffmpeg.exe'), '-n', '-i', source_file, '-vcodec', 'libx264', '-acodec', 'aac', mov_file_path]
        try:
            log_message(f"Converting: {file_name}", console_output)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in process.stdout:
                if stop_event.is_set():
                    process.kill()
                    log_message(f"Conversion of {file_name} stopped.", console_output)
                    return
                if any(keyword in line.lower() for keyword in ["error", "conversion", "success"]):
                    log_message(line.strip(), console_output)
            process.wait()
            log_message(f"Successfully converted: {file_name}", console_output)
            if backup_folder:
                backup_file_path = os.path.join(backup_folder, file_name)
                os.rename(source_file, backup_file_path)
                log_message(f"Moved {file_name} to backup folder.", console_output)
        except FileNotFoundError:
            log_message("ffmpeg not found.", console_output)
        except subprocess.CalledProcessError as e:
            log_message(f"Error converting {source_file}: {e}", console_output)


class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Converter")
        self.root.geometry("600x400")
        self.root.resizable(False, False)  # Adjusted size for shorter height

        try:
            self.root.iconbitmap(resource_path('icon.ico'))
        except Exception as e:
            print(f"Error setting icon: {e}")

        # Initialize attributes before calling toggle_process
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.status_thread = None
        self.status_running = False
        self.start_button = None

        settings = load_settings()
        self.source_folder = settings.get('source_folder', '')
        self.destination_folder = settings.get('destination_folder', '')
        self.backup_folder = settings.get('backup_folder', '')
        self.auto_run = settings.get('auto_run', False)

        # Setup UI and other components
        self.setup_ui()
        self.setup_tray_icon()
        
        # Start minimized to the system tray
        self.root.withdraw()

        # If auto_run is enabled, start the conversion process automatically
        if self.auto_run and self.source_folder and self.destination_folder and self.backup_folder:
            self.start_conversion()

    def setup_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left side UI for control buttons
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Buttons
        tk.Button(left_frame, text="Source Folder", command=self.select_source_folder).pack(fill=tk.X, pady=5)
        tk.Button(left_frame, text="Destination Folder", command=self.select_destination_folder).pack(fill=tk.X, pady=5)
        tk.Button(left_frame, text="Backup Folder", command=self.select_backup_folder).pack(fill=tk.X, pady=5)

        # Logo
        logo_path = resource_path('logo.png')
        if os.path.exists(logo_path):
            logo_image = Image.open(logo_path).resize((120, 120), Image.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(left_frame, image=self.logo_photo)
            logo_label.pack(pady=10)

        # Start/Stop Button
        self.start_button = tk.Button(left_frame, text="Start/Stop Conversion", command=self.toggle_process)
        self.start_button.pack(fill=tk.X, pady=5)

        # Toggle auto-run switch
        self.auto_run_var = tk.BooleanVar(value=self.auto_run)
        auto_run_checkbox = tk.Checkbutton(left_frame, text="Auto Run on Startup", variable=self.auto_run_var, command=self.toggle_auto_run)
        auto_run_checkbox.pack(fill=tk.X, pady=5)

        # Info menu
        menubar = tk.Menu(self.root)
        menubar.add_command(label="Info", command=self.show_info)
        self.root.config(menu=menubar)

        # Right side for status information
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.console_output = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, width=50, height=12)  # Adjusted height to make it shorter
        self.console_output.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Status indicator at the bottom right
        self.status_label = tk.Label(self.root, text="Status: Off", font=("Helvetica", 10), anchor='w', width=16)
        self.status_label.pack(side=tk.BOTTOM, anchor=tk.E, padx=10, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def setup_tray_icon(self):
        def on_left_click(icon, event):
            if self.root.state() == "withdrawn":
                self.root.deiconify()
                
            else:
                self.root.withdraw()

        icon_image = Image.open(resource_path('icon.ico')) if os.path.exists(resource_path('icon.ico')) else Image.new('RGB', (64, 64), color='gray')
        menu = (MenuItem('Show', lambda: on_left_click(None, None)), MenuItem('Quit', self.quit_application))
        self.tray_icon = Icon("VideoConverter", icon_image, menu=menu)
        self.tray_icon.run_detached()
        self.tray_icon.visible = True
        self.tray_icon.update_menu()
        self.tray_icon.icon.left_click = on_left_click

    def select_source_folder(self):
        self.source_folder = filedialog.askdirectory(title="Select Source Folder", initialdir=self.source_folder)
        save_settings(self.source_folder, self.destination_folder, self.backup_folder, self.auto_run_var.get())
        log_message(f"Source folder updated: {self.source_folder}", self.console_output)

    def select_destination_folder(self):
        self.destination_folder = filedialog.askdirectory(title="Select Destination Folder", initialdir=self.destination_folder)
        save_settings(self.source_folder, self.destination_folder, self.backup_folder, self.auto_run_var.get())
        log_message(f"Destination folder updated: {self.destination_folder}", self.console_output)

    def select_backup_folder(self):
        self.backup_folder = filedialog.askdirectory(title="Select Backup Folder", initialdir=self.backup_folder)
        save_settings(self.source_folder, self.destination_folder, self.backup_folder, self.auto_run_var.get())
        log_message(f"Backup folder updated: {self.backup_folder}", self.console_output)

    def toggle_auto_run(self):
        self.auto_run = self.auto_run_var.get()
        save_settings(self.source_folder, self.destination_folder, self.backup_folder, self.auto_run)
        log_message(f"Auto Run on Startup set to: {self.auto_run}", self.console_output)

    def toggle_process(self):
        if self.running:
            self.stop_conversion()
        else:
            self.start_conversion()

    def start_conversion(self):
        if not self.source_folder or not self.destination_folder or not self.backup_folder:
            log_message("Please select all folders.", self.console_output)
            return
        self.running = True
        self.stop_event.clear()
        self.start_button.config(text="Stop Conversion")
        log_message("Conversion started.", self.console_output)
        self.thread = threading.Thread(target=self.run_conversion)
        self.thread.daemon = True
        self.thread.start()
        self.status_running = True
        self.status_thread = threading.Thread(target=self.update_status_indicator)
        self.status_thread.daemon = True
        self.status_thread.start()

    def stop_conversion(self):
        self.running = False
        self.stop_event.set()
        self.start_button.config(text="Start Conversion")
        log_message("Conversion stopped.", self.console_output)
        self.status_running = False

    def run_conversion(self):
        try:
            while self.running and not self.stop_event.is_set():
                convert_videos(self.source_folder, self.destination_folder, self.backup_folder, self.stop_event, self.console_output)
                time.sleep(5)
        except Exception as e:
            log_message(f"Error: {e}", self.console_output)
        finally:
            self.stop_event.set()

    def update_status_indicator(self):
        base_text = "Status: Running"
        indicator_state = ["", ".", "..", "..."]
        idx = 0
        while self.status_running:
            self.status_label.config(text=f"{base_text:<16}{indicator_state[idx % len(indicator_state)]}")
            idx += 1
            time.sleep(0.5)
        self.status_label.config(text="Status: Idle")

    def show_info(self):
        about_text = (
            "NVC 1.2 monitors a source folder for .mp4 files and converts them to .mov "
            "using FFMPEG. Converted files are saved in the destination folder, ensuring that "
            "no files are deleted from either location. After conversion, .mp4 files are moved to a backup folder. "
            "The application continuously monitors the source folder for new files and converts them automatically when detected.\n\n"
            "How to use this application:\n"
            "1. Click 'Source Folder' to choose the folder with .mp4 files.\n"
            "2. Click 'Destination Folder' to choose where converted .mov files will be saved.\n"
            "3. Click 'Backup Folder' to choose where .mp4 files will be moved after conversion.\n"
            "4. Press 'Start/Stop Conversion' to begin monitoring and converting files.\n"
            "5. Check 'Auto Run on Startup' if you want the application to start automatically with the same settings next time.\n\n"
            "This application uses FFMPEG for video conversion. You can download the required "
            "build of FFMPEG from: https://www.gyan.dev/ffmpeg/builds/\n\n"
            "This application was written in Python. The source code "
            "can be found at: https://github.com/ipaulbot/Video-converter"
        )
        messagebox.showinfo("About Video Converter", about_text)

    def minimize_to_tray(self, *args):
        self.root.withdraw()

    def quit_application(self, *args):
        self.running = False
        self.status_running = False
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=5)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterApp(root)
    root.mainloop()
