import os
import sys
import yt_dlp
import requests
import re
import logging
import tempfile
from PIL import Image
from io import BytesIO
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QFileDialog,
    QListWidget, QCheckBox, QProgressBar
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Set up logging to a user-writable temporary directory
log_dir = tempfile.gettempdir()
log_file = os.path.join(log_dir, 'video_downloader.log')
try:
    logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                        format='%(asctime)s - %(levelname)s - %(message)s')
except PermissionError as e:
    # Fallback to console logging if file access fails
    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error(f"Failed to create log file in {log_dir}: {str(e)}")

class PreviewThread(QThread):
    info_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, url, platform):
        super().__init__()
        self.url = url
        self.platform = platform

    def run(self):
        ydl_opts = {
            'extract_flat': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.info_signal.emit(info)
        except Exception as e:
            error_str = str(e).lower()
            # Retry with cookies only for YouTube if authentication is required
            if self.platform == "YouTube" and ("sign in" in error_str or "login required" in error_str) and os.path.exists('cookies.txt'):
                ydl_opts['cookiefile'] = 'cookies.txt'
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(self.url, download=False)
                        self.info_signal.emit(info)
                except Exception as e2:
                    logging.error(f"Preview error with cookies for {self.url}: {str(e2)}")
                    self.error_signal.emit(str(e2))
            else:
                logging.error(f"Preview error for {self.url}: {str(e)}")
                self.error_signal.emit(str(e))

class DownloadThread(QThread):
    progress_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, urls, output_path, platform, playlist=False):
        super().__init__()
        self.urls = urls
        self.output_path = output_path
        self.platform = platform
        self.playlist = playlist

    def run(self):
        ffmpeg_path = os.path.join(os.path.dirname(sys.argv[0]), 'ffmpeg.exe')
        ydl_opts = {
            'outtmpl': os.path.join(self.output_path, '%(title)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best' if self.platform == "YouTube" else 'best',
            'merge_output_format': 'webm' if self.platform == "YouTube" else 'mp4',
            'noplaylist': not self.playlist,
            'progress_hooks': [self.progress_hook],
            'quiet': False,
            'noprogress': False,
            'ffmpeg_location': ffmpeg_path,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(self.urls)
            self.finished_signal.emit()
        except Exception as e:
            error_str = str(e).lower()
            # Retry with cookies only for YouTube if authentication is required
            if self.platform == "YouTube" and ("sign in" in error_str or "login required" in error_str) and os.path.exists('cookies.txt'):
                ydl_opts['cookiefile'] = 'cookies.txt'
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download(self.urls)
                    self.finished_signal.emit()
                except Exception as e2:
                    logging.error(f"Download error with cookies for {self.urls}: {str(e2)}")
                    self.error_signal.emit(str(e2))
            else:
                logging.error(f"Download error for {self.urls}: {str(e)}")
                self.error_signal.emit(str(e))

    def progress_hook(self, d):
        self.progress_signal.emit(d)

class VideoDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_info = []
        self.last_percentage = -1  # Track last percentage to filter redundant updates
        self.initUI()
        self.loading_states = ["Loading.", "Loading..", "Loading..."]
        self.loading_index = 0
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self.update_loading_animation)

    def initUI(self):
        self.setWindowTitle("Video Downloader")
        self.setGeometry(100, 100, 800, 600)

        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Apply stylesheet for minimalistic colors and modern look
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f7fa;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                color: #2c3e50;
            }
            QLineEdit {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                padding: 8px;
                border: 1px solid #dfe6e9;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QComboBox {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                padding: 8px;
                border: 1px solid #dfe6e9;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QPushButton {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                padding: 8px 16px;
                border: none;
                border-radius: 5px;
                background-color: #3498db;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #b0b0b0;
            }
            QTextEdit {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                border: 1px solid #dfe6e9;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QProgressBar {
                border: 1px solid #dfe6e9;
                border-radius: 5px;
                text-align: center;
                background-color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                border-radius: 3px;
            }
            QListWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                border: 1px solid #dfe6e9;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QCheckBox {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #2c3e50;
            }
        """)

        # URL input
        url_layout = QHBoxLayout()
        self.url_label = QLabel("Video URL:")
        self.url_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube or Facebook video URL")
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.start_preview)
        url_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.preview_button)
        layout.addLayout(url_layout)

        # Platform selection
        platform_layout = QHBoxLayout()
        self.platform_label = QLabel("Platform:")
        self.platform_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["YouTube", "Facebook"])
        self.platform_combo.currentTextChanged.connect(self.update_ui_for_platform)
        platform_layout.addWidget(self.platform_label)
        platform_layout.addWidget(self.platform_combo)
        layout.addLayout(platform_layout)

        # Output directory
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Folder:")
        self.output_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.output_input = QLineEdit()
        self.output_input.setText(os.path.join(os.getcwd(), "downloads"))
        self.output_button = QPushButton("Browse")
        self.output_button.clicked.connect(self.browse_folder)
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_input)
        output_layout.addWidget(self.output_button)
        layout.addLayout(output_layout)

        # Video/Playlist preview
        self.preview_layout = QVBoxLayout()
        self.video_title = QLabel("Video Title: Not loaded")
        self.video_title.setFont(QFont('Segoe UI', 16, QFont.Bold))
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px solid #dfe6e9; border-radius: 5px; background-color: #ffffff;")
        self.loading_label = QLabel("Loading.")  # Loading indicator
        self.loading_label.setFont(QFont('Segoe UI', 12))
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setVisible(False)
        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QListWidget.MultiSelection)
        self.select_all_check = QCheckBox("Select All Videos (YouTube Playlist)")
        self.select_all_check.stateChanged.connect(self.toggle_select_all)
        self.preview_layout.addWidget(self.video_title)
        self.preview_layout.addWidget(self.thumbnail_label)
        self.preview_layout.addWidget(self.loading_label)
        self.preview_layout.addWidget(self.select_all_check)
        self.preview_layout.addWidget(self.video_list)
        layout.addLayout(self.preview_layout)

        # Download button
        self.download_button = QPushButton("Download Selected")
        self.download_button.clicked.connect(self.download_video)
        self.download_button.setEnabled(False)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:disabled {
                background-color: #b0b0b0;
            }
        """)
        layout.addWidget(self.download_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Status log
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        layout.addWidget(self.status_log)

        # Developer information
        developer_label = QLabel("Developed by Israk Ahmed | Contact: israkahmed7@gmail.com")
        developer_label.setFont(QFont('Segoe UI', 10))
        developer_label.setAlignment(Qt.AlignCenter)
        developer_label.setStyleSheet("color: #7f8c8d; margin-top: 10px;")
        layout.addWidget(developer_label)

        self.update_ui_for_platform()

    def update_ui_for_platform(self):
        platform = self.platform_combo.currentText()
        self.select_all_check.setVisible(platform == "YouTube")
        self.video_list.setVisible(platform == "YouTube")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_input.setText(folder)

    def clean_ansi_codes(self, text):
        """Remove ANSI escape codes from text."""
        ansi_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_regex.sub('', text)

    def update_loading_animation(self):
        """Cycle through loading states for animation effect."""
        self.loading_index = (self.loading_index + 1) % len(self.loading_states)
        self.loading_label.setText(self.loading_states[self.loading_index])

    def is_not_found_error(self, error):
        """Check if the error indicates a video or playlist is not found or requires authentication."""
        error_lower = str(error).lower()
        return any(keyword in error_lower for keyword in [
            "video unavailable", "not found", "content not available",
            "video does not exist", "playlist does not exist", "removed",
            "private video", "unavailable video", "not available",
            "sign in", "login required"
        ])

    def is_auth_required_error(self, error):
        """Check if the error indicates authentication is required."""
        error_lower = str(error).lower()
        return "sign in" in error_lower or "login required" in error_lower

    def is_valid_url_for_platform(self, url, platform):
        """Check if the URL matches the selected platform."""
        url_lower = url.lower()
        if platform == "YouTube":
            return "youtube.com" in url_lower or "youtu.be" in url_lower
        elif platform == "Facebook":
            return "facebook.com" in url_lower or "fb.watch" in url_lower
        return False

    def get_best_thumbnail(self, info):
        """Select the best available thumbnail URL from yt-dlp info."""
        if not info:
            return None
        # Try to get the highest quality thumbnail
        if 'thumbnails' in info and isinstance(info['thumbnails'], list) and info['thumbnails']:
            # Sort thumbnails by resolution (if available) or take the last one (usually highest quality)
            thumbnails = sorted(info['thumbnails'], key=lambda x: x.get('height', 0), reverse=True)
            return thumbnails[0].get('url')
        return info.get('thumbnail')

    def start_preview(self):
        url = self.url_input.text().strip()
        platform = self.platform_combo.currentText()

        if not url:
            self.status_log.append("<span style='color: #e74c3c;'>Error: Please enter a valid URL.</span>")
            return

        if not self.is_valid_url_for_platform(url, platform):
            self.status_log.append("<span style='color: #e74c3c;'>Invalid URL for selected platform</span>")
            return

        self.video_info = []
        self.video_list.clear()
        self.download_button.setEnabled(False)
        self.thumbnail_label.setPixmap(QPixmap())  # Clear thumbnail
        self.video_title.setText("Video Title: Loading...")
        self.loading_label.setVisible(True)  # Show loading indicator
        self.loading_timer.start(500)  # Update every 500ms for animation
        self.status_log.append(f"Fetching info from {platform}...")

        self.preview_thread = PreviewThread(url, platform)
        self.preview_thread.info_signal.connect(self.handle_preview_info)
        self.preview_thread.error_signal.connect(self.handle_preview_error)
        self.preview_thread.start()

    def handle_preview_info(self, info):
        platform = self.platform_combo.currentText()
        self.video_info = []
        self.video_list.clear()
        self.loading_label.setVisible(False)  # Hide loading indicator
        self.loading_timer.stop()  # Stop animation

        if platform == "YouTube" and 'entries' in info and info.get('_type') == 'playlist':
            self.video_info = info['entries']
            self.video_title.setText(f"Playlist: {info.get('title', 'Unknown Playlist')}")
            for video in self.video_info:
                self.video_list.addItem(video.get('title', 'Unknown Title'))
            # Show thumbnail of first video
            if self.video_info:
                thumbnail_url = self.get_best_thumbnail(self.video_info[0])
                self.display_thumbnail(thumbnail_url)
        else:
            self.video_info = [info]
            self.video_title.setText(f"Video: {info.get('title', 'Unknown Title')}")
            thumbnail_url = self.get_best_thumbnail(info)
            self.display_thumbnail(thumbnail_url)
            if platform == "Facebook":
                self.video_list.setVisible(False)
            else:
                self.video_list.addItem(info.get('title', 'Unknown Title'))
        self.download_button.setEnabled(True)

    def handle_preview_error(self, error):
        self.loading_label.setVisible(False)  # Hide loading indicator
        self.loading_timer.stop()  # Stop animation
        if self.is_not_found_error(error):
            error_msg = "Video/Playlist not found with this URL"
            if self.is_auth_required_error(error):
                error_msg += ". For restricted videos, place a valid cookies.txt file in the application folder (C:\\Program Files\\VideoDownloader). See README.txt for instructions."
            self.status_log.append(f"<span style='color: #e74c3c;'>{error_msg}</span>")
        else:
            self.status_log.append("<span style='color: #e74c3c;'>An Error Occurred</span>")
        self.video_title.setText("Video Title: Not loaded")
        self.download_button.setEnabled(False)

    def display_thumbnail(self, thumbnail_url):
        if thumbnail_url:
            try:
                # Add timeout to prevent hanging
                response = requests.get(thumbnail_url, timeout=5)
                response.raise_for_status()  # Raise exception for bad status codes
                image = Image.open(BytesIO(response.content))
                image = image.convert('RGB')  # Ensure RGB format for compatibility
                image = image.resize((320, 180), Image.LANCZOS)
                qimage = QImage(image.tobytes(), image.size[0], image.size[1], QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)
                self.thumbnail_label.setPixmap(pixmap)
            except Exception as e:
                logging.error(f"Thumbnail error for URL {thumbnail_url}: {str(e)}")
                self.status_log.append("<span style='color: #e74c3c;'>An Error Occurred</span>")
                self.thumbnail_label.setText("Thumbnail not available")
        else:
            logging.warning("No thumbnail URL provided")
            self.thumbnail_label.setText("Thumbnail not available")

    def toggle_select_all(self, state):
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            item.setSelected(state == Qt.Checked)

    def download_video(self):
        url = self.url_input.text().strip()
        output_path = self.output_input.text().strip()
        platform = self.platform_combo.currentText()

        if not url:
            self.status_log.append("<span style='color: #e74c3c;'>Error: Please enter a valid URL.</span>")
            return

        if not self.is_valid_url_for_platform(url, platform):
            self.status_log.append("<span style='color: #e74c3c;'>Invalid URL for selected platform</span>")
            return

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        selected_videos = []
        is_playlist = platform == "YouTube" and len(self.video_info) > 1
        if is_playlist:
            selected_items = self.video_list.selectedItems()
            if not selected_items:
                self.status_log.append("<span style='color: #e74c3c;'>Error: Please select at least one video.</span>")
                return
            selected_videos = [self.video_info[self.video_list.row(item)]['url'] for item in selected_items]
        else:
            selected_videos = [url]

        self.download_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.last_percentage = -1  # Reset progress tracking
        self.status_log.append(f"Starting download from {platform}...")

        self.download_thread = DownloadThread(selected_videos, output_path, platform, is_playlist)
        self.download_thread.progress_signal.connect(self.progress_hook)
        self.download_thread.error_signal.connect(self.handle_error)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.start()

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent_str = self.clean_ansi_codes(d.get('_percent_str', '0%')).replace('%', '').strip()
            speed = self.clean_ansi_codes(d.get('_speed_str', 'Unknown speed')).replace('i', 'iB').strip()
            try:
                percentage = float(percent_str)
                # Only update if percentage has increased significantly to reduce spam
                if percentage >= self.last_percentage + 0.1 or speed != "Unknown speed":
                    self.progress_bar.setValue(int(percentage))
                    self.status_log.append(f"Downloading: {percent_str}% at {speed}")
                    self.last_percentage = percentage
            except ValueError:
                self.status_log.append(f"Downloading: {percent_str}% at {speed} (Invalid percentage format)")
        elif d['status'] == 'finished':
            self.status_log.append("Download finished, processing file...")

    def handle_error(self, error):
        if self.is_not_found_error(error):
            error_msg = "Video/Playlist not found with this URL"
            if self.is_auth_required_error(error):
                error_msg += ". For restricted videos, place a valid cookies.txt file in the application folder (C:\\Program Files\\VideoDownloader). See README.txt for instructions."
            self.status_log.append(f"<span style='color: #e74c3c;'>{error_msg}</span>")
        else:
            self.status_log.append("<span style='color: #e74c3c;'>An Error Occurred</span>")
        self.download_button.setEnabled(True)

    def download_finished(self):
        self.status_log.append("<span style='color: #2ecc71;'>Download complete!</span>")
        self.download_button.setEnabled(True)
        self.progress_bar.setValue(100)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoDownloaderApp()
    window.show()
    sys.exit(app.exec_())