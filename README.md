# Video Downloader

## Overview
This application allows users to download videos from YouTube and Facebook with a simple and intuitive interface.

## Requirements
- Python (for initial setup or alternative cookie generation)
- yt-dlp (optional, for cookie generation)

## Usage
### Downloading Videos
1. Launch the Video Downloader application.
2. Enter the URL of the video from YouTube or Facebook.
3. Select the platform (YouTube or Facebook) from the dropdown menu.
4. Click "Preview" to verify the video details.
5. Choose the output folder and click "Download Selected" to start the download.

### Handling Age-Restricted or Private YouTube Videos
For videos that require authentication (e.g., age-restricted or private content), follow these steps:

1. **Log in to YouTube**:
   - Use a supported browser (e.g., Chrome, Brave, or Edge).

2. **Export Cookies**:
   - **Option 1: Browser Extension**
     - Install a browser extension such as "Get cookies.txt LOCALLY" (for Chrome/Brave/Edge) or "cookies.txt" (for Firefox).
     - Export the cookies to a file named `cookies.txt`.
   - **Option 2: Using yt-dlp**
     - Ensure Python and yt-dlp are installed (`pip install yt-dlp`).
     - Run the following command in your terminal or command prompt:
       ```bash
       yt-dlp --cookies-from-browser chrome > cookies.txt
       ```
     - This generates a `cookies.txt` file from your browser's cookies.

3. **Place the Cookies File**:
   - Move the `cookies.txt` file to `C:\Program Files\VideoDownloader`.

4. **Restart and Retry**:
   - Restart the Video Downloader application.
   - Enter the restricted URL and attempt the download again.

## Installation
The installer for the Video Downloader application can be downloaded from the following link:
- [Installer Download](https://drive.google.com/drive/folders/1zXffTHsDPrrNeUZYrMulv4K58bhGaXhA?usp=sharing)

## Contact
For support or inquiries, please contact:
- Email: [israkahmed7@gmail.com](mailto:israkahmed7@gmail.com)