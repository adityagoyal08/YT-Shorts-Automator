Here is a complete, well-structured `README.md` for your GitHub repository based on your project's flow, file structure, and logs. 

Since I cannot access external Claude links, I have crafted this README to be highly professional, comprehensive, and tailored exactly to the details you provided.

***

```markdown
# 🎬 YouTube to Shorts — Auto Scheduler (Ollama Edition)

A fully automated Python pipeline that downloads long-form YouTube videos from your favorite channels, uses AI to find the most engaging moments, clips them into YouTube Shorts, generates catchy titles, and uploads them to your YouTube account automatically. 

Powered entirely by **local AI (Ollama + Llama 3.2)** and **OpenAI Whisper** for zero-cost intelligence! 🚀

---

## ✨ Features
* **📥 Auto-Download:** Scrapes target channels and downloads videos using `yt-dlp`.
* **🎙️ Smart Transcription:** Uses `Whisper` to transcribe video audio (auto-detects languages like Hindi, English, etc.).
* **🤖 Local AI Clipping:** Prompts a local `Ollama` instance (`llama3.2:latest`) to identify the most viral/engaging moments (includes a fallback safety mechanism if AI fails).
* **✂️ Auto-Editing:** Uses `FFmpeg` to cut the selected moments into vertical Shorts-ready formats.
* **📝 AI Metadata Generation:** Ollama automatically generates engaging titles with emojis (e.g., *😍 Can 5 Girls Impressed Him? 🤔*).
* **📤 Auto-Upload:** Authenticates via Google API and uploads the generated Shorts directly to your YouTube channel.
* **⏰ Fully Scheduled:** Integrates with Windows Task Scheduler for hands-off operation (e.g., 9 AM & 9 PM daily).

---

## 📂 Project Structure

```text
aditya-trash/
  ├── n8n_yts_ollama.py     ← Main pipeline script (Download, AI, Edit, Upload)
  ├── scheduler.py          ← Logic to pick channels, track history, and run the pipeline
  ├── run_shorts.bat        ← Executable batch file for Windows Task Scheduler
  ├── channels.txt          ← List of target YouTube channels (Supports 100+ channels)
  ├── cookies.txt           ← YouTube cookies to bypass download restrictions
  ├── client_secret.json    ← Google API credentials (from Google Cloud / AI Studio)
  ├── youtube_token.json    ← Saved YouTube authentication token for auto-uploads
  └── shorts_output/        ← Auto-generated folder for temporary downloads and final clips
```

---

## 🛠️ Prerequisites & Installation

### 1. System Dependencies
Ensure the following are installed and added to your system's `PATH`:
* **Python 3.10+**
* **[FFmpeg](https://ffmpeg.org/download.html)** (Required for video editing and audio extraction)
* **[Ollama](https://ollama.com/)** (Running locally)

### 2. Pull the Local AI Model
Open your terminal and pull the Llama 3.2 model:
```bash
ollama run llama3.2:latest
```

### 3. Install Python Packages
```bash
pip install yt-dlp openai-whisper google-api-python-client google-auth-oauthlib google-auth-httplib2
```

### 4. Setup Authentication & Config Files
1. **`channels.txt`**: Add the YouTube channel URLs you want to monitor.
   ```text
   [https://www.youtube.com/@FilterCopy/videos](https://www.youtube.com/@FilterCopy/videos)
   [https://www.youtube.com/@BBKiVines/videos](https://www.youtube.com/@BBKiVines/videos)
   [https://www.youtube.com/@CarryMinati/videos](https://www.youtube.com/@CarryMinati/videos)
   ```
2. **`cookies.txt`**: Export your YouTube cookies using a browser extension (like *Get cookies.txt LOCALLY*) and save them here to prevent `yt-dlp` from being blocked.
3. **`client_secret.json`**: Get your OAuth 2.0 Client IDs from the [Google Cloud Console](https://console.cloud.google.com/) (Ensure the YouTube Data API v3 is enabled).
4. **`youtube_token.json`**: This will be generated automatically the first time you run the script and authenticate via your browser.

---

## ⚙️ How It Works (The Flow)

When the script runs, it follows this exact execution pipeline:
1. **Check Dependencies:** Verifies FFmpeg, yt-dlp, Whisper, Ollama, and Google APIs.
2. **Fetch Video:** Selects a target channel from `channels.txt` and downloads a recent video.
3. **Transcribe:** Whisper transcribes the full video and creates timestamps.
4. **AI Clip Selection:** The transcript is sent to local Llama 3.2 via Ollama to find the best 30-60 second segments. *(Fallback: If Ollama fails to find a valid clip, it safely slices clips every 60 seconds).*
5. **Video Processing:** FFmpeg cuts the video and formats it.
6. **Metadata & Upload:** Ollama generates a catchy title, and the Google API uploads it directly to YouTube Shorts!

---

## ⏰ Automation Setup (Windows Task Scheduler)

Set this up once, and your PC will run a fully automated YouTube Shorts factory.

### Step 1: Create the Batch File
Ensure `run_shorts.bat` has the following code:
```bat
@echo off
cd C:\Users\Administratorr\Documents\aditya-trash
python scheduler.py
```

### Step 2: Open Task Scheduler
Press `Win + S` → search **Task Scheduler** → Open it.

### Step 3: Create Morning Task (9:00 AM)
1. Click **Create Basic Task** (Right panel).
2. **Name:** `YouTube Shorts Morning`
3. **Trigger:** `Daily` → Start: `9:00 AM`
4. **Action:** `Start a program`
   * **Program/script:** Browse to `C:\Users\Administratorr\Documents\aditya-trash\run_shorts.bat`
5. Click **Finish**.

### Step 4: Create Evening Task (9:00 PM)
Repeat Step 3, but use:
* **Name:** `YouTube Shorts Evening`
* **Trigger:** `Daily` → Start: `9:00 PM`

### Step 5: Prevent PC from Sleeping
Your PC must be awake for the tasks to trigger:
1. Press `Win + S` → search **Power & Sleep settings**.
2. Under **Sleep**, set *When plugged in, PC goes to sleep after* to **Never**.

---

## 📝 Example Output Log
```text
🔍 Checking dependencies...
✅ FFmpeg found
✅ yt-dlp found
✅ whisper found
✅ Ollama running with model: llama3.2:latest
✅ google-api-python-client found
...
✅ Downloaded the video
✅ Whisper transcribed 162 segments, detected Hindi
✅ Ollama picked clip moments
✅ FFmpeg cut short_01.mp4 (7.0 MB)
✅ Ollama generated titles
✅ Uploaded! [https://youtube.com/shorts/YRuYCnzhrY8](https://youtube.com/shorts/YRuYCnzhrY8)
============================================================
  ✅ DONE!
============================================================
```

---

## ⚠️ Disclaimer
* Make sure you have the right to repurpose and upload the videos you are downloading.
* This tool is intended for educational purposes and personal channel automation. 
* Keep your `client_secret.json`, `cookies.txt`, and `youtube_token.json` completely private! Add them to your `.gitignore`.
```
