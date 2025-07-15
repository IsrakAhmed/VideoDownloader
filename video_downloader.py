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
            logging.error(f"Preview error for {self.url}: {str(e)}")
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
        try:
            if not os.path.exists(ffmpeg_path):
                logging.error("ffmpeg.exe not found in executable directory")
                raise FileNotFoundError("ffmpeg.exe is required but not found.")
            logging.info(f"Using ffmpeg from: {ffmpeg_path}")
            ydl_opts = {
                'outtmpl': os.path.join(self.output_path, '%(title)s.%(ext)s'),
                'format': 'best',
                'merge_output_format': None,
                'noplaylist': not self.playlist,
                'progress_hooks': [self.progress_hook],
                'quiet': False,
                'noprogress': False,
                'ffmpeg_location': ffmpeg_path,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(self.urls)
            self.finished_signal.emit()
        except Exception as e:
            error_str = str(e).lower()
            logging.error(f"Download error for {self.urls}: {str(e)}")
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
                self.error_signal.emit(str(e))

    def progress_hook(self, d):
        try:
            self.progress_signal.emit(d)
        except Exception as e:
            logging.error(f"Progress hook error: {str(e)}")

class VideoDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_info = []
        self.last_percentage = -1  # Track last percentage to filter redundant updates
        self.initUI()
        self.loading_states = ["Loading.", "Loading..", "Loading..."]
        self.loading_index = 0
        self.loading_timer = QTimer()
        try:
            self.loading_timer.timeout.connect(self.update_loading_animation)
        except Exception as e:
            logging.error(f"Failed to connect loading timer: {str(e)}")

    def initUI(self):
        try:
            self.setWindowTitle("Video Downloader")
            self.setGeometry(100, 100, 800, 600)

            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)

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

            platform_layout = QHBoxLayout()
            self.platform_label = QLabel("Platform:")
            self.platform_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
            self.platform_combo = QComboBox()
            self.platform_combo.addItems(["YouTube", "Facebook"])
            self.platform_combo.currentTextChanged.connect(self.update_ui_for_platform)
            platform_layout.addWidget(self.platform_label)
            platform_layout.addWidget(self.platform_combo)
            layout.addLayout(platform_layout)

            output_layout = QHBoxLayout()
            self.output_label = QLabel("Output Folder:")
            self.output_label.setFont(QFont('Segoe UI', 14, QFont.Bold))
            self.output_input = QLineEdit()
            default_output = os.path.join(os.path.expanduser("~"), "Downloads", "VideoDownloader")
            if not os.path.exists(default_output):
                try:
                    os.makedirs(default_output)
                except PermissionError as e:
                    logging.error(f"Failed to create directory {default_output}: {str(e)}")
                    default_output = tempfile.gettempdir()
                    logging.warning(f"Falling back to temp directory: {default_output}")
            self.output_input.setText(default_output)
            self.output_button = QPushButton("Browse")
            self.output_button.clicked.connect(self.browse_folder)
            output_layout.addWidget(self.output_label)
            output_layout.addWidget(self.output_input)
            output_layout.addWidget(self.output_button)
            layout.addLayout(output_layout)

            self.preview_layout = QVBoxLayout()
            self.video_title = QLabel("Video Title: Not loaded")
            self.video_title.setFont(QFont('Segoe UI', 16, QFont.Bold))
            self.thumbnail_label = QLabel()
            self.thumbnail_label.setFixedSize(320, 180)
            self.thumbnail_label.setAlignment(Qt.AlignCenter)
            self.thumbnail_label.setStyleSheet("border: 1px solid #dfe6e9; border-radius: 5px; background-color: #ffffff;")
            self.loading_label = QLabel("Loading.")
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

            self.progress_bar = QProgressBar()
            self.progress_bar.setValue(0)
            layout.addWidget(self.progress_bar)

            self.status_log = QTextEdit()
            self.status_log.setReadOnly(True)
            layout.addWidget(self.status_log)

            developer_label = QLabel("Developed by Israk Ahmed | Contact: israkahmed7@gmail.com")
            developer_label.setFont(QFont('Segoe UI', 10))
            developer_label.setAlignment(Qt.AlignCenter)
            developer_label.setStyleSheet("color: #7f8c8d; margin-top: 10px;")
            layout.addWidget(developer_label)

            self.update_ui_for_platform()
        except Exception as e:
            logging.error(f"UI initialization error: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to initialize UI. Please restart the application.</span>")

    def update_ui_for_platform(self):
        try:
            platform = self.platform_combo.currentText()
            self.select_all_check.setVisible(platform == "YouTube")
            self.video_list.setVisible(platform == "YouTube")
        except Exception as e:
            logging.error(f"Error updating UI for platform: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Error updating interface. Please try again.</span>")

    def browse_folder(self):
        try:
            folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
            if folder:
                self.output_input.setText(folder)
        except Exception as e:
            logging.error(f"Error browsing folder: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to browse for folder. Please try again.</span>")

    def clean_ansi_codes(self, text):
        try:
            ansi_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            return ansi_regex.sub('', text)
        except re.error as e:
            logging.error(f"Error cleaning ANSI codes: {str(e)}")
            return text

    def update_loading_animation(self):
        try:
            self.loading_index = (self.loading_index + 1) % len(self.loading_states)
            self.loading_label.setText(self.loading_states[self.loading_index])
        except Exception as e:
            logging.error(f"Error updating loading animation: {str(e)}")

    def is_not_found_error(self, error):
        try:
            error_lower = str(error).lower()
            return any(keyword in error_lower for keyword in [
                "video unavailable", "not found", "content not available",
                "video does not exist", "playlist does not exist", "removed",
                "private video", "unavailable video", "not available",
                "sign in", "login required"
            ])
        except Exception as e:
            logging.error(f"Error checking not found error: {str(e)}")
            return False

    def is_auth_required_error(self, error):
        try:
            error_lower = str(error).lower()
            return "sign in" in error_lower or "login required" in error_lower
        except Exception as e:
            logging.error(f"Error checking auth required error: {str(e)}")
            return False

    def is_valid_url_for_platform(self, url, platform):
        try:
            url_lower = url.lower()
            if platform == "YouTube":
                return "youtube.com" in url_lower or "youtu.be" in url_lower
            elif platform == "Facebook":
                return "facebook.com" in url_lower or "fb.watch" in url_lower
            return False
        except Exception as e:
            logging.error(f"Error validating URL for platform: {str(e)}")
            return False

    def get_best_thumbnail(self, info):
        try:
            if not info:
                return None
            if 'thumbnails' in info and isinstance(info['thumbnails'], list) and info['thumbnails']:
                thumbnails = sorted(info['thumbnails'], key=lambda x: x.get('height', 0), reverse=True)
                return thumbnails[0].get('url')
            return info.get('thumbnail')
        except Exception as e:
            logging.error(f"Error getting best thumbnail: {str(e)}")
            return None

    def start_preview(self):
        try:
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
            self.thumbnail_label.setPixmap(QPixmap())
            self.video_title.setText("Video Title: Loading...")
            self.loading_label.setVisible(True)
            self.loading_timer.start(500)
            self.status_log.append(f"Fetching info from {platform}...")

            self.preview_thread = PreviewThread(url, platform)
            self.preview_thread.info_signal.connect(self.handle_preview_info)
            self.preview_thread.error_signal.connect(self.handle_preview_error)
            self.preview_thread.start()
        except Exception as e:
            logging.error(f"Error starting preview: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to start preview. Please try again.</span>")
            self.loading_label.setVisible(False)
            self.loading_timer.stop()
            self.video_title.setText("Video Title: Not loaded")
            self.download_button.setEnabled(False)

    def handle_preview_info(self, info):
        try:
            platform = self.platform_combo.currentText()
            self.video_info = []
            self.video_list.clear()
            self.loading_label.setVisible(False)
            self.loading_timer.stop()

            if platform == "YouTube" and 'entries' in info and info.get('_type') == 'playlist':
                self.video_info = info['entries']
                self.video_title.setText(f"Playlist: {info.get('title', 'Unknown Playlist')}")
                for video in self.video_info:
                    self.video_list.addItem(video.get('title', 'Unknown Title'))
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
        except Exception as e:
            logging.error(f"Error handling preview info: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to process preview data. Please try again.</span>")
            self.loading_label.setVisible(False)
            self.loading_timer.stop()
            self.video_title.setText("Video Title: Not loaded")
            self.download_button.setEnabled(False)

    def handle_preview_error(self, error):
        try:
            self.loading_label.setVisible(False)
            self.loading_timer.stop()
            if self.is_not_found_error(error):
                error_msg = "Video/Playlist not found with this URL"
                if self.is_auth_required_error(error):
                    error_msg += ". For restricted videos, place a valid cookies.txt file in the application folder (C:\\Program Files\\VideoDownloader). See README.txt for instructions."
                self.status_log.append(f"<span style='color: #e74c3c;'>{error_msg}</span>")
            else:
                self.status_log.append("<span style='color: #e74c3c;'>An Error Occurred</span>")
            self.video_title.setText("Video Title: Not loaded")
            self.download_button.setEnabled(False)
        except Exception as e:
            logging.error(f"Error handling preview error: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to handle preview error. Please try again.</span>")
            self.video_title.setText("Video Title: Not loaded")
            self.download_button.setEnabled(False)

    def display_thumbnail(self, thumbnail_url):
        try:
            if thumbnail_url:
                response = requests.get(thumbnail_url, timeout=5)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
                image = image.convert('RGB')
                image = image.resize((320, 180), Image.LANCZOS)
                qimage = QImage(image.tobytes(), image.size[0], image.size[1], QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)
                self.thumbnail_label.setPixmap(pixmap)
            else:
                logging.warning("No thumbnail URL provided")
                self.thumbnail_label.setText("Thumbnail not available")
        except Exception as e:
            logging.error(f"Thumbnail error for URL {thumbnail_url}: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to load thumbnail. Please try again.</span>")
            self.thumbnail_label.setText("Thumbnail not available")

    def toggle_select_all(self, state):
        try:
            for i in range(self.video_list.count()):
                item = self.video_list.item(i)
                item.setSelected(state == Qt.Checked)
        except Exception as e:
            logging.error(f"Error toggling select all: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to toggle video selection. Please try again.</span>")

    def download_video(self):
        try:
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
                try:
                    os.makedirs(output_path)
                except PermissionError as e:
                    logging.error(f"Failed to create directory {output_path}: {str(e)}")
                    output_path = tempfile.gettempdir()
                    logging.warning(f"Falling back to temp directory: {output_path}")
                    self.output_input.setText(output_path)
                    self.status_log.append("<span style='color: #e7b416;'>Warning: Using temp directory due to permissions issue.</span>")

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
            self.last_percentage = -1
            self.status_log.append(f"Starting download from {platform}...")

            self.download_thread = DownloadThread(selected_videos, output_path, platform, is_playlist)
            self.download_thread.progress_signal.connect(self.progress_hook)
            self.download_thread.error_signal.connect(self.handle_error)
            self.download_thread.finished_signal.connect(self.download_finished)
            self.download_thread.start()
        except Exception as e:
            logging.error(f"Error starting download: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to start download. Please try again.</span>")
            self.download_button.setEnabled(True)

    def progress_hook(self, d):
        try:
            if d['status'] == 'downloading':
                percent_str = self.clean_ansi_codes(d.get('_percent_str', '0%')).replace('%', '').strip()
                speed = self.clean_ansi_codes(d.get('_speed_str', 'Unknown speed')).replace('i', 'iB').strip()
                try:
                    percentage = float(percent_str)
                    if percentage >= self.last_percentage + 0.1 or speed != "Unknown speed":
                        self.progress_bar.setValue(int(percentage))
                        self.status_log.append(f"Downloading: {percent_str}% at {speed}")
                        self.last_percentage = percentage
                except ValueError:
                    self.status_log.append(f"Downloading: {percent_str}% at {speed} (Invalid percentage format)")
            elif d['status'] == 'finished':
                self.status_log.append("Download finished, processing file...")
        except Exception as e:
            logging.error(f"Progress hook error: {str(e)}")

    def handle_error(self, error):
        try:
            if self.is_not_found_error(error):
                error_msg = "Video/Playlist not found with this URL"
                if self.is_auth_required_error(error):
                    error_msg += ". For restricted videos, place a valid cookies.txt file in the application folder (C:\\Program Files\\VideoDownloader). See README.txt for instructions."
                self.status_log.append(f"<span style='color: #e74c3c;'>{error_msg}</span>")
            else:
                self.status_log.append("<span style='color: #e74c3c;'>An Error Occurred</span>")
            self.download_button.setEnabled(True)
        except Exception as e:
            logging.error(f"Error handling download error: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to handle download error. Please try again.</span>")
            self.download_button.setEnabled(True)

    def download_finished(self):
        try:
            self.status_log.append("<span style='color: #2ecc71;'>Download complete!</span>")
            self.download_button.setEnabled(True)
            self.progress_bar.setValue(100)
        except Exception as e:
            logging.error(f"Error handling download finished: {str(e)}")
            self.status_log.append("<span style='color: #e74c3c;'>Failed to complete download process. Please try again.</span>")
            self.download_button.setEnabled(True)

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = VideoDownloaderApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Application startup error: {str(e)}")
        print(f"Application failed to start: {str(e)}")