import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import json
import sys
import logging
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Save and load folder paths
settings_file = 'settings.json'

# Use application data directory for settings file
app_data_folder = os.path.join(os.getenv('APPDATA'), 'VideoConverterApp')
os.makedirs(app_data_folder, exist_ok=True)
settings_path = os.path.join(app_data_folder, settings_file)

def resource_path(relative_path):
    # Get the absolute path to the resource; works for both development and PyInstaller
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def save_settings(source, destination):
    settings = {
        'source_folder': source,
        'destination_folder': destination
    }
    with open(settings_path, 'w') as f:
        json.dump(settings, f)
    logging.info(f"Settings saved: {settings}")

def load_settings():
    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            logging.info(f"Settings loaded: {settings}")
            return settings
    return {'source_folder': '', 'destination_folder': ''}

# Function to get user input for directories
def get_directory(prompt, initial_dir=''):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    directory = filedialog.askdirectory(title=prompt, initialdir=initial_dir)
    logging.info(f"Directory selected: {directory}")
    return directory

# Function to convert .mov files to .mp4
def convert_videos(source_folder, destination_folder, status_label):
    new_files = [f for f in os.listdir(source_folder) if f.endswith('.mov') and not os.path.exists(os.path.join(destination_folder, os.path.splitext(f)[0] + '.mp4'))]
    if not new_files:
        status_label.config(text="Running... No new files found.")
    for file_name in new_files:
        source_file = os.path.join(source_folder, file_name)
        mp4_file_name = os.path.splitext(file_name)[0] + '.mp4'
        mp4_file_path = os.path.join(destination_folder, mp4_file_name)

        # Run ffmpeg to convert the file
        command = [
            resource_path('ffmpeg.exe'), '-n', '-i', source_file, '-vcodec', 'libx264', '-acodec', 'aac', mp4_file_path
        ]

        try:
            status_label.config(text=f"Converting: {file_name[:15]}...")
            subprocess.run(command, check=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            status_label.config(text=f"Finished conversion: {file_name[:15]}...")
            logging.info(f"Successfully converted: {file_name}")
        except FileNotFoundError:
            status_label.config(text=f"ffmpeg not found. Please check the path.")
            logging.error("ffmpeg.exe not found. Please make sure it is located in the correct directory.")
        except subprocess.CalledProcessError as e:
            status_label.config(text=f"Error converting {source_file}: {e}")
            logging.error(f"Error converting {source_file}: {e}")

# GUI for selecting folders and controlling the process
class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Converter")
        try:
            self.root.iconbitmap(resource_path('icon.ico'))
        except tk.TclError:
            logging.warning('icon.ico not found or could not be loaded. Running without icon.')
        self.root.geometry("300x450")
        self.root.resizable(False, False)

        # Load saved settings
        settings = load_settings()
        self.source_folder = settings.get('source_folder', '') or ''
        self.destination_folder = settings.get('destination_folder', '') or ''

        # Source folder button
        self.source_button = tk.Button(root, text="Select Source Folder", command=self.select_source_folder)
        self.source_button.grid(row=3, column=0, padx=10, pady=5)

        # Destination folder button
        self.destination_button = tk.Button(root, text="Select Destination Folder", command=self.select_destination_folder)
        self.destination_button.grid(row=3, column=1, padx=10, pady=5)

        # Status label
        try:
            self.logo_image = tk.PhotoImage(file=resource_path('logo.png')) if os.path.exists(resource_path('logo.png')) else None
            self.logo_label = tk.Label(root, image=self.logo_image) if self.logo_image else tk.Label(root, text="Video Converter")
            self.logo_label.grid(row=0, column=0, columnspan=2, pady=5)
        except tk.TclError:
            self.logo_label = tk.Label(root, text="Video Converter")
            self.logo_label.grid(row=0, column=0, columnspan=2, pady=5)

        self.status_label = tk.Label(root, text="Status: Off")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=5)
        self.status_label.config(width=40, anchor='w')

        # Start/Stop button
        self.start_button = tk.Button(root, text="Off", bg="red", command=self.toggle_process, width=40)
        self.start_button.grid(row=4, column=0, columnspan=2, pady=10)

        self.running = False
        self.thread = None
        self.stop_event = threading.Event()

        # Info menu
        menubar = tk.Menu(root)
        menubar.add_command(label="Info", command=self.show_info)
        root.config(menu=menubar)

        # Handle close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def select_source_folder(self):
        new_source_folder = get_directory("Select the Source Folder for .mov Files", initial_dir=self.source_folder or os.path.expanduser("~"))
        if new_source_folder:
            self.source_folder = new_source_folder
            self.status_label.config(text=f"Source Folder set to: {self.source_folder}")
            save_settings(self.source_folder, self.destination_folder)

    def select_destination_folder(self):
        new_destination_folder = get_directory("Select the Destination Folder for .mp4 Files", initial_dir=self.destination_folder or os.path.expanduser("~"))
        if new_destination_folder:
            self.destination_folder = new_destination_folder
            self.status_label.config(text=f"Destination Folder set to: {self.destination_folder}")
            save_settings(self.source_folder, self.destination_folder)

    def toggle_process(self):
        if self.running:
            self.running = False
            self.stop_event.set()
            self.start_button.config(text="Off", bg="red")
            self.status_label.config(text="Status: Off")
            logging.info("Conversion stopped.")
        else:
            if not self.source_folder or not self.destination_folder:
                self.status_label.config(text="Please select both source and destination folders.")
                logging.warning("Both source and destination folders need to be selected before starting.")
                return
            self.running = True
            self.stop_event.clear()
            self.start_button.config(text="On", bg="green")
            self.status_label.config(text="Running...")
            logging.info("Conversion started.")
            self.thread = threading.Thread(target=self.run_conversion)
            self.thread.daemon = True
            self.thread.start()

    def run_conversion(self):
        try:
            while self.running and not self.stop_event.is_set():
                if not self.root or not self.root.winfo_exists():
                    break  # Exit if the window has been destroyed
                files_converted = False
                new_files = [f for f in os.listdir(self.source_folder) if f.endswith('.mov') and not os.path.exists(os.path.join(self.destination_folder, os.path.splitext(f)[0] + '.mp4'))]
                if not new_files and not self.stop_event.is_set():
                    self.update_status_label("Running... No new files found.")
                for file_name in new_files:
                    if self.stop_event.is_set():
                        break
                    source_file = os.path.join(self.source_folder, file_name)
                    mp4_file_name = os.path.splitext(file_name)[0] + '.mp4'
                    mp4_file_path = os.path.join(self.destination_folder, mp4_file_name)

                    # Run ffmpeg to convert the file
                    command = [
                        resource_path('ffmpeg.exe'), '-nostdin', '-i', source_file, '-vcodec', 'libx264', '-acodec', 'aac', mp4_file_path
                    ]

                    try:
                        self.update_status_label(f"Converting: {file_name[:15]}...")
                        subprocess.run(command, check=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        self.update_status_label(f"Finished conversion: {file_name[:15]}...")
                        logging.info(f"Successfully converted: {file_name}")
                        files_converted = True
                    except FileNotFoundError:
                        self.update_status_label(f"ffmpeg not found. Please check the path.")
                        logging.error("ffmpeg.exe not found. Please make sure it is located in the correct directory.")
                        self.running = False
                        return
                    except subprocess.CalledProcessError as e:
                        self.update_status_label(f"Error converting {file_name[:15]}: {e}")
                        logging.error(f"Error converting {file_name[:15]}: {e}")

                if not files_converted and not self.stop_event.is_set():
                    self.update_status_label("Running... No new files found.")
                time.sleep(5)
                self.update_status_label("Waiting for new files...")
        except Exception as e:
            logging.error(f"Error in conversion thread: {e}")

    def update_status_label(self, text):
        # Check if the root window still exists before updating the status label
        if self.root and self.root.winfo_exists():
            self.status_label.config(text=text)

    def show_info(self):
        about_text = (
            "N Video Converter monitors a source folder for .mov files and converts them to .mp4 "
            "using FFMPEG. Converted files are saved in the destination folder, ensuring that "
            "no files are deleted from either location. The application continuously monitors the "
            "source folder for new files and converts them automatically.\n\n"
            "How to use this application:\n"
            "1. Click 'Select Source Folder' to choose the folder with .mov files.\n"
            "2. Click 'Select Destination Folder' to choose where converted .mp4 files will be saved.\n"
            "3. Press 'Run' to start monitoring and converting files. Press again to stop.\n\n"
            "This application uses FFMPEG for video conversion. You can download the required "
            "build of FFMPEG from: https://www.gyan.dev/ffmpeg/builds/\n\n"
            "This application was written in Python. The source code "
            "can be found at: https://github.com/ipaulbot/Video-converter"
        )
        messagebox.showinfo("About Video Converter", about_text)

    def on_closing(self):
        self.status_label.config(text="Closing... Please wait.")
        self.root.update()
        self.running = False
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=10)  # Join with a timeout to avoid indefinite blocking
        time.sleep(0.5)  # Give time for any background processes to complete
        self.root.destroy()

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterApp(root)
    root.mainloop()